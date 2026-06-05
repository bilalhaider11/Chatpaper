import re

_NAME_PATTERN = re.compile(r"^[A-Za-z _]+$")

NAME_REQUIREMENTS = "Name may only contain letters, spaces, and underscores."


def validate_name(value: str) -> str:
    trimmed = value.strip()
    if not trimmed:
        raise ValueError("Name cannot be empty.")
    if not _NAME_PATTERN.match(trimmed):
        raise ValueError(NAME_REQUIREMENTS)
    if not re.search(r"[A-Za-z]", trimmed):
        raise ValueError("Name must contain at least one letter.")
    return trimmed
