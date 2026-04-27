import base64
import hashlib

import bcrypt


PASSWORD_SCHEME_PREFIX = "bcrypt_sha256$"


def _password_bytes(password: str) -> bytes:
    return password.encode("utf-8")


def _prehash_password(password: str) -> bytes:
    digest = hashlib.sha256(_password_bytes(password)).digest()
    return base64.b64encode(digest)


def is_legacy_bcrypt_hash(password_hash: str | None) -> bool:
    return bool(password_hash and password_hash.startswith(("$2a$", "$2b$", "$2y$")))


def hash_password(password: str) -> str:
    bcrypt_hash = bcrypt.hashpw(_prehash_password(password), bcrypt.gensalt())
    return f"{PASSWORD_SCHEME_PREFIX}{bcrypt_hash.decode('utf-8')}"


def verify_password(password: str, password_hash: str | None) -> bool:
    if not password_hash:
        return False

    if password_hash.startswith(PASSWORD_SCHEME_PREFIX):
        encoded_hash = password_hash[len(PASSWORD_SCHEME_PREFIX):].encode("utf-8")
        return bcrypt.checkpw(_prehash_password(password), encoded_hash)

    if is_legacy_bcrypt_hash(password_hash):
        password_bytes = _password_bytes(password)
        encoded_hash = password_hash.encode("utf-8")
        try:
            return bcrypt.checkpw(password_bytes, encoded_hash)
        except ValueError:
            return bcrypt.checkpw(password_bytes[:72], encoded_hash)

    return password == password_hash


def verify_and_upgrade_password(password: str, password_hash: str | None) -> tuple[bool, str | None]:
    if not verify_password(password, password_hash):
        return False, None

    if is_legacy_bcrypt_hash(password_hash):
        return True, hash_password(password)

    return True, None
