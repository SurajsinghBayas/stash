from fastapi import APIRouter, Depends, Request, Response
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db import get_session
from app.errors import AppError
from app.middleware.auth import ACCESS_COOKIE, REFRESH_COOKIE
from app.middleware.rate_limit import client_ip, limit, limiter
from app.schemas import EmailIn, LoginIn, ResetIn, SignupIn, TokenIn, UserOut, data
from app.services.auth import oauth, service, tokens
from app.services.users import user_out

router = APIRouter(prefix="/auth", tags=["auth"])

OAUTH_COOKIE = "stash_oauth"


def _set_session(response: Response, s: service.Session) -> None:
    secure = settings.cookie_secure
    response.set_cookie(ACCESS_COOKIE, s.access_token, max_age=settings.access_token_ttl_min * 60,
                        httponly=True, secure=secure, samesite="lax", path="/api")
    response.set_cookie(REFRESH_COOKIE, s.refresh_token, max_age=settings.refresh_token_ttl_days * 86400,
                        httponly=True, secure=secure, samesite="lax", path="/api/v1/auth")


def _clear_session(response: Response) -> None:
    response.delete_cookie(ACCESS_COOKIE, path="/api")
    response.delete_cookie(REFRESH_COOKIE, path="/api/v1/auth")


@router.post("/signup", status_code=201, dependencies=[Depends(limit("signup", 5, 3600))])
async def signup(body: SignupIn, session: AsyncSession = Depends(get_session)):
    user = await service.signup(session, body.email, body.password, body.display_name)
    return data({"email": user.email, "verification_sent": True})


@router.post("/verify-email", dependencies=[Depends(limit("verify", 20, 3600))])
async def verify_email(body: TokenIn, response: Response, session: AsyncSession = Depends(get_session)):
    s = await service.verify_email(session, body.token)
    _set_session(response, s)
    return data(user_out(s.user))


@router.post("/verify-email/resend", status_code=202, dependencies=[Depends(limit("resend", 3, 3600))])
async def resend(body: EmailIn, session: AsyncSession = Depends(get_session)):
    await service.resend_verification(session, body.email)
    return data({"sent": True})


@router.post("/login", dependencies=[Depends(limit("login", 10, 300))])
async def login(body: LoginIn, request: Request, response: Response, session: AsyncSession = Depends(get_session)):
    limiter.hit(f"login:email:{body.email.lower()}", 5, 300)
    s = await service.login(session, body.email, body.password)
    _set_session(response, s)
    return data(user_out(s.user))


@router.post("/refresh", dependencies=[Depends(limit("refresh", 60, 300))])
async def refresh(request: Request, response: Response, session: AsyncSession = Depends(get_session)):
    token = request.cookies.get(REFRESH_COOKIE)
    if not token:
        _clear_session(response)
        raise AppError("Session expired. Sign in again.", code="session_expired", status=401)
    try:
        s = await service.refresh(session, token)
    except AppError:
        _clear_session(response)
        raise
    _set_session(response, s)
    return data(user_out(s.user))


@router.post("/logout", status_code=204)
async def logout(request: Request, response: Response, session: AsyncSession = Depends(get_session)):
    await service.logout(session, request.cookies.get(REFRESH_COOKIE))
    _clear_session(response)
    response.status_code = 204
    return response


@router.post("/password/forgot", status_code=202, dependencies=[Depends(limit("forgot", 3, 3600))])
async def forgot(body: EmailIn, session: AsyncSession = Depends(get_session)):
    limiter.hit(f"forgot:email:{body.email.lower()}", 3, 3600)
    await service.forgot_password(session, body.email)
    return data({"sent": True})


@router.post("/password/reset", dependencies=[Depends(limit("reset", 10, 3600))])
async def reset(body: ResetIn, response: Response, session: AsyncSession = Depends(get_session)):
    s = await service.reset_password(session, body.token, body.password)
    _set_session(response, s)
    return data(user_out(s.user))


@router.get("/providers")
async def providers():
    return data({"google": oauth.configured("google"), "x": oauth.configured("x")})


@router.get("/oauth/{provider}/start", dependencies=[Depends(limit("oauth", 20, 300))])
async def oauth_start(provider: str):
    if provider not in ("google", "x"):
        raise AppError("Unknown provider", code="not_found", status=404)
    url, state = oauth.start(provider)
    response = RedirectResponse(url, status_code=302)
    response.set_cookie(OAUTH_COOKIE, tokens.sign_state(state, 10, "oauth"), max_age=600, httponly=True,
                        secure=settings.cookie_secure, samesite="lax", path="/api/v1/auth/oauth")
    return response


@router.get("/oauth/{provider}/callback")
async def oauth_callback(provider: str, request: Request, session: AsyncSession = Depends(get_session)):
    def fail(reason: str) -> RedirectResponse:
        r = RedirectResponse(f"{settings.app_url}/login?error={reason}", status_code=302)
        r.delete_cookie(OAUTH_COOKIE, path="/api/v1/auth/oauth")
        return r

    limiter.hit(f"oauth-cb:ip:{client_ip(request)}", 20, 300)
    state = tokens.read_state(request.cookies.get(OAUTH_COOKIE, ""), "oauth")
    code = request.query_params.get("code")
    if (not state or state.get("provider") != provider or not code
            or request.query_params.get("state") != state.get("state")):
        return fail("oauth_state")
    try:
        profile = await oauth.finish(provider, code, state["verifier"])
        s = await service.oauth_login(session, provider=provider, provider_user_id=profile.provider_user_id,
                                      email=profile.email, email_verified=profile.email_verified,
                                      display_name=profile.display_name, avatar_url=profile.avatar_url)
    except AppError as exc:
        return fail(exc.code)
    response = RedirectResponse(f"{settings.app_url}/app", status_code=302)
    response.delete_cookie(OAUTH_COOKIE, path="/api/v1/auth/oauth")
    _set_session(response, s)
    return response


__all__ = ["router", "UserOut"]
