"""Autonomy spectrum engine for configurable human-in-the-loop analysis.

Provides AutonomyConfig (per-org checkpoint settings), AutonomyInterceptor
(wraps stage execution), ApprovalQueue (asyncio.Event pause/resume), and
supporting notification/audit services.
"""
