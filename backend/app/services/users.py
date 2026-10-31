from app.data.models import User
from app.schemas import UserOut


def user_out(user: User) -> dict:
    out = UserOut.model_validate(user)
    out.has_password = bool(user.password_hash)
    return out.model_dump(mode="json")
