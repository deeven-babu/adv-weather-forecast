import pytest

from app import create_app
from models import User, db


@pytest.fixture()
def client():
    app = create_app({"TESTING": True, "SECRET_KEY": "test-secret", "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:"})
    with app.test_client() as test_client:
        yield test_client
    with app.app_context():
        db.drop_all()


def register(client, email="student@example.com", password="strong-pass-123"):
    return client.post("/register", data={"name": "Student", "email": email, "password": password, "confirm_password": password})


def test_user_registration_hashes_password(client):
    response = register(client)
    assert response.status_code == 302
    with client.application.app_context():
        user = User.query.filter_by(email="student@example.com").first()
        assert user is not None
        assert user.password_hash != "strong-pass-123"
        assert user.check_password("strong-pass-123")


def test_login_redirects_to_protected_dashboard(client):
    register(client)
    response = client.post("/login", data={"email": "student@example.com", "password": "strong-pass-123"})
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/dashboard")
    assert client.get("/dashboard").status_code == 200


def test_invalid_login_is_rejected(client):
    register(client)
    response = client.post("/login", data={"email": "student@example.com", "password": "wrong-password"})
    assert response.status_code == 401
    assert b"Invalid email or password" in response.data


def test_logout_clears_session(client):
    register(client)
    client.post("/login", data={"email": "student@example.com", "password": "strong-pass-123"})
    response = client.get("/logout")
    assert response.status_code == 302
    assert client.get("/dashboard").status_code == 302