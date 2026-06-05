import re
_PASSWORD_PATTERN = re.compile(
    r"^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[^A-Za-z0-9]).+$"
)

def validate_password_strength(password: str) -> str:
    if not _PASSWORD_PATTERN.match(password) or len(password) < 8:
        raise ValueError("Password must be more than 8 characters and include uppercase, lowercase, number, and special character.")
    return password
