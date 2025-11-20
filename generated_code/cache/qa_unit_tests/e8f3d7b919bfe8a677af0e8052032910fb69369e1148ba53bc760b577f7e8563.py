```python
# backend_infrastructure/tests/conftest.py
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from fastapi.testclient import TestClient
from src.main import app
from src.database import Base, get_db
from src.models.user import User
from src.security import get_password_hash
from src.config import settings
from datetime import timedelta
from src.security import create_access_token as _create_access_token

# Use an in-memory SQLite database for testing
SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"
test_engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)

@pytest.fixture(name="db_session")
def db_session_fixture():
    """
    Provides a test database session.
    Creates tables before tests and drops them after.
    """
    Base.metadata.create_all(bind=test_engine)
    db = TestSessionLocal()
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=test_engine)

@pytest.fixture(name="client")
def client_fixture(db_session):
    """
    Provides a FastAPI test client with an overridden database dependency.
    """
    def override_get_db():
        try:
            yield db_session
        finally:
            db_session.close()

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()

@pytest.fixture(name="test_user_data")
def test_user_data_fixture():
    """Provides common test user data."""
    return {
        "email": "test@example.com",
        "password": "testpassword123",
        "hashed_password": get_password_hash("testpassword123")
    }

@pytest.fixture(name="another_test_user_data")
def another_test_user_data_fixture():
    """Provides common test user data for a second user."""
    return {
        "email": "another@example.com",
        "password": "anotherpassword",
        "hashed_password": get_password_hash("anotherpassword")
    }

@pytest.fixture(name="inactive_user_data")
def inactive_user_data_fixture():
    """Provides data for an inactive test user."""
    return {
        "email": "inactive@example.com",
        "password": "inactivepassword",
        "hashed_password": get_password_hash("inactivepassword"),
        "is_active": False
    }

@pytest.fixture(name="registered_user")
def registered_user_fixture(db_session, test_user_data):
    """Creates and returns a registered user in the test database."""
    user = User(
        email=test_user_data["email"],
        hashed_password=test_user_data["hashed_password"]
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user

@pytest.fixture(name="inactive_registered_user")
def inactive_registered_user_fixture(db_session, inactive_user_data):
    """Creates and returns an inactive registered user in the test database."""
    user = User(
        email=inactive_user_data["email"],
        hashed_password=inactive_user_data["hashed_password"],
        is_active=inactive_user_data["is_active"]
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user

@pytest.fixture(name="auth_token")
def auth_token_fixture(client, registered_user, test_user_data):
    """
    Logs in the registered_user and returns an access token.
    Requires the client fixture.
    """
    response = client.post(
        "/auth/token",
        data={"username": test_user_data["email"], "password": test_user_data["password"]}
    )
    assert response.status_code == 200
    return response.json()["access_token"]

@pytest.fixture(name="inactive_auth_token")
def inactive_auth_token_fixture(inactive_registered_user, inactive_user_data):
    """
    Creates an access token for an inactive user.
    """
    return _create_access_token(data={"sub": inactive_user_data["email"]})

```
```python
# backend_infrastructure/tests/test_main.py
from fastapi.testclient import TestClient

def test_read_root(client: TestClient):
    """
    Test the root endpoint of the application.
    """
    response = client.get("/")
    assert response.status_code == 200
    assert response.json() == {"message": "Welcome to the Backend Infrastructure API!"}

# Additional tests for router inclusion are implicitly covered by testing router endpoints.
# For example, if /auth/register works, it means the auth router is included.
# The `db_session` fixture in conftest.py already ensures tables are created on startup
# and dropped afterwards, implicitly testing the `on_event("startup")` hook.
```
```python
# backend_infrastructure/tests/test_security.py
from datetime import datetime, timedelta, timezone
import pytest
from jose import jwt, JWTError
from src.security import (
    verify_password,
    get_password_hash,
    create_access_token,
    decode_access_token
)
from src.config import settings
from src.schemas.token import TokenData

def test_verify_password_success():
    """
    Test password verification for a correct password.
    """
    password = "mysecretpassword"
    hashed_password = get_password_hash(password)
    assert verify_password(password, hashed_password) is True

def test_verify_password_failure():
    """
    Test password verification for an incorrect password.
    """
    password = "mysecretpassword"
    hashed_password = get_password_hash(password)
    assert verify_password("wrongpassword", hashed_password) is False

def test_get_password_hash_format():
    """
    Test that password hashing produces a valid hash string.
    """
    password = "anothersecretpassword"
    hashed_password = get_password_hash(password)
    assert isinstance(hashed_password, str)
    assert len(hashed_password) > 0
    assert hashed_password.startswith("$2b$") # bcrypt hash prefix

def test_get_password_hash_is_not_deterministic():
    """
    Test that hashing the same password multiple times produces different hashes
    due to salting.
    """
    password = "password123"
    hash1 = get_password_hash(password)
    hash2 = get_password_hash(password)
    assert hash1 != hash2
    assert verify_password(password, hash1)
    assert verify_password(password, hash2)

def test_create_access_token_default_expiry():
    """
    Test access token creation with default expiry and verify its payload.
    """
    data = {"sub": "test@example.com"}
    token = create_access_token(data)
    assert isinstance(token, str)
    assert len(token) > 0

    decoded_payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    assert decoded_payload["sub"] == data["sub"]
    assert "exp" in decoded_payload
    # Check expiry is roughly within the expected window (default + a few seconds for execution)
    expected_expire_time = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    assert decoded_payload["exp"] > datetime.now(timezone.utc).timestamp()
    assert decoded_payload["exp"] < (expected_expire_time + timedelta(minutes=1)).timestamp()

def test_create_access_token_custom_expiry():
    """
    Test access token creation with a custom expiry and verify its payload.
    """
    data = {"sub": "test@example.com"}
    expires_delta = timedelta(minutes=5)
    token = create_access_token(data, expires_delta=expires_delta)

    decoded_payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    assert decoded_payload["sub"] == data["sub"]
    assert "exp" in decoded_payload
    expected_expire_time = datetime.now(timezone.utc) + expires_delta
    assert decoded_payload["exp"] > datetime.now(timezone.utc).timestamp()
    assert decoded_payload["exp"] < (expected_expire_time + timedelta(minutes=1)).timestamp()

def test_decode_access_token_valid():
    """
    Test decoding a valid access token successfully.
    """
    email = "valid@example.com"
    token = create_access_token({"sub": email})
    token_data = decode_access_token(token)
    assert token_data is not None
    assert token_data.email == email

def test_decode_access_token_invalid_signature():
    """
    Test decoding an access token with an invalid signature should return None.
    """
    # Create a token with a valid payload but sign it with a wrong key
    payload = {"sub": "test@example.com", "exp": (datetime.now(timezone.utc) + timedelta(minutes=30)).timestamp()}
    invalid_token = jwt.encode(payload, "wrong_secret_key", algorithm=settings.ALGORITHM)
    token_data = decode_access_token(invalid_token)
    assert token_data is None

def test_decode_access_token_expired():
    """
    Test decoding an expired access token should return None.
    """
    email = "expired@example.com"
    expires_delta = timedelta(seconds=-1) # Token already expired
    token = create_access_token({"sub": email}, expires_delta=expires_delta)
    token_data = decode_access_token(token)
    assert token_data is None

def test_decode_access_token_missing_sub_claim():
    """
    Test decoding an access token that is missing the 'sub' claim should return None.
    """
    # Create a token with no 'sub' claim
    payload = {"exp": (datetime.now(timezone.utc) + timedelta(minutes=30)).timestamp()}
    token_without_sub = jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    token_data = decode_access_token(token_without_sub)
    assert token_data is None

def test_decode_access_token_malformed():
    """
    Test decoding a malformed access token string should return None.
    """
    malformed_token = "this.is.not.a.jwt.token"
    token_data = decode_access_token(malformed_token)
    assert token_data is None

```
```python
# backend_infrastructure/tests/test_services_user_service.py
import pytest
from unittest.mock import MagicMock
from sqlalchemy.orm import Session
from src.services.user_service import UserService
from src.models.user import User
from src.schemas.user import UserCreate
from src import security

@pytest.fixture
def mock_security_module():
    """Mocks the security module for isolated UserService testing."""
    with pytest.patch('src.services.user_service.security') as mock_security:
        yield mock_security

@pytest.fixture
def user_service_instance():
    """Provides an instance of UserService."""
    return UserService()

@pytest.fixture
def mock_db_session():
    """Provides a mock SQLAlchemy session."""
    return MagicMock(spec=Session)

def test_get_user_by_email_found(user_service_instance: UserService, mock_db_session: MagicMock):
    """
    Test retrieving a user by email when the user exists in the database.
    """
    test_email = "test@example.com"
    mock_user = User(email=test_email, hashed_password="hashed_password")
    mock_db_session.query.return_value.filter.return_value.first.return_value = mock_user

    user = user_service_instance.get_user_by_email(mock_db_session, test_email)

    assert user == mock_user
    mock_db_session.query.assert_called_once_with(User)
    mock_db_session.query.return_value.filter.assert_called_once()

def test_get_user_by_email_not_found(user_service_instance: UserService, mock_db_session: MagicMock):
    """
    Test retrieving a user by email when the user does not exist in the database.
    """
    test_email = "nonexistent@example.com"
    mock_db_session.query.return_value.filter.return_value.first.return_value = None

    user = user_service_instance.get_user_by_email(mock_db_session, test_email)

    assert user is None
    mock_db_session.query.assert_called_once_with(User)

def test_create_user_success(user_service_instance: UserService, mock_db_session: MagicMock, mock_security_module: MagicMock):
    """
    Test creating a new user successfully.
    """
    user_create_data = UserCreate(email="newuser@example.com", password="newpassword")
    hashed_password = "mock_hashed_password"
    mock_security_module.get_password_hash.return_value = hashed_password

    created_user = user_service_instance.create_user(mock_db_session, user_create_data)

    mock_security_module.get_password_hash.assert_called_once_with(user_create_data.password)
    mock_db_session.add.assert_called_once()
    mock_db_session.commit.assert_called_once()
    mock_db_session.refresh.assert_called_once_with(mock_db_session.add.call_args[0][0]) # Check refresh was called on the added user object

    assert created_user.email == user_create_data.email
    assert created_user.hashed_password == hashed_password
    assert created_user.is_active is True # Default value

def test_authenticate_user_success(user_service_instance: UserService, mock_db_session: MagicMock, mock_security_module: MagicMock):
    """
    Test successful user authentication with correct credentials.
    """
    test_email = "auth@example.com"
    test_password = "authpassword"
    hashed_password = "hashed_auth_password"
    mock_user = User(email=test_email, hashed_password=hashed_password)

    # Mock get_user_by_email internally to control its return
    user_service_instance.get_user_by_email = MagicMock(return_value=mock_user)
    mock_security_module.verify_password.return_value = True

    authenticated_user = user_service_instance.authenticate_user(mock_db_session, test_email, test_password)

    user_service_instance.get_user_by_email.assert_called_once_with(mock_db_session, test_email)
    mock_security_module.verify_password.assert_called_once_with(test_password, hashed_password)
    assert authenticated_user == mock_user

def test_authenticate_user_not_found(user_service_instance: UserService, mock_db_session: MagicMock, mock_security_module: MagicMock):
    """
    Test user authentication when the user is not found in the database.
    """
    test_email = "nonexistent@example.com"
    test_password = "anypassword"

    user_service_instance.get_user_by_email = MagicMock(return_value=None)

    authenticated_user = user_service_instance.authenticate_user(mock_db_session, test_email, test_password)

    user_service_instance.get_user_by_email.assert_called_once_with(mock_db_session, test_email)
    mock_security_module.verify_password.assert_not_called() # Should not call verify if user not found
    assert authenticated_user is None

def test_authenticate_user_incorrect_password(user_service_instance: UserService, mock_db_session: MagicMock, mock_security_module: MagicMock):
    """
    Test user authentication with an incorrect password.
    """
    test_email = "auth@example.com"
    test_password = "wrongpassword"
    hashed_password = "hashed_auth_password"
    mock_user = User(email=test_email, hashed_password=hashed_password)

    user_service_instance.get_user_by_email = MagicMock(return_value=mock_user)
    mock_security_module.verify_password.return_value = False

    authenticated_user = user_service_instance.authenticate_user(mock_db_session, test_email, test_password)

    user_service_instance.get_user_by_email.assert_called_once_with(mock_db_session, test_email)
    mock_security_module.verify_password.assert_called_once_with(test_password, hashed_password)
    assert authenticated_user is None

```
```python
# backend_infrastructure/tests/test_dependencies.py
import pytest
from unittest.mock import MagicMock
from fastapi import HTTPException, status
from src.dependencies import get_current_user, get_current_active_user
from src.models.user import User
from src.schemas.token import TokenData
from src import security, services

@pytest.fixture
def mock_security_module():
    """Mocks the security module for dependency testing."""
    with pytest.patch('src.dependencies.security') as mock_security:
        yield mock_security

@pytest.fixture
def mock_user_service():
    """Mocks the UserService for dependency testing."""
    return MagicMock(spec=services.UserService)

@pytest.fixture
def mock_db_session():
    """Provides a mock SQLAlchemy session."""
    return MagicMock()

def test_get_current_user_success(mock_security_module: MagicMock, mock_user_service: MagicMock, mock_db_session: MagicMock):
    """
    Test get_current_user dependency with a valid token and active user.
    """
    test_token = "valid_token"
    test_email = "user@example.com"
    mock_security_module.decode_access_token.return_value = TokenData(email=test_email)
    mock_user = User(id=1, email=test_email, hashed_password="hashed_password", is_active=True)
    mock_user_service.get_user_by_email.return_value = mock_user

    current_user = get_current_user(test_token, mock_db_session, mock_user_service)

    mock_security_module.decode_access_token.assert_called_once_with(test_token)
    mock_user_service.get_user_by_email.assert_called_once_with(mock_db_session, email=test_email)
    assert current_user == mock_user

def test_get_current_user_invalid_token(mock_security_module: MagicMock, mock_user_service: MagicMock, mock_db_session: MagicMock):
    """
    Test get_current_user dependency with an invalid token (decode returns None).
    """
    test_token = "invalid_token"
    mock_security_module.decode_access_token.return_value = None

    with pytest.raises(HTTPException) as exc_info:
        get_current_user(test_token, mock_db_session, mock_user_service)

    assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED
    assert exc_info.value.detail == "Could not validate credentials"
    mock_security_module.decode_access_token.assert_called_once_with(test_token)
    mock_user_service.get_user_by_email.assert_not_called()

def test_get_current_user_token_data_missing_email(mock_security_module: MagicMock, mock_user_service: MagicMock, mock_db_session: MagicMock):
    """
    Test get_current_user dependency when token data is missing the email (sub claim).
    """
    test_token = "token_without_email"
    mock_security_module.decode_access_token.return_value = TokenData(email=None)

    with pytest.raises(HTTPException) as exc_info:
        get_current_user(test_token, mock_db_session, mock_user_service)

    assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED
    assert exc_info.value.detail == "Could not validate credentials"
    mock_security_module.decode_access_token.assert_called_once_with(test_token)
    mock_user_service.get_user_by_email.assert_not_called()

def test_get_current_user_user_not_found_in_db(mock_security_module: MagicMock, mock_user_service: MagicMock, mock_db_session: MagicMock):
    """
    Test get_current_user dependency when the user specified in the token is not found in the DB.
    """
    test_token = "valid_token"
    test_email = "nonexistent@example.com"
    mock_security_module.decode_access_token.return_value = TokenData(email=test_email)
    mock_user_service.get_user_by_email.return_value = None

    with pytest.raises(HTTPException) as exc_info:
        get_current_user(test_token, mock_db_session, mock_user_service)

    assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED
    assert exc_info.value.detail == "Could not validate credentials"
    mock_security_module.decode_access_token.assert_called_once_with(test_token)
    mock_user_service.get_user_by_email.assert_called_once_with(mock_db_session, email=test_email)

def test_get_current_active_user_success():
    """
    Test get_current_active_user dependency with an active user.
    """
    active_user = User(id=1, email="active@example.com", hashed_password="hashed", is_active=True)
    current_active_user = get_current_active_user(active_user)
    assert current_active_user == active_user

def test_get_current_active_user_inactive():
    """
    Test get_current_active_user dependency with an inactive user should raise HTTPException.
    """
    inactive_user = User(id=1, email="inactive@example.com", hashed_password="hashed", is_active=False)
    with pytest.raises(HTTPException) as exc_info:
        get_current_active_user(inactive_user)

    assert exc_info.value.status_code == status.HTTP_400_BAD_REQUEST
    assert exc_info.value.detail == "Inactive user"

```
```python
# backend_infrastructure/tests/test_auth.py
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from src.models.user import User
from src.security import verify_password

def test_register_user_success(client: TestClient, db_session: Session, test_user_data: dict):
    """
    Test successful user registration via the /auth/register endpoint.
    """
    response = client.post(
        "/auth/register",
        json={"email": test_user_data["email"], "password": test_user_data["password"]}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["email"] == test_user_data["email"]
    assert "id" in data
    assert data["is_active"] is True

    # Verify user is in the database
    db_user = db_session.query(User).filter(User.email == test_user_data["email"]).first()
    assert db_user is not None
    assert db_user.email == test_user_data["email"]
    assert verify_password(test_user_data["password"], db_user.hashed_password)

def test_register_user_email_already_registered(client: TestClient, registered_user: User, test_user_data: dict):
    """
    Test user registration with an email that is already registered should return 400.
    """
    response = client.post(
        "/auth/register",
        json={"email": test_user_data["email"], "password": "newpassword"}
    )
    assert response.status_code == 400
    assert response.json() == {"detail": "Email already registered"}

def test_register_user_invalid_email_format(client: TestClient):
    """
    Test user registration with an invalid email format should return 422.
    """
    response = client.post(
        "/auth/register",
        json={"email": "invalid-email", "password": "password123"}
    )
    assert response.status_code == 422 # Unprocessable Entity for Pydantic validation error
    assert "email" in response.json()["detail"][0]["loc"]

def test_register_user_missing_password(client: TestClient):
    """
    Test user registration with a missing password field should return 422.
    """
    response = client.post(
        "/auth/register",
        json={"email": "test@example.com"}
    )
    assert response.status_code == 422
    assert "password" in response.json()["detail"][0]["loc"]

def test_login_for_access_token_success(client: TestClient, registered_user: User, test_user_data: dict):
    """
    Test successful login and access token generation via /auth/token endpoint.
    """
    response = client.post(
        "/auth/token",
        data={"username": test_user_data["email"], "password": test_user_data["password"]}
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    assert len(data["access_token"]) > 0

def test_login_for_access_token_incorrect_password(client: TestClient, registered_user: User, test_user_data: dict):
    """
    Test login with an incorrect password should return 401.
    """
    response = client.post(
        "/auth/token",
        data={"username": test_user_data["email"], "password": "wrongpassword"}
    )
    assert response.status_code == 401
    assert response.json() == {"detail": "Incorrect username or password"}

def test_login_for_access_token_user_not_found(client: TestClient):
    """
    Test login with a non-existent user should return 401.
    """
    response = client.post(
        "/auth/token",
        data={"username": "nonexistent@example.com", "password": "anypassword"}
    )
    assert response.status_code == 401
    assert response.json() == {"detail": "Incorrect username or password"}

def test_login_for_access_token_missing_username(client: TestClient):
    """
    Test login with missing username in form data should return 422.
    """
    response = client.post(
        "/auth/token",
        data={"password": "testpassword123"} # Missing username
    )
    assert response.status_code == 422
    assert "username" in response.json()["detail"][0]["loc"]

def test_login_for_access_token_missing_password(client: TestClient):
    """
    Test login with missing password in form data should return 422.
    """
    response = client.post(
        "/auth/token",
        data={"username": "test@example.com"} # Missing password
    )
    assert response.status_code == 422
    assert "password" in response.json()["detail"][0]["loc"]

```
```python
# backend_infrastructure/tests/test_users.py
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from src.models.user import User
from src.security import verify_password

def test_read_users_me_success(client: TestClient, registered_user: User, auth_token: str):
    """
    Test retrieving the current authenticated user's information via /users/me endpoint.
    """
    response = client.get(
        "/users/me",
        headers={"Authorization": f"Bearer {auth_token}"}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["email"] == registered_user.email
    assert data["id"] == registered_user.id
    assert data["is_active"] is True

def test_read_users_me_unauthorized_no_token(client: TestClient):
    """
    Test retrieving current user without an authorization token should return 401.
    """
    response = client.get("/users/me")
    assert response.status_code == 401
    assert response.json() == {"detail": "Not authenticated"}

def test_read_users_me_unauthorized_invalid_token(client: TestClient):
    """
    Test retrieving current user with an invalid authorization token should return 401.
    """
    response = client.get(
        "/users/me",
        headers={"Authorization": "Bearer invalid_token"}
    )
    assert response.status_code == 401
    assert response.json() == {"detail": "Could not validate credentials"}

def test_read_users_me_inactive_user(client: TestClient, inactive_registered_user: User, inactive_auth_token: str):
    """
    Test retrieving current user when the user is inactive should return 400.
    """
    response = client.get(
        "/users/me",
        headers={"Authorization": f"Bearer {inactive_auth_token}"}
    )
    assert response.status_code == 400
    assert response.json() == {"detail": "Inactive user"}

def test_create_user_endpoint_success(client: TestClient, db_session: Session, another_test_user_data: dict):
    """
    Test creating a user via the /users/ endpoint successfully.
    This endpoint might be for admin or public registration.
    """
    response = client.post(
        "/users/",
        json={"email": another_test_user_data["email"], "password": another_test_user_data["password"]}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["email"] == another_test_user_data["email"]
    assert "id" in data
    assert data["is_active"] is True

    # Verify user is in the database
    db_user = db_session.query(User).filter(User.email == another_test_user_data["email"]).first()
    assert db_user is not None
    assert db_user.email == another_test_user_data["email"]
    assert verify_password(another_test_user_data["password"], db_user.hashed_password)

def test_create_user_endpoint_email_already_registered(client: TestClient, registered_user: User, test_user_data: dict):
    """
    Test creating a user via /users/ endpoint with an email that is already registered should return 400.
    """
    response = client.post(
        "/users/",
        json={"email": test_user_data["email"], "password": "newpassword"}
    )
    assert response.status_code == 400
    assert response.json() == {"detail": "Email already registered"}

def test_create_user_endpoint_invalid_email_format(client: TestClient):
    """
    Test creating a user via /users/ endpoint with an invalid email format should return 422.
    """
    response = client.post(
        "/users/",
        json={"email": "invalid-email", "password": "password123"}
    )
    assert response.status_code == 422
    assert "email" in response.json()["detail"][0]["loc"]

def test_create_user_endpoint_missing_password(client: TestClient):
    """
    Test creating a user via /users/ endpoint with a missing password should return 422.
    """
    response = client.post(
        "/users/",
        json={"email": "test@example.com"}
    )
    assert response.status_code == 422
    assert "password" in response.json()["detail"][0]["loc"]

```