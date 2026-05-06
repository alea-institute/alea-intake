"""Tests for the practice-area HTTP surface (plan 13-02).

Covers:
  - GET /api/practice-areas returns the registered areas, sorted by display_name
  - POST /api/v1/intake/ with practice_area_id="personal_injury" succeeds and
    echoes the id on the response
  - POST /api/v1/intake/ with an unknown practice_area_id returns 400
  - POST /api/v1/intake/ with no practice_area_id (or empty body) still works
    -- backwards-compatibility regression guard
  - POST /api/v1/intake/{intake_id}/session honours practice_area_id too
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient


# Re-use the auth helper pattern from test_intake_chat.py
async def _setup_authed_user(async_client: AsyncClient, email: str) -> str:
    """Register a user, login, grant AI consent, return the access token."""
    headers = {"X-Tenant-Slug": "test-legal-aid"}

    await async_client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": "Test1234!Strong",
            "full_name": "Practice Area Tester",
        },
        headers=headers,
    )
    login_resp = await async_client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "Test1234!Strong"},
        headers=headers,
    )
    token = login_resp.json()["access_token"]
    auth_headers = {"Authorization": f"Bearer {token}", **headers}

    await async_client.post(
        "/api/v1/consent/grant",
        json={
            "consent_version": "1.0",
            "consent_items": {"ai_processing": True, "data_sharing": False},
        },
        headers=auth_headers,
    )

    return token


def _seed_registry_on_app(app, *areas):
    """Attach a fresh PracticeAreaRegistry containing ``areas`` to ``app.state``.

    The async_client fixture doesn't run the production lifespan (which would
    load configs from disk), so we set this up explicitly. Tests that don't
    care about the registry contents can pass the standard PI seed config.
    """
    from app.services.intake.practice_areas import (
        PracticeArea,
        PracticeAreaRegistry,
    )

    registry = PracticeAreaRegistry()
    for area in areas:
        registry.register(area)
    app.state.practice_areas = registry
    return registry


def _pi_area():
    from app.services.intake.practice_areas import PracticeArea

    return PracticeArea(
        id="personal_injury",
        display_name="Personal Injury",
        welcome_message_consumer="Tell me about your accident.",
        welcome_message_professional="Capture the incident facts.",
        system_prompt="You are a personal injury intake assistant.",
        key_topics=["Incident facts", "Injuries"],
        disclaimer=None,
    )


def _family_area():
    from app.services.intake.practice_areas import PracticeArea

    return PracticeArea(
        id="family_law",
        display_name="Family Law",
        welcome_message_consumer="Tell me about your family situation.",
        welcome_message_professional="Family law intake.",
        system_prompt="You are a family law intake assistant.",
        key_topics=["Parties", "Children"],
        disclaimer="Sensitive matters: please call 988 if in crisis.",
    )


# ---------------------------------------------------------------------------
# GET /api/practice-areas
# ---------------------------------------------------------------------------


class TestPracticeAreasListEndpoint:
    @pytest.mark.asyncio
    async def test_list_returns_registered_areas_sorted(self, async_client: AsyncClient):
        from app.main import app as fastapi_app

        # Seed two areas in non-alphabetical order; expect alphabetical by display_name
        _seed_registry_on_app(fastapi_app, _pi_area(), _family_area())

        resp = await async_client.get("/api/practice-areas")
        assert resp.status_code == 200
        data = resp.json()
        assert "practice_areas" in data
        ids = [a["id"] for a in data["practice_areas"]]
        # Family Law < Personal Injury alphabetically
        assert ids == ["family_law", "personal_injury"]

        # Each entry has exactly the documented public fields
        for entry in data["practice_areas"]:
            assert set(entry.keys()) == {"id", "display_name", "disclaimer"}

        # Disclaimer can be None or a string
        family = next(a for a in data["practice_areas"] if a["id"] == "family_law")
        assert family["disclaimer"] == "Sensitive matters: please call 988 if in crisis."
        pi = next(a for a in data["practice_areas"] if a["id"] == "personal_injury")
        assert pi["disclaimer"] is None
        assert pi["display_name"] == "Personal Injury"

    @pytest.mark.asyncio
    async def test_list_no_auth_required(self, async_client: AsyncClient):
        from app.main import app as fastapi_app

        _seed_registry_on_app(fastapi_app, _pi_area())

        # No Authorization header -- should still succeed
        resp = await async_client.get("/api/practice-areas")
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_list_empty_when_registry_missing(self, async_client: AsyncClient):
        from app.main import app as fastapi_app

        # Remove the registry entirely
        if hasattr(fastapi_app.state, "practice_areas"):
            delattr(fastapi_app.state, "practice_areas")

        resp = await async_client.get("/api/practice-areas")
        assert resp.status_code == 200
        assert resp.json() == {"practice_areas": []}


# ---------------------------------------------------------------------------
# POST /api/v1/intake/ with practice_area_id
# ---------------------------------------------------------------------------


class TestSessionCreationWithPracticeArea:
    @pytest.mark.asyncio
    async def test_create_intake_with_valid_practice_area(self, async_client: AsyncClient):
        from app.main import app as fastapi_app

        _seed_registry_on_app(fastapi_app, _pi_area())

        token = await _setup_authed_user(
            async_client, "intake-with-pa@example.com"
        )
        headers = {
            "Authorization": f"Bearer {token}",
            "X-Tenant-Slug": "test-legal-aid",
        }

        resp = await async_client.post(
            "/api/v1/intake/",
            headers=headers,
            json={"practice_area_id": "personal_injury"},
        )
        assert resp.status_code == 201, resp.text
        data = resp.json()
        assert data["practice_area_id"] == "personal_injury"
        assert "session_id" in data

    @pytest.mark.asyncio
    async def test_create_intake_with_unknown_practice_area_returns_400(
        self, async_client: AsyncClient
    ):
        from app.main import app as fastapi_app

        _seed_registry_on_app(fastapi_app, _pi_area())

        token = await _setup_authed_user(
            async_client, "intake-bad-pa@example.com"
        )
        headers = {
            "Authorization": f"Bearer {token}",
            "X-Tenant-Slug": "test-legal-aid",
        }

        resp = await async_client.post(
            "/api/v1/intake/",
            headers=headers,
            json={"practice_area_id": "not_a_thing"},
        )
        assert resp.status_code == 400
        body = resp.json()
        assert "not_a_thing" in body.get("detail", "")
        assert body.get("practice_area_id") == "not_a_thing"

    @pytest.mark.asyncio
    async def test_create_intake_without_practice_area_still_works(
        self, async_client: AsyncClient
    ):
        """Backwards-compatibility regression guard: no body, no practice_area_id."""
        from app.main import app as fastapi_app

        _seed_registry_on_app(fastapi_app, _pi_area())

        token = await _setup_authed_user(
            async_client, "intake-no-pa@example.com"
        )
        headers = {
            "Authorization": f"Bearer {token}",
            "X-Tenant-Slug": "test-legal-aid",
        }

        # No JSON body at all
        resp = await async_client.post("/api/v1/intake/", headers=headers)
        assert resp.status_code == 201, resp.text
        data = resp.json()
        assert data["practice_area_id"] is None

        # Empty JSON body
        resp = await async_client.post(
            "/api/v1/intake/", headers=headers, json={}
        )
        assert resp.status_code == 201, resp.text
        assert resp.json()["practice_area_id"] is None

        # Explicit null
        resp = await async_client.post(
            "/api/v1/intake/",
            headers=headers,
            json={"practice_area_id": None},
        )
        assert resp.status_code == 201, resp.text
        assert resp.json()["practice_area_id"] is None

    @pytest.mark.asyncio
    async def test_create_session_endpoint_with_practice_area(
        self, async_client: AsyncClient
    ):
        """POST /api/v1/intake/{intake_id}/session also accepts practice_area_id."""
        from app.main import app as fastapi_app

        _seed_registry_on_app(fastapi_app, _pi_area())

        token = await _setup_authed_user(
            async_client, "intake-newsess-pa@example.com"
        )
        headers = {
            "Authorization": f"Bearer {token}",
            "X-Tenant-Slug": "test-legal-aid",
        }

        # First create an intake (no practice area)
        create_resp = await async_client.post("/api/v1/intake/", headers=headers)
        assert create_resp.status_code == 201
        intake_id = create_resp.json()["id"]

        # Now spin up a new session bound to PI
        sess_resp = await async_client.post(
            f"/api/v1/intake/{intake_id}/session",
            headers=headers,
            json={"practice_area_id": "personal_injury"},
        )
        assert sess_resp.status_code == 201, sess_resp.text
        assert sess_resp.json()["practice_area_id"] == "personal_injury"

        # And one without one keeps the old behaviour
        sess_resp_2 = await async_client.post(
            f"/api/v1/intake/{intake_id}/session",
            headers=headers,
        )
        assert sess_resp_2.status_code == 201
        assert sess_resp_2.json()["practice_area_id"] is None

        # Bogus id on /session also 400s
        bad = await async_client.post(
            f"/api/v1/intake/{intake_id}/session",
            headers=headers,
            json={"practice_area_id": "junk_id"},
        )
        assert bad.status_code == 400
