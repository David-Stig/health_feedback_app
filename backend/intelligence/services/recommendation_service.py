from __future__ import annotations


def build_recommendations(insights):
    recommendations = []
    for insight in insights:
        if insight["direction"] == "declining":
            recommendations.append(
                {
                    "title": f"Review {insight['metric_name']}",
                    "detail": f"Investigate the decline in {insight['metric_name']} and verify staffing, supplies, and patient flow controls.",
                }
            )
        elif insight["direction"] == "improving":
            recommendations.append(
                {
                    "title": f"Protect gains in {insight['metric_name']}",
                    "detail": f"Document the practices behind the improvement in {insight['metric_name']} and assess whether they can be replicated elsewhere.",
                }
            )
    deduped = []
    seen = set()
    for recommendation in recommendations:
        key = recommendation["title"]
        if key in seen:
            continue
        seen.add(key)
        deduped.append(recommendation)
    return deduped
