"""Clerk JWT verification (local RSA key + mocked JWKS) and lazy provisioning."""

import json
import time
from datetime import timedelta

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from sqlalchemy import select, update

from app.auth import current_user
from app.db import SessionLocal
from app.main import app
from app.models import User, utcnow
from app.services.clerk import ClerkProfile, InvalidToken, clerk, normalize_username
from tests.conftest import auth

ORIGIN = "http://localhost:3000"


def _keypair(kid: str):
    private = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    jwk = json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(private.public_key()))
    jwk.update({"kid": kid, "use": "sig", "alg": "RS256"})
    return private, jwk


KEY_A, JWK_A = _keypair("key-a")
KEY_B, JWK_B = _keypair("key-b")


def make_token(private=KEY_A, kid="key-a", **overrides) -> str:
    now = int(time.time())
    claims = {"sub": "user_clerk123", "iat": now, "nbf": now - 5, "exp": now + 60, "azp": ORIGIN}
    claims.update(overrides)
    claims = {k: v for k, v in claims.items() if v is not None}
    return jwt.encode(claims, private, algorithm="RS256", headers={"kid": kid})


def cookie(token: str) -> dict[str, str]:
    return {"Cookie": f"__session={token}"}


@pytest.fixture
def clerk_mock(monkeypatch):
    """Replace Clerk's two network calls and count how often they are used."""
    state = {
        "jwks": [JWK_A],
        "jwks_calls": 0,
        "user_calls": 0,
        "profile": ClerkProfile("Ada-L", "Ada Lovelace", "https://img/ada.png"),
    }

    async def fetch_jwks():
        state["jwks_calls"] += 1
        return {"keys": state["jwks"]}

    async def fetch_user(clerk_user_id):
        state["user_calls"] += 1
        return state["profile"]

    clerk.reset_cache()
    monkeypatch.setattr(clerk, "fetch_jwks", fetch_jwks)
    monkeypatch.setattr(clerk, "fetch_user", fetch_user)
    yield state
    clerk.reset_cache()


@pytest.fixture
def real_auth(clerk_mock):
    """Use the real `current_user` dependency instead of the test bypass."""
    override = app.dependency_overrides.pop(current_user)
    yield clerk_mock
    app.dependency_overrides[current_user] = override


# --- JWT verification ---------------------------------------------------------


async def test_valid_token_is_accepted_and_jwks_is_cached(clerk_mock):
    claims = await clerk.verify_token(make_token())
    assert claims["sub"] == "user_clerk123"
    await clerk.verify_token(make_token())
    assert clerk_mock["jwks_calls"] == 1


async def test_expired_token_rejected(clerk_mock):
    with pytest.raises(InvalidToken):
        await clerk.verify_token(make_token(exp=int(time.time()) - 60))


async def test_not_yet_valid_token_rejected(clerk_mock):
    with pytest.raises(InvalidToken):
        await clerk.verify_token(make_token(nbf=int(time.time()) + 300))


async def test_wrong_origin_rejected(clerk_mock):
    with pytest.raises(InvalidToken):
        await clerk.verify_token(make_token(azp="https://evil.example"))


async def test_missing_azp_allowed(clerk_mock):
    assert (await clerk.verify_token(make_token(azp=None)))["sub"] == "user_clerk123"


async def test_forged_signature_rejected(clerk_mock):
    # Signed by a different key but claiming the trusted key's id.
    with pytest.raises(InvalidToken):
        await clerk.verify_token(make_token(private=KEY_B, kid="key-a"))


async def test_garbage_token_rejected(clerk_mock):
    for bad in ("", "not-a-jwt", "a.b.c"):
        with pytest.raises(InvalidToken):
            await clerk.verify_token(bad)


async def test_unknown_kid_triggers_refetch(clerk_mock, monkeypatch):
    await clerk.verify_token(make_token())
    # Clerk rotates keys: a token arrives signed by a key we have not seen.
    clerk_mock["jwks"] = [JWK_A, JWK_B]
    monkeypatch.setattr("app.services.clerk.JWKS_MIN_REFETCH_SECONDS", 0)
    claims = await clerk.verify_token(make_token(private=KEY_B, kid="key-b"))
    assert claims["sub"] == "user_clerk123"
    assert clerk_mock["jwks_calls"] == 2


async def test_unknown_kid_that_stays_unknown_is_rejected(clerk_mock, monkeypatch):
    monkeypatch.setattr("app.services.clerk.JWKS_MIN_REFETCH_SECONDS", 0)
    with pytest.raises(InvalidToken):
        await clerk.verify_token(make_token(private=KEY_B, kid="key-b"))


# --- lazy provisioning through the real dependency ---------------------------------


async def test_first_request_creates_the_user(client, real_auth):
    r = await client.get("/api/me", headers=cookie(make_token()))
    assert r.status_code == 200
    body = r.json()
    assert body["username"] == "ada_l"  # normalised to [a-z0-9_]
    assert body["display_name"] == "Ada Lovelace"
    assert body["avatar_url"] == "https://img/ada.png"
    assert body["timezone"] == "America/New_York" and body["timezone_set"] is False

    r2 = await client.get("/api/me", headers=cookie(make_token()))
    assert r2.json()["id"] == body["id"]
    assert real_auth["user_calls"] == 1  # fresh row: no second Clerk lookup


async def test_bearer_header_works_as_fallback(client, real_auth):
    r = await client.get("/api/me", headers={"Authorization": f"Bearer {make_token()}"})
    assert r.status_code == 200
    # An expired cookie does not block a valid bearer token.
    expired = make_token(exp=int(time.time()) - 60)
    r = await client.get("/api/me", headers={**cookie(expired), "Authorization": f"Bearer {make_token()}"})
    assert r.status_code == 200


async def test_no_or_bad_token_is_401(client, real_auth):
    r = await client.get("/api/me")
    assert r.status_code == 401
    assert r.json()["error"]["code"] == "unauthorized"
    r = await client.get("/api/me", headers=cookie(make_token(private=KEY_B, kid="key-a")))
    assert r.status_code == 401
    assert real_auth["user_calls"] == 0


async def test_stale_profile_is_refreshed(client, real_auth):
    await client.get("/api/me", headers=cookie(make_token()))
    real_auth["profile"] = ClerkProfile("ada_new", "Ada King", None)

    # Still fresh: nothing changes.
    r = await client.get("/api/me", headers=cookie(make_token()))
    assert r.json()["username"] == "ada_l"

    async with SessionLocal() as session:
        await session.execute(update(User).values(updated_at=utcnow() - timedelta(minutes=11)))
        await session.commit()
    r = await client.get("/api/me", headers=cookie(make_token()))
    assert r.json()["username"] == "ada_new"
    assert r.json()["display_name"] == "Ada King"
    assert r.json()["avatar_url"] is None
    assert real_auth["user_calls"] == 2


async def test_username_collision_gets_a_suffix(client, real_auth, make_user):
    await make_user("ada_l")
    r = await client.get("/api/me", headers=cookie(make_token()))
    assert r.json()["username"] == "ada_l_2"


def test_normalize_username():
    assert normalize_username("Ada-Lovelace", "user_x") == "ada_lovelace"
    assert normalize_username("a" * 40, "user_x") == "a" * 20
    assert normalize_username(None, "user_2abcDEF123") == "user_bcdef123"
    assert normalize_username("ab", "user_2abcDEF123") == "user_bcdef123"


# --- /api/me ---------------------------------------------------------------------------


async def test_patch_timezone(client, make_user):
    user = await make_user("grace", timezone_set=False)
    r = await client.patch("/api/me", json={"timezone": "Europe/Paris"}, headers=auth(user))
    assert r.status_code == 200
    assert r.json()["timezone"] == "Europe/Paris" and r.json()["timezone_set"] is True


async def test_patch_invalid_timezone_is_422(client, make_user):
    user = await make_user("grace")
    for bad in ("Mars/Olympus_Mons", "", "EST5EDT4"):
        r = await client.patch("/api/me", json={"timezone": bad}, headers=auth(user))
        assert r.status_code == 422, bad
        assert r.json()["error"]["code"] == "invalid_timezone"
    r = await client.patch("/api/me", json={}, headers=auth(user))
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "validation_error"


async def test_timestamps_come_back_timezone_aware_utc(make_user):
    await make_user("grace")
    async with SessionLocal() as session:
        user = (await session.execute(select(User))).scalar_one()
    assert user.created_at.tzinfo is not None
    assert user.created_at.utcoffset() == timedelta(0)
    assert abs(utcnow() - user.created_at) < timedelta(seconds=5)


async def test_naive_datetimes_are_rejected_on_write():
    from datetime import datetime

    from sqlalchemy.exc import StatementError

    async with SessionLocal() as session:
        session.add(User(clerk_user_id="c1", username="naive", created_at=datetime(2026, 1, 1)))
        with pytest.raises(StatementError):
            await session.commit()
