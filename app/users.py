"""Login accounts and their roles.

Three roles: admin (manages everything), entry (logs and corrects work), viewer (read only).
The web admin screen and the CLI `user` commands both call these. Not found raises
LookupError; invalid input, duplicates, and the last-admin guard raise ValueError.
"""
from __future__ import annotations

from typing import Optional

from . import storage
from .auth import hash_password
from .models import User

ROLES = ("admin", "entry", "viewer")
MIN_PASSWORD = 8


def list_users() -> list[User]:
    return storage.load_users()


def _find(users: list[User], email: str) -> User:
    key = (email or "").strip().lower()
    user = next((u for u in users if u.email.lower() == key), None)
    if user is None:
        raise LookupError(f"No user with email '{email}'")
    return user


def find_user(email: str) -> User:
    return _find(storage.load_users(), email)


def _check_role(role: str) -> str:
    if role not in ROLES:
        raise ValueError(f"role must be one of: {', '.join(ROLES)}")
    return role


def _check_password(password: Optional[str]) -> str:
    if len(password or "") < MIN_PASSWORD:
        raise ValueError(f"password must be at least {MIN_PASSWORD} characters")
    return password


def _admin_count(users: list[User]) -> int:
    return sum(1 for u in users if u.role == "admin")


def create_user(email: str, name: str, password: str, role: str = "viewer") -> User:
    email = (email or "").strip()
    name = (name or "").strip()
    if not email or "@" not in email:
        raise ValueError("a valid email address is required")
    if not name:
        raise ValueError("name is required")
    _check_password(password)
    _check_role(role)
    users = storage.load_users()
    if any(u.email.lower() == email.lower() for u in users):
        raise ValueError(f"a user with email '{email}' already exists")
    user = User(email=email, password_hash=hash_password(password), name=name, role=role)
    users.append(user)
    storage.save_users(users)
    return user


def update_user(email: str, *, name: Optional[str] = None, role: Optional[str] = None,
                password: Optional[str] = None) -> User:
    """Change a user's name, role, or password. Refuses to demote the only admin."""
    if name is None and role is None and password is None:
        raise ValueError("No fields provided; specify at least one of: name, role, password")
    users = storage.load_users()
    user = _find(users, email)
    if name is not None:
        name = name.strip()
        if not name:
            raise ValueError("name cannot be empty")
        user.name = name
    if role is not None:
        _check_role(role)
        if user.role == "admin" and role != "admin" and _admin_count(users) == 1:
            raise ValueError("cannot demote the only admin; make someone else an admin first")
        user.role = role
    if password is not None:
        user.password_hash = hash_password(_check_password(password))
    storage.save_users(users)
    return user


def delete_user(email: str) -> User:
    """Remove a user. Refuses to delete the only admin."""
    users = storage.load_users()
    user = _find(users, email)
    if user.role == "admin" and _admin_count(users) == 1:
        raise ValueError("cannot delete the only admin; make someone else an admin first")
    users.remove(user)
    storage.save_users(users)
    return user
