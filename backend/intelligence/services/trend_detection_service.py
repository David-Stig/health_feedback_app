from __future__ import annotations

from decimal import Decimal

from intelligence.models import IntelligenceInsight


def percent_change(current, comparison):
    if comparison in (None, 0):
        return None
    return ((Decimal(str(current)) - Decimal(str(comparison))) / Decimal(str(comparison))) * Decimal("100")


def classify_sample_size(sample_size, config):
    if sample_size <= config.minimum_sample_insufficient:
        return IntelligenceInsight.ConfidenceLevel.INSUFFICIENT
    if sample_size <= config.minimum_sample_low_volume:
        return IntelligenceInsight.ConfidenceLevel.LOW
    if sample_size >= config.minimum_sample_low_volume * 2:
        return IntelligenceInsight.ConfidenceLevel.HIGH
    return IntelligenceInsight.ConfidenceLevel.MEDIUM


def classify_direction(current, comparison, *, bigger_is_better, config):
    if comparison is None:
        return IntelligenceInsight.Direction.INSUFFICIENT_DATA
    delta_pct = percent_change(current, comparison)
    if delta_pct is None:
        return IntelligenceInsight.Direction.INSUFFICIENT_DATA
    threshold = Decimal(str(config.stability_change_threshold))
    if abs(delta_pct) <= threshold:
        return IntelligenceInsight.Direction.STABLE
    if bigger_is_better:
        return (
            IntelligenceInsight.Direction.IMPROVING
            if delta_pct > 0
            else IntelligenceInsight.Direction.DECLINING
        )
    return (
        IntelligenceInsight.Direction.IMPROVING
        if delta_pct < 0
        else IntelligenceInsight.Direction.DECLINING
    )


def classify_severity(direction, sample_size, config):
    if sample_size <= config.minimum_sample_insufficient:
        return IntelligenceInsight.Severity.INFORMATIONAL
    if direction == IntelligenceInsight.Direction.DECLINING:
        return IntelligenceInsight.Severity.HIGH
    if direction == IntelligenceInsight.Direction.IMPROVING:
        return IntelligenceInsight.Severity.LOW
    return IntelligenceInsight.Severity.INFORMATIONAL


def confidence_score(sample_size, facility_count, change_strength, config):
    score = Decimal("0")
    if sample_size > config.minimum_sample_insufficient:
        score += Decimal("25")
    if sample_size > config.minimum_sample_low_volume:
        score += Decimal("25")
    if facility_count >= config.minimum_cross_facility_count:
        score += Decimal("20")
    if abs(Decimal(str(change_strength or 0))) >= Decimal(str(config.significant_change_threshold)):
        score += Decimal("30")
    return min(score, Decimal("100"))
