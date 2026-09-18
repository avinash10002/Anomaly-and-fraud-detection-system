"""
cleaner.py
==========
Text cleaning utilities for MPLADS WORK description field.

Rules & Expectations:
1. Strip leading work-code prefixes if present:
   e.g. "WS/MP559/2023-2024/92788 - Construction of community hall..."
        -> "Construction of community hall..."
2. Preserve the actual human-readable project description intact.
3. Clean up extra whitespaces, dashes, and residual formatting noise.
4. Fall back safely to raw text if stripping leaves nothing or if no prefix exists.
"""

from __future__ import annotations

import re
from typing import Optional

# Leading work code pattern:
# Covers formats like:
#   WS/MP559/2023-2024/92788 - ...
#   RD/MP100/2022-2023/12345: ...
#   WORK/MP01/2021-22/001 - ...
#   WS/RS12/2020-2021/4567 — ...
WORK_CODE_PREFIX_REGEX = re.compile(
    r"^\s*[A-Za-z0-9_\-]+(?:/[A-Za-z0-9_\-]+){2,}\s*[-–—:]\s*",
    re.IGNORECASE,
)

# Secondary pattern for simpler code prefixes like "WS/12345 - " or "MP559/92788 - "
SECONDARY_PREFIX_REGEX = re.compile(
    r"^\s*[A-Za-z0-9_]+/[A-Za-z0-9_\-]+\s*[-–—:]\s*",
    re.IGNORECASE,
)

# Generic numbered or tagged prefixes like "WORK CODE: 12345 - " or "#12345 - "
TAGGED_PREFIX_REGEX = re.compile(
    r"^\s*(?:work\s*code|proj(?:ect)?\s*id|work\s*id|code)\s*[:#\-]?\s*[A-Za-z0-9_\-/]+\s*[-–—:]\s*",
    re.IGNORECASE,
)


def clean_work_description(raw_work: Optional[str]) -> str:
    """
    Clean a raw MPLADS work description by removing administrative / tracking code prefixes
    while retaining the substantive project scope description.

    Examples:
        >>> clean_work_description("WS/MP559/2023-2024/92788 - Construction of Community Hall")
        'Construction of Community Hall'
        >>> clean_work_description("Construction of concrete road in Gram Panchayat")
        'Construction of concrete road in Gram Panchayat'
        >>> clean_work_description("")
        ''
    """
    if raw_work is None:
        return ""

    text = str(raw_work).strip()
    if not text:
        return ""

    # Try standard multi-segment work code pattern
    cleaned = WORK_CODE_PREFIX_REGEX.sub("", text).strip()

    # Try secondary prefix if unchanged and looks like a code prefix
    if cleaned == text:
        cleaned = SECONDARY_PREFIX_REGEX.sub("", text).strip()

    # Try tagged prefix
    if cleaned == text:
        cleaned = TAGGED_PREFIX_REGEX.sub("", text).strip()

    # Clean leading bullet points, dangling dashes, or colons left behind
    cleaned = re.sub(r"^[\s\-–—:•*.]+\s*", "", cleaned).strip()

    # Normalize multiple whitespaces
    cleaned = re.sub(r"\s+", " ", cleaned)

    # If everything was stripped (e.g. description was only a code), revert to sanitized original
    if not cleaned:
        cleaned = re.sub(r"\s+", " ", text).strip()

    return cleaned
