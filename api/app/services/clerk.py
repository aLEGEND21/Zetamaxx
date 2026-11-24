"""Everything that talks to Clerk: session-token verification and the Backend API."""

import logging
import re
import time
from dataclasses import dataclass

import httpx
import jwt

from app.config import get_settings

log = logging.getLogger(__name__)

JWKS_MIN_REFETCH_SECONDS = 5  # an unknown `kid` triggers a refetch, but not a stampede
HTTP_TIMEOUT = 5.0


class InvalidToken(Exception):
    pass


@dataclass
class ClerkProfile:
    username: str | None
    display_name: str | None
    avatar_url: str | None


class ClerkClient:
    def __init__(self) -> None:
        self._keys: dict[str, jwt.PyJWK] = {}
        self._last_fetch = 0.0

    # --- network calls (tests replace these two) -------------------------------

    async def fetch_jwks(self) -> dict:
        settings = get_settings()
        async with httpx.AsyncClient(timeout=HTTP_TIMEOUT) as http:
            r = await http.get(
                f"{settings.clerk_api_url}/jwks",
                headers={"Authorization": f"Bearer {settings.clerk_secret_key}"},
            )
            r.raise_for_status()
            return r.json()

    async def fetch_user(self, clerk_user_id: str) -> ClerkProfile:
        settings = get_settings()
        async with httpx.AsyncClient(timeout=HTTP_TIMEOUT) as http:
            r = await http.get(
                f"{settings.clerk_api_url}/users/{clerk_user_id}",
                headers={"Authorization": f"Bearer {settings.clerk_secret_key}"},
            )
            r.raise_for_status()
            data = r.json()
        name = " ".join(p for p in (data.get("first_name"), data.get("last_name")) if p) or None
        return ClerkProfile(username=data.get("username"), display_name=name, avatar_url=data.get("image_url"))

    # --- token verification ----------------------------------------------------

    async def _key_for(self, kid: str) -> jwt.PyJWK:
        if kid not in self._keys and time.monotonic() - self._last_fetch >= JWKS_MIN_REFETCH_SECONDS:
            self._last_fetch = time.monotonic()
            try:
                jwks = await self.fetch_jwks()
            except httpx.HTTPError as exc:
                raise InvalidToken(f"could not fetch JWKS: {exc}") from exc
            self._keys = {k["kid"]: jwt.PyJWK(k) for k in jwks.get("keys", []) if "kid" in k}
        if kid not in self._keys:
            raise InvalidToken("unknown signing key")
        return self._keys[kid]

    async def verify_token(self, token: str) -> dict:
        """Return the claims of a valid Clerk session token, or raise InvalidToken."""
        try:
            kid = jwt.get_unverified_header(token).get("kid")
        except jwt.PyJWTError as exc:
            raise InvalidToken("malformed token") from exc
        if not kid:
            raise InvalidToken("token has no kid")
        key = await self._key_for(kid)
        try:
            claims = jwt.decode(
                token,
                key=key.key,
                algorithms=["RS256"],
                options={"require": ["exp", "sub"], "verify_aud": False},  # exp and nbf are checked
                leeway=5,
            )
        except jwt.PyJWTError as exc:
            raise InvalidToken(str(exc)) from exc
        # `azp` is the origin the token was issued to. Clerk omits it for some
        # non-browser clients; when present it must be one of ours.
        azp = claims.get("azp")
        if azp is not None and azp.rstrip("/") not in get_settings().allowed_origin_list:
            raise InvalidToken("token was issued for another origin")
        return claims

    def reset_cache(self) -> None:
        self._keys = {}
        self._last_fetch = 0.0


clerk = ClerkClient()


def normalize_username(raw: str | None, clerk_user_id: str) -> str:
    """Fit a Clerk username into ours: 3 to 20 chars of [a-z0-9_]."""
    name = re.sub(r"[^a-z0-9_]", "_", (raw or "").lower())[:20]
    if len(name) < 3:
        suffix = re.sub(r"[^a-z0-9]", "", clerk_user_id.lower())[-8:] or "player"
        name = f"user_{suffix}"[:20]
    return name
