from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from decimal import Decimal

from django.db import transaction
from django.db.models import Avg, Count
from django.utils import timezone

from feedback.models import Feedback
from intelligence.models import (
    IntelligenceConfiguration,
    IntelligenceInsight,
    IntelligenceReport,
    IntelligenceReportVersion,
)
from intelligence.selectors.feedback_data_selector import (
    facility_breakdown,
    feedback_queryset_for_scope,
    rating_breakdown,
    structured_choice_breakdown,
    text_records,
)
from intelligence.services.recommendation_service import build_recommendations
from intelligence.services.topic_extraction_service import extract_topics
from intelligence.services.trend_detection_service import (
    classify_sample_size,
    classify_direction,
    classify_severity,
    confidence_score,
    percent_change,
)


@dataclass
class ReportPeriods:
    period_start: object
    period_end: object
    comparison_start: object | None
    comparison_end: object | None


def default_periods(report_type: str) -> ReportPeriods:
    today = timezone.localdate()
    if report_type == IntelligenceReport.ReportType.WEEKLY:
        period_end = today
        period_start = today - timedelta(days=6)
        comparison_end = period_start - timedelta(days=1)
        comparison_start = comparison_end - timedelta(days=6)
    elif report_type == IntelligenceReport.ReportType.MONTHLY:
        period_start = today.replace(day=1)
        period_end = today
        comparison_end = period_start - timedelta(days=1)
        comparison_start = comparison_end.replace(day=1)
    else:
        period_start = today - timedelta(days=29)
        period_end = today
        comparison_start = period_start - timedelta(days=30)
        comparison_end = period_start - timedelta(days=1)
    return ReportPeriods(period_start, period_end, comparison_start, comparison_end)


def generate_intelligence_report(
    *,
    user,
    report_type: str,
    facility=None,
    collection_session=None,
    submission_source: str = "",
    period_start=None,
    period_end=None,
    report: IntelligenceReport | None = None,
):
    config = IntelligenceConfiguration.load()
    periods = default_periods(report_type)
    period_start = period_start or periods.period_start
    period_end = period_end or periods.period_end
    comparison_start = periods.comparison_start
    comparison_end = periods.comparison_end
    if report_type == IntelligenceReport.ReportType.FACILITY and facility is None:
        raise ValueError("Facility report generation requires a facility.")

    current_qs = feedback_queryset_for_scope(
        user,
        facility=facility,
        period_start=period_start,
        period_end=period_end,
        collection_session=collection_session,
        submission_source=submission_source,
    )
    comparison_qs = feedback_queryset_for_scope(
        user,
        facility=facility,
        period_start=comparison_start,
        period_end=comparison_end,
        collection_session=collection_session,
        submission_source=submission_source,
    ) if comparison_start and comparison_end else current_qs.none()

    current_count = current_qs.count()
    comparison_count = comparison_qs.count()
    current_avg_rating = current_qs.aggregate(value=Avg("rating_responses__rating"))["value"] or 0
    comparison_avg_rating = comparison_qs.aggregate(value=Avg("rating_responses__rating"))["value"] or 0
    current_facility_count = current_qs.values("facility_id").distinct().count()

    current_rating_breakdown = rating_breakdown(current_qs)
    comparison_rating_lookup = {
        row["category"]: row for row in rating_breakdown(comparison_qs)
    }
    text_topics = extract_topics(text_records(current_qs), limit=8)

    structured_counts = {
        "received_service": structured_choice_breakdown(current_qs, "received_service"),
        "change": structured_choice_breakdown(current_qs, "change"),
        "medicines": structured_choice_breakdown(current_qs, "medicines"),
    }
    facility_stats = facility_breakdown(current_qs)[:10]

    insights_payload = []
    volume_pct = percent_change(current_count, comparison_count)
    insights_payload.append(
        build_insight_payload(
            insight_type=IntelligenceInsight.InsightType.METRIC,
            title="Submission volume overview",
            metric_name="Submission volume",
            current_value=current_count,
            comparison_value=comparison_count,
            sample_size=current_count,
            direction=classify_direction(current_count, comparison_count, bigger_is_better=True, config=config),
            evidence={
                "current_period": str(period_start) + " to " + str(period_end),
                "comparison_period": str(comparison_start) + " to " + str(comparison_end) if comparison_start else "",
                "facilities_involved": current_facility_count,
            },
            change_value=volume_pct,
            config=config,
            summary=f"{current_count} submissions captured in the reporting period.",
        )
    )
    insights_payload.append(
        build_insight_payload(
            insight_type=IntelligenceInsight.InsightType.TREND,
            title="Average rating movement",
            metric_name="Average rating",
            current_value=round(current_avg_rating, 2),
            comparison_value=round(comparison_avg_rating, 2),
            sample_size=current_count,
            direction=classify_direction(current_avg_rating, comparison_avg_rating, bigger_is_better=True, config=config),
            evidence={
                "rating_responses": current_qs.aggregate(total=Count("rating_responses"))["total"] or 0,
                "period_start": str(period_start),
                "period_end": str(period_end),
            },
            change_value=percent_change(current_avg_rating, comparison_avg_rating),
            config=config,
            summary=f"Average rating is {round(current_avg_rating, 2)} for the current period.",
        )
    )

    for row in current_rating_breakdown:
        comparison_row = comparison_rating_lookup.get(row["category"], {})
        avg_rating = row["average_rating"] or 0
        comparison_avg = comparison_row.get("average_rating") or 0
        direction = classify_direction(avg_rating, comparison_avg, bigger_is_better=True, config=config)
        insights_payload.append(
            build_insight_payload(
                insight_type=(
                    IntelligenceInsight.InsightType.FACILITY_ALERT
                    if avg_rating <= config.low_rating_threshold
                    else IntelligenceInsight.InsightType.TREND
                ),
                title=f"{row['category']} performance",
                metric_name=row["category"],
                current_value=round(avg_rating, 2),
                comparison_value=round(comparison_avg, 2),
                sample_size=row["total"],
                direction=direction,
                evidence={
                    "responses": row["total"],
                    "low_ratings": row["low_ratings"],
                    "comparison_average": round(comparison_avg, 2),
                },
                change_value=percent_change(avg_rating, comparison_avg),
                config=config,
                summary=f"{row['category']} averaged {round(avg_rating, 2)} from {row['total']} responses.",
            )
        )

    for topic in text_topics[:5]:
        insights_payload.append(
            {
                "insight_type": IntelligenceInsight.InsightType.TOPIC,
                "title": f"Topic emerging in comments: {topic['topic']}",
                "summary": f"Free-text responses repeatedly mention '{topic['topic']}'.",
                "severity": IntelligenceInsight.Severity.INFORMATIONAL,
                "direction": IntelligenceInsight.Direction.STABLE,
                "confidence_level": classify_sample_size(topic["count"], config),
                "confidence_score": Decimal("25") if topic["count"] >= 2 else Decimal("10"),
                "metric_name": "Free-text topic",
                "current_value": topic["count"],
                "comparison_value": None,
                "absolute_change": None,
                "percentage_change": None,
                "sample_size": topic["count"],
                "evidence": topic,
            }
        )

    recommendations = build_recommendations(insights_payload)
    executive_summary = build_executive_summary(
        report_type=report_type,
        current_count=current_count,
        comparison_count=comparison_count,
        current_avg_rating=current_avg_rating,
        insights=insights_payload,
    )

    metadata = {
        "structured_counts": structured_counts,
        "facility_stats": facility_stats,
        "topics": text_topics,
        "generated_on": timezone.now().isoformat(),
    }

    with transaction.atomic():
        if report is None:
            report = IntelligenceReport.objects.create(
                report_type=report_type,
                title=build_report_title(report_type, facility, period_start, period_end),
                facility=facility,
                collection_session=collection_session,
                submission_source=submission_source,
                period_start=period_start,
                period_end=period_end,
                comparison_start=comparison_start,
                comparison_end=comparison_end,
                generated_by=user,
                executive_summary=executive_summary,
                generation_metadata=metadata,
            )
            version_number = 1
        else:
            if report.status == IntelligenceReport.Status.APPROVED:
                raise ValueError("Approved reports cannot be regenerated.")
            report.version += 1
            report.generated_at = timezone.now()
            report.generated_by = user
            report.executive_summary = executive_summary
            report.generation_metadata = metadata
            report.save(update_fields=["version", "generated_at", "generated_by", "executive_summary", "generation_metadata", "updated_at"])
            version_number = report.version

        version = IntelligenceReportVersion.objects.create(
            report=report,
            version=version_number,
            executive_summary=executive_summary,
            recommendations=normalize_for_json(recommendations),
            supporting_statistics=normalize_for_json(metadata),
            insight_snapshot=normalize_for_json(insights_payload),
            topic_snapshot=normalize_for_json(text_topics),
            generation_settings={
                "report_type": report_type,
                "facility_id": facility.pk if facility else None,
                "collection_session_id": collection_session.pk if collection_session else None,
                "submission_source": submission_source,
                "period_start": str(period_start),
                "period_end": str(period_end),
            },
            generated_by=user,
        )

        IntelligenceInsight.objects.bulk_create(
            [
                IntelligenceInsight(
                    report=report,
                    report_version=version,
                    facility=facility,
                    insight_type=payload["insight_type"],
                    title=payload["title"],
                    summary=payload["summary"],
                    severity=payload["severity"],
                    direction=payload["direction"],
                    confidence_level=payload["confidence_level"],
                    confidence_score=payload["confidence_score"],
                    metric_name=payload["metric_name"],
                    current_value=payload["current_value"],
                    comparison_value=payload["comparison_value"],
                    absolute_change=payload["absolute_change"],
                    percentage_change=payload["percentage_change"],
                    sample_size=payload["sample_size"],
                    evidence=payload["evidence"],
                    display_order=index,
                )
                for index, payload in enumerate(insights_payload, start=1)
            ]
        )

    return report


def normalize_for_json(value):
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, dict):
        return {key: normalize_for_json(item) for key, item in value.items()}
    if isinstance(value, list):
        return [normalize_for_json(item) for item in value]
    return value


def build_executive_summary(*, report_type, current_count, comparison_count, current_avg_rating, insights):
    trend_count = len([item for item in insights if item["direction"] == IntelligenceInsight.Direction.DECLINING])
    positive_count = len([item for item in insights if item["direction"] == IntelligenceInsight.Direction.IMPROVING])
    return (
        f"{report_type.title()} intelligence report covering {current_count} submissions. "
        f"Comparison period recorded {comparison_count} submissions. "
        f"Average rating for the current period is {round(current_avg_rating, 2)}. "
        f"{trend_count} declining signals and {positive_count} improving signals were detected."
    )


def build_report_title(report_type, facility, period_start, period_end):
    report_name = dict(IntelligenceReport.ReportType.choices).get(report_type, report_type.title())
    if facility:
        return f"{report_name} intelligence for {facility.name} ({period_start:%d %b %Y} - {period_end:%d %b %Y})"
    return f"{report_name} intelligence ({period_start:%d %b %Y} - {period_end:%d %b %Y})"


def build_insight_payload(
    *,
    insight_type,
    title,
    metric_name,
    current_value,
    comparison_value,
    sample_size,
    direction,
    evidence,
    change_value,
    config,
    summary,
):
    absolute_change = None
    if current_value is not None and comparison_value is not None:
        absolute_change = Decimal(str(current_value)) - Decimal(str(comparison_value))
    conf_level = classify_sample_size(sample_size, config)
    return {
        "insight_type": insight_type,
        "title": title,
        "summary": summary,
        "severity": classify_severity(direction, sample_size, config),
        "direction": direction,
        "confidence_level": conf_level,
        "confidence_score": confidence_score(sample_size, evidence.get("facilities_involved", 1), change_value or 0, config),
        "metric_name": metric_name,
        "current_value": current_value,
        "comparison_value": comparison_value,
        "absolute_change": absolute_change,
        "percentage_change": change_value,
        "sample_size": sample_size,
        "evidence": evidence,
    }
