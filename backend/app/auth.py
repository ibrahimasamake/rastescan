"""Officer accounts: argon2 password hashes, signed session tokens, and the expo PIN fallback."""
import hmac
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError

COOKIE = "rs_session"
ROLES = ("officer", "admin")
_hasher = PasswordHasher()
# Verified against when the email is unknown, so a wrong email and a wrong password take the same time.
_DUMMY_HASH = _hasher.hash("rastescan-timing-guard")


@dataclass(frozen=True)
class Officer:
    id: int | None  # None for the shared PIN login
    name: str
    role: str

    @property
    def is_admin(self) -> bool:
        return self.role == "admin"


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def check_password(stored_hash: str | None, password: str) -> bool:
    try:
        return _hasher.verify(stored_hash or _DUMMY_HASH, password) and stored_hash is not None
    except (VerificationError, InvalidHashError):
        return False


def load_secret(configured: str, data_dir: Path) -> str:
    """The signing key: from SECRET_KEY, or generated once and kept next to the database (never in git)."""
    if configured:
        return configured
    path = data_dir / "secret.key"
    if path.is_file():
        return path.read_text().strip()
    data_dir.mkdir(parents=True, exist_ok=True)
    key = secrets.token_urlsafe(48)
    path.write_text(key)
    path.chmod(0o600)
    return key


def issue_token(secret: str, officer_id: int, hours: int) -> str:
    now = datetime.now(timezone.utc)
    return jwt.encode({"sub": str(officer_id), "iat": now, "exp": now + timedelta(hours=hours)}, secret, algorithm="HS256")


def read_token(secret: str, token: str) -> int | None:
    try:
        return int(jwt.decode(token, secret, algorithms=["HS256"])["sub"])
    except (jwt.PyJWTError, KeyError, ValueError):
        return None


def pin_matches(configured: str, given: str | None) -> bool:
    return bool(configured) and given is not None and hmac.compare_digest(configured, given)


def valid_password(password: str) -> bool:
    return len(password) >= 10
