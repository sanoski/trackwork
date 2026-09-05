import pytest

from app import auth, users


def test_create_and_verify():
    u = users.create_user("boss@example.com", "Boss", "password123", "admin")
    assert u.role == "admin"
    assert auth.verify_password("password123", users.find_user("BOSS@example.com").password_hash)


@pytest.mark.parametrize("args", [
    ("boss@example.com", "Dup", "password123", "viewer"),   # duplicate
    ("x@example.com", "X", "short", "viewer"),               # weak password
    ("y@example.com", "Y", "password123", "king"),           # unknown role
    ("no-at-sign", "Z", "password123", "viewer"),            # bad email
])
def test_create_rejects(args):
    users.create_user("boss@example.com", "Boss", "password123", "admin")
    with pytest.raises(ValueError):
        users.create_user(*args)


def test_last_admin_guard():
    users.create_user("boss@example.com", "Boss", "password123", "admin")
    with pytest.raises(ValueError):
        users.update_user("boss@example.com", role="viewer")
    with pytest.raises(ValueError):
        users.delete_user("boss@example.com")
    users.create_user("it@example.com", "IT", "password123", "admin")
    assert users.update_user("boss@example.com", role="entry").role == "entry"
    users.delete_user("boss@example.com")
    with pytest.raises(LookupError):
        users.find_user("boss@example.com")
    with pytest.raises(ValueError):
        users.delete_user("it@example.com")


def test_update_password_and_validation():
    users.create_user("a@example.com", "A", "password123", "admin")
    with pytest.raises(ValueError):
        users.update_user("a@example.com")
    with pytest.raises(ValueError):
        users.update_user("a@example.com", password="short")
    users.update_user("a@example.com", password="newpassword1", name="AA")
    u = users.find_user("a@example.com")
    assert u.name == "AA" and auth.verify_password("newpassword1", u.password_hash)
    with pytest.raises(LookupError):
        users.update_user("ghost@example.com", name="x")
