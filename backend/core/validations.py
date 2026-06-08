import re
_PASSWORD_PATTERN = re.compile(
    r"^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[^A-Za-z0-9]).+$"
)

_NAME_PATTERN = re.compile(r"^[A-Za-z _]+$")

NAME_REQUIREMENTS = "Name may only contain letters, spaces, and underscores."

def validate_password_strength(password: str) -> str:
    if not _PASSWORD_PATTERN.match(password) or len(password) < 8:
        raise ValueError("Password must be more than 8 characters and include uppercase, lowercase, number, and special character.")
    return password


def validate_name(value: str) -> str:
    trimmed = value.strip()
    if not trimmed:
        raise ValueError("Name cannot be empty.")
    if not _NAME_PATTERN.match(trimmed):
        raise ValueError(NAME_REQUIREMENTS)
    if not re.search(r"[A-Za-z]", trimmed):
        raise ValueError("Name must contain at least one letter.")
    return trimmed
