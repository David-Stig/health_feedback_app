from __future__ import annotations

import re
from collections import Counter


STOP_WORDS = {
    "the", "and", "for", "with", "this", "that", "from", "have", "were", "been",
    "they", "them", "there", "their", "about", "into", "after", "before", "very",
    "more", "less", "your", "here", "what", "when", "where", "which", "would",
    "could", "should", "also", "some", "only", "just", "than", "then", "because",
    "facility", "health", "staff", "service", "services",
}


def normalize_text(value: str) -> list[str]:
    tokens = re.findall(r"[a-zA-Z]{3,}", value.lower())
    return [token for token in tokens if token not in STOP_WORDS]


def extract_topics(records, *, limit=10):
    counter = Counter()
    examples = {}
    for record in records:
        seen = set()
        for token in normalize_text(record["text"]):
            if token in seen:
                continue
            seen.add(token)
            counter[token] += 1
            examples.setdefault(token, record["text"])
    topics = []
    for token, count in counter.most_common(limit):
        topics.append(
            {
                "topic": token,
                "count": count,
                "example": examples.get(token, ""),
            }
        )
    return topics
