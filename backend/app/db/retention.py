"""One owner for the complete guest graph and its upload directory.

Child IDs are captured before deletes. Files are removed before the database
transaction commits: a crash rolls back rows, so the next sweep can finish.
Showcase runs in a dedicated single-tenant database, never a tenant schema.
"""
import asyncio
import errno
import logging
import shutil
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path

from sqlalchemy import delete, select, or_, update
from sqlalchemy.ext.asyncio import AsyncSession

from app import config
from app.db.engine import get_engine
from app.db.base import TenantBase
from app.models import Intake, User
import app.models.audio  # register models not re-exported by app.models
import app.models.document  # noqa: F401 -- register model metadata

logger = logging.getLogger(__name__)
# Requests currently doing work must not expire during a long LLM response.
_active: dict[int, int] = {}


@asynccontextmanager
async def guest_activity(user_id):
    _active[user_id] = _active.get(user_id, 0) + 1
    try:
        yield
    finally:
        _active[user_id] -= 1
        if not _active[user_id]:
            del _active[user_id]


async def touch_guest(conn_or_session, user_id):
    result = await conn_or_session.execute(
        update(User).where(User.id == user_id).values(updated_at=datetime.now(timezone.utc)))
    return result.rowcount


def _aware(dt):
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt


async def _delete_guest_identity(session, user_id, *, include_audit=False):
    names = ('consent_records', 'refresh_tokens', 'audit_log') if include_audit else ('consent_records', 'refresh_tokens')
    for name in names:
        table = TenantBase.metadata.tables['tenant.' + name]
        column = table.c.actor_id if name == 'audit_log' else table.c.user_id
        await session.execute(delete(table).where(column == user_id))
    await session.execute(delete(User).where(User.id == user_id))


async def purge_intake(session: AsyncSession, intake_id: int):
    """Delete an intake graph; the caller owns commit/rollback."""
    intake = await session.get(Intake, intake_id)
    if intake is None:
        return
    user_id = intake.created_by_user_id
    tables = {t.name: t for t in TenantBase.metadata.tables.values()}
    ids = {'intake_id': [intake_id]}
    # Explicit traversal documents every non-intake child edge.
    edges = [('intake_sessions', 'intake_id', 'session_id'),
             ('messages', 'session_id', 'message_id'),
             ('extracted_facts', 'intake_id', 'fact_id'),
             ('analysis_runs', 'intake_id', 'run_id'),
             ('analysis_iterations', 'run_id', 'iteration_id'),
             ('analysis_claims', 'run_id', 'claim_id'),
             ('claim_elements', 'claim_id', 'element_id'),
             ('analysis_gaps', 'run_id', 'gap_id'),
             ('uploaded_documents', 'intake_id', 'document_id'),
             ('audio_recordings', 'intake_id', 'recording_id'),
             ('authorities', 'intake_id', 'authority_id')]
    for name, parent, child in edges:
        table = tables[name]
        ids[child] = list((await session.execute(select(table.c.id).where(table.c[parent].in_(ids[parent])))).scalars())
    # All direct intake tables, then children, are included; org configuration,
    # knowledge-base content and screening protocol definitions are not session data.
    excluded = {'intakes', 'users', 'consent_records', 'refresh_tokens', 'kb_chunks'}
    selected = []
    for name, table in tables.items():
        if name in excluded:
            continue
        conditions = [table.c[key].in_(values) for key, values in ids.items() if key in table.c]
        if name == 'audit_log':
            conditions = [(table.c.resource_type == 'intake') & (table.c.resource_id == intake_id)]
            if user_id is not None:
                conditions.append(table.c.actor_id == user_id)
        if conditions:
            selected.append((table, or_(*conditions)))
    # There are no foreign keys between these graph tables. Delete leaves first
    # nevertheless, to preserve dependency order for future FK migrations.
    parent_names = [edge[0] for edge in edges]
    selected.sort(key=lambda item: parent_names.index(item[0].name) if item[0].name in parent_names else 999, reverse=True)
    for table, condition in selected:
        await session.execute(delete(table).where(condition))
    root = Path(config.get_settings().intake_upload_dir)
    # save_upload writes {root}/{org_slug}/{intake_id}/{uuid}.{ext}; remove
    # the directory even when an upload died before its row was committed.
    if root.exists():
        for path in root.glob(f'*/{intake_id}'):
            if path.exists():
                shutil.rmtree(path)
                try:
                    path.parent.rmdir()
                except OSError as exc:
                    if exc.errno not in (errno.ENOTEMPTY, errno.ENOENT):
                        raise
    await session.execute(delete(Intake).where(Intake.id == intake_id))
    # A guest can own multiple intakes. Keep its identity until the last is gone.
    remaining = (await session.execute(select(Intake.id).where(Intake.created_by_user_id == user_id))).first()
    user = await session.get(User, user_id) if user_id else None
    if remaining is None and user is not None and user.email is None and user.hashed_password is None:
        await _delete_guest_identity(session, user_id)


async def sweep_showcase_sessions():
    settings = config.get_settings()
    if not settings.showcase_mode:
        return
    cutoff = datetime.now(timezone.utc) - timedelta(seconds=settings.showcase_idle_ttl_seconds)
    async with get_engine().connect() as conn:
        conn = await conn.execution_options(schema_translate_map={'tenant': None, 'shared': None})
        async with AsyncSession(bind=conn, expire_on_commit=False) as session:
            guests = list((await session.execute(select(User.id).where(
                User.email.is_(None), User.hashed_password.is_(None), User.role == 'consumer',
                User.updated_at < cutoff))).scalars())
            for user_id in guests:
                if user_id in _active:
                    continue
                try:
                    guest = (await session.execute(select(User).where(User.id == user_id).with_for_update(skip_locked=True))).scalar_one_or_none()
                    if guest is None:
                        continue
                    last_active = _aware(guest.updated_at)
                    if last_active >= cutoff or user_id in _active:
                        continue
                    intakes = list((await session.execute(select(Intake).where(Intake.created_by_user_id == user_id))).scalars())
                    if any(_aware(i.updated_at) >= cutoff for i in intakes):
                        continue
                    for intake in intakes:
                        await purge_intake(session, intake.id)
                    if not intakes:
                        await _delete_guest_identity(session, user_id, include_audit=True)
                    await session.commit()
                except Exception:
                    await session.rollback()
                    logger.warning('Guest purge interrupted; next sweep will retry')


async def run_showcase_sweeper():
    while True:
        try:
            await sweep_showcase_sessions()
        except Exception:
            logger.warning('Guest sweep unavailable; retrying next interval')
        await asyncio.sleep(min(60, max(1, config.get_settings().showcase_idle_ttl_seconds / 2)))
