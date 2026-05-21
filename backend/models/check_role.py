from fastapi import Depends, HTTPException
from core import auth as auth_functions
from schema import auth as schema_auth


class RoleChecker:
    def __init__(self, allowed_roles: list[str]):
        self.allowed_roles = allowed_roles

    def __call__(self, user: schema_auth.User = Depends(auth_functions.get_current_user)):
        if user.role not in self.allowed_roles:
            raise HTTPException(status_code=403, detail="Operation not permitted")
