from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.data.models import User
from app.db import get_session
from app.errors import Forbidden, Unauthorized
from app.services.auth.tokens import decode_access_token

ACCESS_COOKIE = "stash_at"
REFRESH_COOKIE = "stash_rt"


async def current_user(request: Request, session: AsyncSession = Depends(get_session)) -> User:
    token = request.cookies.get(ACCESS_COOKIE)
    header = request.headers.get("authorization", "")
    if not token and header.lower().startswith("bearer "):
        token = header[7:]
    user_id = decode_access_token(token) if token else None
    if not user_id:
        raise Unauthorized("Sign in to continue.", code="unauthorized")
    user = await session.get(User, user_id)
    if not user:
        raise Unauthorized("Sign in to continue.", code="unauthorized")
    if user.suspended_at:
        raise Forbidden("This account is suspended.", code="account_suspended")
    request.state.user_id = str(user.id)
    return user
