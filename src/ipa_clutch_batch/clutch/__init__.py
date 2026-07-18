"""Check and prepare the Clutch binary on a connected iOS device."""

from ipa_clutch_batch.clutch.clutch_manager import (
    REMOTE_CLUTCH_PATH,
    ClutchCheckResult,
    ensure_clutch_ready,
)
from ipa_clutch_batch.clutch.clutch_workflow import run_clutch_check

__all__ = [
    "REMOTE_CLUTCH_PATH",
    "ClutchCheckResult",
    "ensure_clutch_ready",
    "run_clutch_check",
]
