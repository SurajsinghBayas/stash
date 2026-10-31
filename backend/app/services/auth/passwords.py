import asyncio

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerifyMismatchError

_hasher = PasswordHasher()  # argon2id with the library's current recommended parameters

# Verified against when the email is unknown, so a miss costs the same time as a wrong password.
_DUMMY_HASH = _hasher.hash("stash-dummy-password-for-timing")


async def hash_password(password: str) -> str:
    return await asyncio.to_thread(_hasher.hash, password)


async def verify_password(password: str, password_hash: str | None) -> bool:
    def _verify() -> bool:
        try:
            return _hasher.verify(password_hash or _DUMMY_HASH, password) and password_hash is not None
        except (VerifyMismatchError, InvalidHashError):
            return False

    return await asyncio.to_thread(_verify)
