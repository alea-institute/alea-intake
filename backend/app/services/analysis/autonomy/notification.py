"""Notification dispatch for autonomy approval requests.

Primary channel: WebSocket via IntakeConnectionManager.send_to_session.
Email: stub only -- logs warning if enabled but SMTP not configured.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


class NotificationService:
    """Dispatches approval_pending notifications to connected clients."""

    def __init__(
        self,
        ws_manager: Any | None = None,
        smtp_config: dict | None = None,
    ) -> None:
        self._ws_manager = ws_manager
        self._smtp_config = smtp_config

    async def notify(
        self,
        request: Any,
        session_id: int,
        notify_email: bool = False,
    ) -> None:
        """Send approval_pending event via WebSocket (and optionally email).

        Args:
            request: ApprovalRequestSchema or object with id, run_id, stage_name,
                     safety_triggered attributes.
            session_id: Intake session to notify.
            notify_email: Whether to attempt email notification.
        """
        if self._ws_manager is not None:
            message = {
                "type": "approval_pending",
                "request_id": request.id,
                "run_id": request.run_id,
                "stage_name": request.stage_name,
                "safety_triggered": getattr(request, "safety_triggered", False),
            }
            await self._ws_manager.send_to_session(session_id, message)

        if notify_email:
            if self._smtp_config is None:
                logger.warning(
                    "Email notification requested but SMTP not configured. "
                    "Skipping email for approval request %s.",
                    getattr(request, "id", "unknown"),
                )
            else:
                # Stub: email sending not implemented. Per D-07, WebSocket is
                # the primary notification channel. Email is secondary and
                # will be implemented when aiosmtplib integration is needed.
                logger.info(
                    "Email notification stub: would send approval_pending "
                    "for request %s.",
                    getattr(request, "id", "unknown"),
                )
