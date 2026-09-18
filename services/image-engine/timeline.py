"""
timeline.py
===========
Chronological degradation progression engine for infrastructure inspections.

Analyzes time-series inspection records, calculates an overall degradation score (0.0 to 1.0),
and constructs plain-language summaries suitable for administrative oversight and audit reports.
"""

from __future__ import annotations

from datetime import datetime
from typing import List, Tuple
from models import CaptureRecord, DefectClass, Severity, SourceType, TimelineResponse


SEVERITY_WEIGHTS = {
    Severity.NONE: 0.0,
    Severity.LOW: 0.30,
    Severity.MEDIUM: 0.65,
    Severity.HIGH: 1.0,
}

DEFECT_WEIGHTS = {
    DefectClass.NO_VISIBLE_DEFECT: 0.0,
    DefectClass.SURFACE_DETERIORATION: 0.70,
    DefectClass.CRACK: 0.85,
    DefectClass.POTHOLE: 1.0,
}


def parse_date(date_str: str) -> datetime:
    """Parse common ISO date formats."""
    for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%Y/%m/%d", "%d/%m/%Y"):
        try:
            return datetime.strptime(date_str.strip(), fmt)
        except ValueError:
            continue
    # Fallback to current time if unparseable
    return datetime.now()


def compute_timeline_progression(
    project_id: str,
    captures: List[CaptureRecord],
) -> TimelineResponse:
    """
    Evaluate chronological sequence of inspection captures.
    Computes overall degradation score and plain-language summary.
    """
    if not captures:
        raise ValueError("At least one capture record is required to compute timeline.")

    # 1. Sort captures chronologically
    sorted_captures = sorted(captures, key=lambda c: parse_date(c.capture_date))
    n = len(sorted_captures)

    # 2. Compute timespan in months
    d_start = parse_date(sorted_captures[0].capture_date)
    d_end = parse_date(sorted_captures[-1].capture_date)
    delta_days = max(0, (d_end - d_start).days)
    timespan_months = round(delta_days / 30.4375, 1)

    # 3. Extract progression metrics
    first = sorted_captures[0]
    last = sorted_captures[-1]

    first_sev_val = SEVERITY_WEIGHTS.get(first.severity, 0.0)
    last_sev_val = SEVERITY_WEIGHTS.get(last.severity, 0.0)
    last_defect_weight = DEFECT_WEIGHTS.get(last.defect_class, 0.0)

    # Compute degradation score (0.0 to 1.0):
    # - 50% weighted on latest severity and defect class
    # - 30% weighted on severity trajectory / delta
    # - 20% weighted on mean historical severity
    avg_hist_sev = sum(SEVERITY_WEIGHTS.get(c.severity, 0.0) for c in sorted_captures) / n
    latest_component = last_sev_val * (0.6 + 0.4 * last_defect_weight)

    delta = last_sev_val - first_sev_val
    trend_component = max(0.0, delta)

    if n == 1:
        degradation_score = round(latest_component, 3)
    else:
        raw_score = (0.50 * latest_component) + (0.25 * avg_hist_sev) + (0.25 * (last_sev_val + trend_component) / 2.0)
        degradation_score = round(max(0.0, min(1.0, raw_score)), 3)

    # 4. Formulate plain-language progression summary
    if n == 1:
        if last.severity == Severity.NONE:
            summary = f"Single capture on {last.capture_date} showed no visible infrastructure defects."
        else:
            summary = (
                f"Single capture on {last.capture_date} identified {last.defect_class.value} "
                f"at {last.severity.value} severity."
            )
    else:
        time_str = f"{timespan_months} months" if timespan_months != 1.0 else "1 month"
        if delta > 0.05:
            summary = (
                f"Defect severity increased from {first.severity.value} to {last.severity.value} "
                f"over {n} captures spanning {time_str}."
            )
        elif delta < -0.05:
            summary = (
                f"Defect severity decreased from {first.severity.value} to {last.severity.value} "
                f"following intervention over {n} captures spanning {time_str}."
            )
        else:
            if last.severity == Severity.NONE:
                summary = (
                    f"Asset remained in sound condition with no visible defects "
                    f"across {n} captures spanning {time_str}."
                )
            else:
                summary = (
                    f"Defect severity remained consistent at {last.severity.value} ({last.defect_class.value}) "
                    f"across {n} captures spanning {time_str}."
                )

    # 5. Collect source types
    source_types = list({c.source_type for c in sorted_captures})

    # Dominant defect class in history
    defect_counts = {}
    for c in sorted_captures:
        defect_counts[c.defect_class] = defect_counts.get(c.defect_class, 0) + 1
    dominant_defect = max(defect_counts.items(), key=lambda x: x[1])[0]

    return TimelineResponse(
        project_id=project_id,
        degradation_score=degradation_score,
        progression_summary=summary,
        total_captures=n,
        timespan_months=timespan_months,
        current_severity=last.severity,
        dominant_defect=dominant_defect,
        source_types_present=source_types,
    )
