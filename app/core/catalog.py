from __future__ import annotations

import os

# Vote threshold: when a book title gets this many upvotes, auto-create & learn
VOTE_THRESHOLD = int(os.getenv("VOTE_THRESHOLD", "3"))

# Scheduled discovery interval in seconds (default 6 hours, 0 to disable)
DISCOVERY_INTERVAL = int(os.getenv("DISCOVERY_INTERVAL", str(6 * 3600)))

# Max books to discover per scheduled run
DISCOVERY_BATCH_SIZE = int(os.getenv("DISCOVERY_BATCH_SIZE", "5"))

# ─── Topic tags for interest-driven discovery ───
TOPIC_TAGS = [
    "Psychology", "Philosophy", "Economics", "Physics",
    "Computer Science", "Biology", "History", "Mathematics",
    "Business & Strategy", "Neuroscience", "Literature",
    "Political Science", "Sociology", "Art & Design", "Self-Development",
]

# Number of books to discover per topic
TOPIC_DISCOVER_COUNT = int(os.getenv("TOPIC_DISCOVER_COUNT", "5"))
