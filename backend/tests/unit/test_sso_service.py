"""Unit tests for SSO service: nonce exchange and user upsert."""

import time

import pytest

from app.services.sso_service import SSOService


@pytest.fixture(autouse=True)
def clear_nonces():
    """Ensure nonce store is clean between tests."""
    SSOService._nonces.clear()
    yield
    SSOService._nonces.clear()


class TestExchangeCode:
    """Tests for one-time exchange code pattern (Pitfall 4 safe)."""

    def test_generate_and_redeem(self):
        nonce = SSOService.generate_exchange_code("u1", "tok-abc")
        assert len(nonce) >= 32
        user_id, token = SSOService.redeem_exchange_code(nonce)
        assert user_id == "u1"
        assert token == "tok-abc"

    def test_single_use(self):
        nonce = SSOService.generate_exchange_code("u1", "tok")
        SSOService.redeem_exchange_code(nonce)
        with pytest.raises(ValueError, match="Invalid"):
            SSOService.redeem_exchange_code(nonce)

    def test_invalid_code(self):
        with pytest.raises(ValueError, match="Invalid"):
            SSOService.redeem_exchange_code("nonexistent")

    def test_expiration(self, monkeypatch):
        real_time = time.time
        nonce = SSOService.generate_exchange_code("u1", "tok")
        # Fast-forward past TTL by patching time.time
        monkeypatch.setattr(time, "time", lambda: real_time() + 120)
        with pytest.raises(ValueError, match="expired"):
            SSOService.redeem_exchange_code(nonce)


class TestUpsertUser:
    """Tests for SSO user upsert logic (link existing, create new)."""

    @pytest.mark.asyncio
    async def test_create_new_user(self, async_session, test_org):
        sso = SSOService(async_session)
        user = await sso.upsert_user(
            email="newuser@example.com",
            provider="google",
            provider_id="g123",
            full_name="New User",
            org_id=test_org.id,
        )
        assert user.email == "newuser@example.com"
        assert user.sso_provider == "google"
        assert user.sso_subject == "g123"
        assert user.role == "consumer"

    @pytest.mark.asyncio
    async def test_link_existing_by_email(self, async_session, test_org):
        """If user already exists with same email, link SSO fields."""
        from app.models.user import User

        existing = User(
            email="existing@example.com",
            hashed_password="$hash$",
            full_name=b"Existing User",
            role="consumer",
            org_id=test_org.id,
        )
        async_session.add(existing)
        await async_session.flush()

        sso = SSOService(async_session)
        user = await sso.upsert_user(
            email="existing@example.com",
            provider="microsoft",
            provider_id="ms456",
            org_id=test_org.id,
        )
        assert user.id == existing.id
        assert user.sso_provider == "microsoft"
        assert user.sso_subject == "ms456"

    @pytest.mark.asyncio
    async def test_no_duplicate_on_second_upsert(self, async_session, test_org):
        """Calling upsert again with same provider+subject returns same user."""
        sso = SSOService(async_session)
        user1 = await sso.upsert_user(
            email="dup@example.com",
            provider="google",
            provider_id="g789",
            org_id=test_org.id,
        )
        user2 = await sso.upsert_user(
            email="dup@example.com",
            provider="google",
            provider_id="g789",
            org_id=test_org.id,
        )
        assert user1.id == user2.id

    @pytest.mark.asyncio
    async def test_org_required_for_new_user(self, async_session):
        """Creating a new SSO user without org_id raises ValueError."""
        sso = SSOService(async_session)
        with pytest.raises(ValueError, match="org_id required"):
            await sso.upsert_user(
                email="noorg@example.com",
                provider="google",
                provider_id="g000",
            )
