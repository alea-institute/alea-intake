"""Smart OWL cache with ETag-based freshness check and one-version rollback.

Manages the FOLIO OWL file cache, providing:
- ETag-based HTTP conditional freshness checks (HEAD request per startup)
- XML validation before overwriting the cache
- Atomic write (via .tmp rename) with one-version rollback via .previous
- SHA-256 content hash for version identification
"""

from __future__ import annotations

import hashlib
import json
import logging
from datetime import datetime, timezone
from pathlib import Path

import httpx
from lxml import etree

from app.config import get_settings

logger = logging.getLogger(__name__)

_OWL_URL_TEMPLATE = (
    "https://raw.githubusercontent.com/alea-institute/folio/refs/heads/{branch}/FOLIO.owl"
)
_REQUEST_TIMEOUT = 30.0


def _get_paths(cache_dir: Path | None = None) -> tuple[Path, Path, Path, Path]:
    """Return (cache_dir, owl_file, previous_file, meta_file) paths."""
    if cache_dir is None:
        settings = get_settings()
        cache_dir = Path(settings.folio_cache_dir)
    owl_file = cache_dir / "folio.owl"
    previous_file = cache_dir / "folio.owl.previous"
    meta_file = cache_dir / "folio.meta.json"
    return cache_dir, owl_file, previous_file, meta_file


def _load_metadata(meta_file: Path) -> dict:
    """Load metadata JSON, returning empty dict if missing or corrupt."""
    if not meta_file.exists():
        return {}
    try:
        return json.loads(meta_file.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def _save_metadata(meta_file: Path, data: dict) -> None:
    """Write metadata JSON atomically."""
    meta_file.parent.mkdir(parents=True, exist_ok=True)
    tmp = meta_file.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(data, indent=2), encoding="utf-8")
    tmp.rename(meta_file)


def ensure_owl_fresh(
    branch: str | None = None,
    cache_dir: Path | None = None,
) -> bool:
    """Check if the cached FOLIO OWL is up to date; download if stale.

    Uses HTTP conditional requests (ETag / If-None-Match) to avoid
    re-downloading when nothing has changed.

    Args:
        branch: GitHub branch to fetch from. Defaults to settings.folio_owl_branch.
        cache_dir: Override cache directory. Defaults to settings.folio_cache_dir.

    Returns:
        True if a new version was downloaded, False if already up to date.
    """
    if branch is None:
        settings = get_settings()
        branch = settings.folio_owl_branch

    cache_dir_path, owl_file, previous_file, meta_file = _get_paths(cache_dir)
    cache_dir_path.mkdir(parents=True, exist_ok=True)

    meta = _load_metadata(meta_file)
    stored_etag = meta.get("etag")

    owl_url = _OWL_URL_TEMPLATE.format(branch=branch)

    # Step 1: HEAD request with conditional header
    headers: dict[str, str] = {}
    if stored_etag and owl_file.exists():
        headers["If-None-Match"] = stored_etag

    try:
        with httpx.Client(timeout=_REQUEST_TIMEOUT, follow_redirects=True) as client:
            head_resp = client.head(owl_url, headers=headers)
    except httpx.HTTPError as exc:
        logger.warning("OWL freshness check failed (network error): %s", exc)
        return False

    if head_resp.status_code == 304:
        logger.info("FOLIO OWL is up to date (304 Not Modified)")
        meta["last_checked"] = datetime.now(timezone.utc).isoformat()
        _save_metadata(meta_file, meta)
        return False

    if head_resp.status_code != 200:
        logger.warning("OWL freshness HEAD returned unexpected status %d", head_resp.status_code)
        return False

    new_etag = head_resp.headers.get("etag", "").strip('"')

    # Step 2: Download the full OWL
    try:
        with httpx.Client(timeout=_REQUEST_TIMEOUT, follow_redirects=True) as client:
            get_resp = client.get(owl_url)
            get_resp.raise_for_status()
    except httpx.HTTPError as exc:
        logger.warning("OWL download failed: %s", exc)
        return False

    content = get_resp.content

    # Step 3: Validate XML
    try:
        etree.fromstring(content)
    except etree.XMLSyntaxError as exc:
        logger.warning("Downloaded OWL failed XML validation: %s", exc)
        return False

    # Step 4: Rotate and write atomically
    if owl_file.exists():
        # Keep one-version backup
        if previous_file.exists():
            previous_file.unlink()
        owl_file.rename(previous_file)

    tmp = owl_file.with_suffix(".owl.tmp")
    tmp.write_bytes(content)
    tmp.rename(owl_file)

    # Step 5: Update metadata
    _save_metadata(meta_file, {
        "etag": new_etag,
        "last_checked": datetime.now(timezone.utc).isoformat(),
        "owl_bytes": len(content),
    })

    logger.info("FOLIO OWL updated (etag: %s, %d bytes)", new_etag, len(content))
    return True


def get_owl_status(cache_dir: Path | None = None) -> dict:
    """Return cache status for the health endpoint.

    Returns dict with keys: cached, etag, last_checked, content_hash.
    """
    cache_dir_path, owl_file, previous_file, meta_file = _get_paths(cache_dir)
    meta = _load_metadata(meta_file)

    content_hash = None
    if owl_file.exists():
        content = owl_file.read_bytes()
        content_hash = hashlib.sha256(content).hexdigest()[:16]

    return {
        "cached": owl_file.exists(),
        "etag": meta.get("etag"),
        "last_checked": meta.get("last_checked"),
        "content_hash": content_hash,
    }


def rollback_owl(cache_dir: Path | None = None) -> bool:
    """Roll back to the previous OWL version.

    Returns True if rollback succeeded, False if no previous version available.
    """
    cache_dir_path, owl_file, previous_file, meta_file = _get_paths(cache_dir)

    if not previous_file.exists():
        return False

    if owl_file.exists():
        owl_file.unlink()

    previous_file.rename(owl_file)

    # Clear etag so next startup re-checks freshness
    meta = _load_metadata(meta_file)
    meta.pop("etag", None)
    meta["rolled_back_at"] = datetime.now(timezone.utc).isoformat()
    _save_metadata(meta_file, meta)

    logger.info("Rolled back to previous FOLIO OWL version")
    return True


def get_cache_path(cache_dir: Path | None = None) -> Path:
    """Return the OWL cache file path for FOLIO() constructor."""
    _, owl_file, _, _ = _get_paths(cache_dir)
    return owl_file
