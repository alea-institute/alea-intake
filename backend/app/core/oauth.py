"""Authlib OAuth client registry for Google + Microsoft OIDC providers.

Uses server_metadata_url for auto-discovery of authorization, token,
and JWKS endpoints. Providers are registered only when client credentials
are configured (empty credentials = provider disabled).
"""

from authlib.integrations.starlette_client import OAuth

from app.config import get_settings

settings = get_settings()
oauth = OAuth()

if settings.google_client_id:
    oauth.register(
        name="google",
        client_id=settings.google_client_id,
        client_secret=settings.google_client_secret,
        server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
        client_kwargs={"scope": "openid email profile", "prompt": "select_account"},
    )

if settings.microsoft_client_id:
    oauth.register(
        name="microsoft",
        client_id=settings.microsoft_client_id,
        client_secret=settings.microsoft_client_secret,
        server_metadata_url="https://login.microsoftonline.com/common/v2.0/.well-known/openid-configuration",
        client_kwargs={"scope": "openid email profile User.Read"},
    )
