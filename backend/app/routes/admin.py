from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.data.models import User
from app.db import get_session
from app.errors import NotFound
from app.middleware.auth import current_user
from app.schemas import data
from app.services import admin

router = APIRouter(tags=["admin"])


async def require_admin(user: User = Depends(current_user)) -> User:
    # 404, not 403: other accounts can't tell that an admin API exists.
    if not admin.is_admin(user):
        raise NotFound()
    return user


@router.get("/admin/metrics", dependencies=[Depends(require_admin)])
async def metrics(session: AsyncSession = Depends(get_session)):
    return data(await admin.metrics(session))
