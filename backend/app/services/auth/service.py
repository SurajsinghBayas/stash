"""Account rules. Routes call these; these call the database and queue mail."""

import uuid
from dataclasses import dataclass
from datetime import timedelta

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.data.jobs import enqueue
from app.data.models import EmailToken, OAuthAccount, RefreshToken, User
from app.errors import AppError, Conflict, Forbidden, Unauthorized, ValidationFailed
from app.services.auth import tokens
from app.services.auth.passwords import hash_password, verify_password

VERIFY_TTL = timedelta(hours=24)
RESET_TTL = timedelta(minutes=30)


@dataclass
class Session:
    user: User
    access_token: str
    refresh_token: str


async def _issue(session: AsyncSession, user: User, family_id: uuid.UUID | None = None) -> Session:
    refresh, refresh_hash = tokens.new_opaque_token()
    session.add(RefreshToken(user_id=user.id, token_hash=refresh_hash, family_id=family_id or uuid.uuid4(),
                             expires_at=tokens.now() + timedelta(days=settings.refresh_token_ttl_days)))
    await session.commit()
    return Session(user, tokens.create_access_token(user.id), refresh)


async def _email_token(session: AsyncSession, user: User, purpose: str) -> str:
    # One live token per purpose: older unused ones stop working.
    await session.execute(update(EmailToken)
                          .where(EmailToken.user_id == user.id, EmailToken.purpose == purpose,
                                 EmailToken.used_at.is_(None))
                          .values(used_at=tokens.now()))
    token, token_hash = tokens.new_opaque_token()
    ttl = VERIFY_TTL if purpose == "verify" else RESET_TTL
    session.add(EmailToken(user_id=user.id, purpose=purpose, token_hash=token_hash, expires_at=tokens.now() + ttl))
    return token


async def _consume_email_token(session: AsyncSession, token: str, purpose: str) -> User:
    row = await session.scalar(
        select(EmailToken).where(EmailToken.token_hash == tokens.hash_token(token), EmailToken.purpose == purpose)
        .with_for_update()
    )
    if not row or row.used_at or row.expires_at < tokens.now():
        raise AppError("This link has expired or was already used.", code="invalid_token", status=400)
    row.used_at = tokens.now()
    user = await session.get(User, row.user_id)
    if not user:
        raise AppError("This link has expired or was already used.", code="invalid_token", status=400)
    return user


def check_password_rules(password: str) -> None:
    if len(password) < 10:
        raise ValidationFailed("password: use at least 10 characters")
    if len(password) > 128:
        raise ValidationFailed("password: use at most 128 characters")


async def send_verification(session: AsyncSession, user: User) -> None:
    token = await _email_token(session, user, "verify")
    await enqueue(session, "send_email", {"template": "verify_email", "to": user.email,
                                          "link": f"{settings.app_url}/verify-email?token={token}"})
    await session.commit()


async def signup(session: AsyncSession, email: str, password: str, display_name: str | None) -> User:
    check_password_rules(password)
    if await session.scalar(select(User.id).where(User.email == email)):
        raise Conflict("An account with this email already exists. Sign in instead.", code="email_taken")
    user = User(email=email, password_hash=await hash_password(password), display_name=display_name)
    session.add(user)
    await session.flush()
    await send_verification(session, user)
    return user


async def verify_email(session: AsyncSession, token: str) -> Session:
    user = await _consume_email_token(session, token, "verify")
    user.email_verified = True
    return await _issue(session, user)


async def resend_verification(session: AsyncSession, email: str) -> None:
    user = await session.scalar(select(User).where(User.email == email))
    if user and not user.email_verified and user.password_hash:
        await send_verification(session, user)


async def login(session: AsyncSession, email: str, password: str) -> Session:
    user = await session.scalar(select(User).where(User.email == email))
    if not await verify_password(password, user.password_hash if user else None) or not user:
        raise Unauthorized("Email or password is incorrect.", code="invalid_credentials")
    if user.suspended_at:
        raise Forbidden("This account is suspended.", code="account_suspended")
    if not user.email_verified:
        raise Forbidden("Confirm your email first. We can send the link again.", code="email_not_verified")
    return await _issue(session, user)


async def refresh(session: AsyncSession, refresh_token: str) -> Session:
    row = await session.scalar(
        select(RefreshToken).where(RefreshToken.token_hash == tokens.hash_token(refresh_token)).with_for_update()
    )
    if not row:
        raise Unauthorized("Session expired. Sign in again.", code="session_expired")
    if row.revoked_at:
        # A rotated token came back: someone else may hold it. End every session in this family.
        await session.execute(update(RefreshToken).where(RefreshToken.family_id == row.family_id,
                                                         RefreshToken.revoked_at.is_(None))
                              .values(revoked_at=tokens.now()))
        await session.commit()
        raise Unauthorized("Session expired. Sign in again.", code="session_expired")
    if row.expires_at < tokens.now():
        raise Unauthorized("Session expired. Sign in again.", code="session_expired")
    user = await session.get(User, row.user_id)
    if not user or user.suspended_at:
        raise Unauthorized("Session expired. Sign in again.", code="session_expired")
    row.revoked_at = tokens.now()
    return await _issue(session, user, family_id=row.family_id)


async def logout(session: AsyncSession, refresh_token: str | None) -> None:
    if not refresh_token:
        return
    row = await session.scalar(select(RefreshToken).where(RefreshToken.token_hash == tokens.hash_token(refresh_token)))
    if row:
        await session.execute(update(RefreshToken).where(RefreshToken.family_id == row.family_id,
                                                         RefreshToken.revoked_at.is_(None))
                              .values(revoked_at=tokens.now()))
        await session.commit()


async def logout_everywhere(session: AsyncSession, user_id: uuid.UUID) -> None:
    await session.execute(update(RefreshToken).where(RefreshToken.user_id == user_id,
                                                     RefreshToken.revoked_at.is_(None))
                          .values(revoked_at=tokens.now()))
    await session.commit()


async def forgot_password(session: AsyncSession, email: str) -> None:
    """Always succeeds from the caller's point of view: no account enumeration."""
    user = await session.scalar(select(User).where(User.email == email))
    if not user or user.suspended_at:
        return
    token = await _email_token(session, user, "reset")
    await enqueue(session, "send_email", {"template": "reset_password", "to": user.email,
                                          "link": f"{settings.app_url}/reset-password?token={token}"})
    await session.commit()


async def reset_password(session: AsyncSession, token: str, new_password: str) -> Session:
    check_password_rules(new_password)
    user = await _consume_email_token(session, token, "reset")
    user.password_hash = await hash_password(new_password)
    user.email_verified = True  # they proved they own the inbox
    await session.execute(update(RefreshToken).where(RefreshToken.user_id == user.id,
                                                     RefreshToken.revoked_at.is_(None))
                          .values(revoked_at=tokens.now()))
    return await _issue(session, user)


async def oauth_login(session: AsyncSession, *, provider: str, provider_user_id: str, email: str | None,
                      email_verified: bool, display_name: str | None, avatar_url: str | None) -> Session:
    account = await session.scalar(select(OAuthAccount).where(OAuthAccount.provider == provider,
                                                              OAuthAccount.provider_user_id == provider_user_id))
    if account:
        user = await session.get(User, account.user_id)
    else:
        user = None
        # Link to an existing account only on an email the provider has verified.
        if email and email_verified:
            user = await session.scalar(select(User).where(User.email == email))
        if user is None:
            taken = email and await session.scalar(select(User.id).where(User.email == email))
            user = User(email=email if email and email_verified and not taken else None,
                        email_verified=bool(email and email_verified and not taken),
                        display_name=display_name, avatar_url=avatar_url)
            session.add(user)
            await session.flush()
        elif email_verified:
            user.email_verified = True
        session.add(OAuthAccount(user_id=user.id, provider=provider, provider_user_id=provider_user_id))
    if not user:
        raise Unauthorized("Sign-in failed. Try again.", code="oauth_failed")
    if user.suspended_at:
        raise Forbidden("This account is suspended.", code="account_suspended")
    if not user.avatar_url and avatar_url:
        user.avatar_url = avatar_url
    if not user.display_name and display_name:
        user.display_name = display_name
    return await _issue(session, user)
