"""Custom Prometheus metrics for ALEA Intake.

Domain-specific counters and histograms for intake operations,
LLM costs, screening triggers, and analysis stage durations.
"""

from prometheus_client import Counter, Histogram

INTAKE_COUNTER = Counter(
    "alea_intakes_total",
    "Total intakes started",
    ["org_slug", "mode"],
)

LLM_COST_HISTOGRAM = Histogram(
    "alea_llm_cost_dollars",
    "LLM API cost per call",
    ["provider", "model"],
)

SCREENING_TRIGGER_COUNTER = Counter(
    "alea_screening_triggers_total",
    "Screening protocol triggers",
    ["protocol_name", "trigger_type"],
)

ANALYSIS_STAGE_DURATION = Histogram(
    "alea_analysis_stage_seconds",
    "Analysis stage duration",
    ["stage_name"],
)
