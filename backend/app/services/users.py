from app.data.models import User
from app.schemas import UserOut
from app.services.admin import is_admin


def user_out(user: User) -> dict:
    out = UserOut.model_validate(user)
    out.has_password = bool(user.password_hash)
    out.is_admin = is_admin(user)
    return out.model_dump(mode="json")
