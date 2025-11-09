# project/tests/test_health.py
import pytest
from unittest.mock import patch
from src.api.v1.health import get_health_status, health_check_endpoint

def test_get_health_status_ok():
    """
    Test get_health_status returns 'ok' under normal conditions.
    Mocks os.getenv to ensure no maintenance mode is active.
    """
    with patch('os.getenv', return_value=None): # No maintenance mode
        status = get_health_status()
        assert status["status"] == "ok"
        assert "database_status" in status["details"]
        assert status["details"]["database_status"] == "connected"

def test_get_health_status_degraded_maintenance_mode():
    """
    Test get_health_status returns 'degraded' when maintenance mode is active.
    Mocks os.getenv to simulate APP_MAINTENANCE_MODE being 'true'.
    """
    with patch('os.getenv', side_effect=lambda k, d=None: "true" if k == "APP_MAINTENANCE_MODE" else d):
        status = get_health_status()
        assert status["status"] == "degraded"
        assert status["details"]["maintenance_mode"] is True
        assert status["details"]["database_status"] == "connected" # Other checks still pass

def test_health_check_endpoint_ok():
    """
    Test health_check_endpoint returns 200 and 'ok' status when underlying health is good.
    Mocks get_health_status to control its return value.
    """
    with patch('src.api.v1.health.get_health_status', return_value={"status": "ok", "details": {"database_status": "connected"}}):
        response, status_code = health_check_endpoint()
        assert status_code == 200
        assert response["status"] == "ok"

def test_health_check_endpoint_degraded():
    """
    Test health_check_endpoint returns 503 and 'degraded' status when underlying health is not 'ok'.
    Mocks get_health_status to control its return value.
    """
    with patch('src.api.v1.health.get_health_status', return_value={"status": "degraded", "details": {"database_status": "failed"}}):
        response, status_code = health_check_endpoint()
        assert status_code == 503
        assert response["status"] == "degraded"

# project/tests/test_config.py
import pytest
from unittest.mock import patch, MagicMock
from src.core.config import AppConfig, ConfigError

@pytest.fixture(autouse=True)
def reset_app_config_singleton():
    """
    Fixture to reset the AppConfig singleton before each test.
    This ensures tests are isolated from each other's config changes.
    """
    # Store original instance state
    original_instance = AppConfig._instance
    original_initialized = False
    if original_instance:
        original_initialized = original_instance._initialized

    # Reset for the test
    AppConfig._instance = None
    yield
    # Restore original instance state
    AppConfig._instance = original_instance
    if original_instance:
        original_instance._initialized = original_initialized

def test_app_config_singleton():
    """
    Test that AppConfig returns the same instance (singleton pattern).
    """
    config1 = AppConfig()
    config2 = AppConfig()
    assert config1 is config2

def test_app_config_loads_from_env_and_defaults(mocker):
    """
    Test AppConfig loads values from environment variables or uses defaults.
    Mocks dotenv.load_dotenv and os.getenv.
    """
    mocker.patch('dotenv.load_dotenv')
    mocker.patch('os.getenv', side_effect=lambda k, d=None: {
        "DATABASE_URL": "postgresql://user:pass@host:5432/db",
        "API_VERSION": "v2",
        "DEBUG_MODE": "True",
        "SECRET_KEY": "test_secret"
    }.get(k, d))

    config = AppConfig()
    assert config.DATABASE_URL == "postgresql://user:pass@host:5432/db"
    assert config.API_VERSION == "v2"
    assert config.DEBUG_MODE is True
    assert config.SECRET_KEY == "test_secret"

    # Test default values when env vars are not set
    mocker.patch('os.getenv', side_effect=lambda k, d=None: {
        "SECRET_KEY": "another_secret" # Still need SECRET_KEY for validation
    }.get(k, d))
    config.reload() # Reload to pick up new mocked env
    assert config.DATABASE_URL == "sqlite:///./test.db"
    assert config.API_VERSION == "v1"
    assert config.DEBUG_MODE is False

def test_app_config_get_method():
    """
    Test the get() method retrieves configuration values correctly, including defaults and non-existent keys.
    """
    with patch('dotenv.load_dotenv'), \
         patch('os.getenv', side_effect=lambda k, d=None: {
             "SECRET_KEY": "some_key",
             "CUSTOM_SETTING": "custom_value"
         }.get(k, d)):
        config = AppConfig()
        assert config.get("SECRET_KEY") == "some_key"
        assert config.get("API_VERSION") == "v1" # Default value
        assert config.get("NON_EXISTENT_KEY") is None
        assert config.get("NON_EXISTENT_KEY", "default_val") == "default_val"

def test_app_config_validate_success(mocker):
    """
    Test AppConfig.validate() succeeds when all required settings (e.g., SECRET_KEY) are present.
    """
    mocker.patch('dotenv.load_dotenv')
    mocker.patch('os.getenv', side_effect=lambda k, d=None: {
        "SECRET_KEY": "a_valid_secret"
    }.get(k, d))
    config = AppConfig()
    assert config.validate() is True

def test_app_config_validate_missing_secret_key(mocker):
    """
    Test AppConfig.validate() raises ConfigError when SECRET_KEY is missing.
    """
    mocker.patch('dotenv.load_dotenv')
    mocker.patch('os.getenv', return_value=None) # No SECRET_KEY
    config = AppConfig()
    with pytest.raises(ConfigError, match="SECRET_KEY is not set"):
        config.validate()

def test_app_config_reload(mocker):
    """
    Test AppConfig.reload() reloads configuration from environment variables, reflecting changes.
    """
    mock_load_dotenv = mocker.patch('dotenv.load_dotenv')
    mock_getenv = mocker.patch('os.getenv', side_effect=lambda k, d=None: {
        "SECRET_KEY": "initial_secret",
        "API_VERSION": "v1"
    }.get(k, d))

    config = AppConfig()
    assert config.SECRET_KEY == "initial_secret"
    assert config.API_VERSION == "v1"
    mock_load_dotenv.assert_called_once()

    # Change environment variables and reload
    mock_getenv.side_effect = lambda k, d=None: {
        "SECRET_KEY": "reloaded_secret",
        "API_VERSION": "v3"
    }.get(k, d)
    config.reload()

    assert config.SECRET_KEY == "reloaded_secret"
    assert config.API_VERSION == "v3"
    assert mock_load_dotenv.call_count == 2 # Called again on reload

# project/tests/test_database.py
import pytest
from unittest.mock import MagicMock, patch
from sqlalchemy.exc import OperationalError
from src.core.database import DatabaseManager, DatabaseError

@pytest.fixture
def mock_sqlalchemy_engine(mocker):
    """
    Fixture to mock sqlalchemy.create_engine and its components for database tests.
    """
    mock_engine = MagicMock()
    mock_connection = MagicMock()
    mock_engine.connect.return_value.__enter__.return_value = mock_connection
    mock_session_local = MagicMock()
    mocker.patch('sqlalchemy.create_engine', return_value=mock_engine)
    mocker.patch('sqlalchemy.orm.sessionmaker', return_value=mock_session_local)
    return mock_engine, mock_session_local

def test_database_manager_init():
    """
    Test DatabaseManager initialization sets database_url and nullifies engine/SessionLocal.
    """
    db_url = "sqlite:///:memory:"
    db_manager = DatabaseManager(db_url)
    assert db_manager.database_url == db_url
    assert db_manager.engine is None
    assert db_manager.SessionLocal is None

def test_database_manager_connect_success(mock_sqlalchemy_engine):
    """
    Test successful database connection, verifying engine and sessionmaker are set up.
    """
    mock_engine, mock_session_local = mock_sqlalchemy_engine
    db_manager = DatabaseManager("sqlite:///:memory:")
    db_manager.connect()

    mock_engine.connect.assert_called_once()
    mock_engine.connect.return_value.__enter__.return_value.execute.assert_called_once_with("SELECT 1")
    assert db_manager.engine is mock_engine
    assert db_manager.SessionLocal is mock_session_local

def test_database_manager_connect_operational_error(mocker):
    """
    Test database connection failure due to an SQLAlchemy OperationalError.
    """
    mocker.patch('sqlalchemy.create_engine', side_effect=OperationalError("mock_db_error", {}, {}))
    db_manager = DatabaseManager("invalid_url")
    with pytest.raises(DatabaseError, match="Could not connect to database: mock_db_error"):
        db_manager.connect()
    assert db_manager.engine is None
    assert db_manager.SessionLocal is None

def test_database_manager_connect_generic_error(mocker):
    """
    Test database connection failure due to a generic unexpected error.
    """
    mocker.patch('sqlalchemy.create_engine', side_effect=Exception("generic error"))
    db_manager = DatabaseManager("invalid_url")
    with pytest.raises(DatabaseError, match="An unexpected error occurred during database connection: generic error"):
        db_manager.connect()
    assert db_manager.engine is None
    assert db_manager.SessionLocal is None

def test_database_manager_disconnect(mock_sqlalchemy_engine):
    """
    Test database disconnection, verifying engine.dispose() is called and attributes are reset.
    """
    mock_engine, _ = mock_sqlalchemy_engine
    db_manager = DatabaseManager("sqlite:///:memory:")
    db_manager.connect() # Establish connection first
    db_manager.disconnect()

    mock_engine.dispose.assert_called_once()
    assert db_manager.engine is None
    assert db_manager.SessionLocal is None

def test_database_manager_disconnect_not_connected():
    """
    Test disconnecting when not connected does not raise an error and changes nothing.
    """
    db_manager = DatabaseManager("sqlite:///:memory:")
    db_manager.disconnect() # Should not raise error
    assert db_manager.engine is None
    assert db_manager.SessionLocal is None

def test_database_manager_get_session_success(mock_sqlalchemy_engine):
    """
    Test getting a database session successfully and ensuring it's closed after use.
    """
    mock_engine, mock_session_local = mock_sqlalchemy_engine
    mock_session = MagicMock()
    mock_session_local.return_value = mock_session

    db_manager = DatabaseManager("sqlite:///:memory:")
    db_manager.connect()

    session_generator = db_manager.get_session()
    session = next(session_generator)

    assert session is mock_session
    mock_session_local.assert_called_once()
    mock_session.close.assert_not_called() # Should not be closed yet

    # Ensure session is closed when generator exits
    with pytest.raises(StopIteration):
        next(session_generator) # Exhaust the generator
    mock_session.close.assert_called_once()

def test_database_manager_get_session_not_connected():
    """
    Test getting a session before connecting raises a DatabaseError.
    """
    db_manager = DatabaseManager("sqlite:///:memory:")
    with pytest.raises(DatabaseError, match="Database not connected. Call .connect() first."):
        next(db_manager.get_session())

# project/tests/test_main.py
import pytest
from unittest.mock import patch, MagicMock
import sys
from src.main import initialize_app, main
from src.core.config import AppConfig, ConfigError
from src.core.database import DatabaseManager, DatabaseError
from src.api.v1.health import health_check_endpoint # Imported for mocking purposes

@pytest.fixture
def mock_app_components(mocker):
    """
    Fixture to mock AppConfig, DatabaseManager, and health_check_endpoint for main/initialize_app tests.
    """
    mock_app_config = MagicMock(spec=AppConfig)
    mock_app_config.DATABASE_URL = "sqlite:///:memory:"
    mock_app_config.DEBUG_MODE = True
    mock_app_config.API_VERSION = "v1"
    mock_app_config.validate.return_value = True

    mock_db_manager = MagicMock(spec=DatabaseManager)

    mocker.patch('src.main.AppConfig', return_value=mock_app_config)
    mocker.patch('src.main.DatabaseManager', return_value=mock_db_manager)
    mocker.patch('src.main.health_check_endpoint', return_value=({"status": "ok", "details": {}}, 200))

    return mock_app_config, mock_db_manager

def test_initialize_app_success(mock_app_components):
    """
    Test successful application initialization, verifying config validation and DB connection.
    """
    mock_app_config, mock_db_manager = mock_app_components
    app_config, db_manager = initialize_app()

    mock_app_config.validate.assert_called_once()
    mock_db_manager.connect.assert_called_once()
    assert app_config is mock_app_config
    assert db_manager is mock_db_manager

def test_initialize_app_config_error(mock_app_components, mocker):
    """
    Test initialize_app handles ConfigError during validation and exits the application.
    """
    mock_app_config, _ = mock_app_components
    mock_app_config.validate.side_effect = ConfigError("Test config error")
    mock_sys_exit = mocker.patch('sys.exit')
    mocker.patch('builtins.print') # Suppress print statements during test

    initialize_app()
    mock_sys_exit.assert_called_once_with(1)

def test_initialize_app_database_error(mock_app_components, mocker):
    """
    Test initialize_app handles DatabaseError during connection and exits the application.
    """
    _, mock_db_manager = mock_app_components
    mock_db_manager.connect.side_effect = DatabaseError("Test DB error")
    mock_sys_exit = mocker.patch('sys.exit')
    mocker.patch('builtins.print') # Suppress print statements during test

    initialize_app()
    mock_sys_exit.assert_called_once_with(1)

def test_initialize_app_generic_error(mock_app_components, mocker):
    """
    Test initialize_app handles generic exceptions during initialization and exits the application.
    """
    mock_app_config, _ = mock_app_components
    mock_app_config.validate.side_effect = Exception("Generic init error")
    mock_sys_exit = mocker.patch('sys.exit')
    mocker.patch('builtins.print') # Suppress print statements during test

    initialize_app()
    mock_sys_exit.assert_called_once_with(1)

def test_main_function_flow(mock_app_components, mocker):
    """
    Test the main function's overall flow, including initialization, health check, and cleanup.
    Mocks initialize_app, health_check_endpoint, and builtins.print.
    """
    mock_app_config, mock_db_manager = mock_app_components
    mock_initialize_app = mocker.patch('src.main.initialize_app', return_value=(mock_app_config, mock_db_manager))
    mock_health_check = mocker.patch('src.main.health_check_endpoint', return_value=({"status": "ok", "details": {}}, 200))
    mock_print = mocker.patch('builtins.print')

    main()

    mock_initialize_app.assert_called_once()
    mock_health_check.assert_called_once()
    mock_db_manager.disconnect.assert_called_once()
    # Optional: Assert specific print calls if their content is critical
    # mock_print.assert_any_call("Starting application...")
    # mock_print.assert_any_call(f"Application running in DEBUG_MODE: {mock_app_config.DEBUG_MODE}")
    # mock_print.assert_any_call("Application stopped.")

def test_main_function_exit_on_init_failure(mocker):
    """
    Test that main correctly handles SystemExit raised by initialize_app.
    """
    mock_initialize_app = mocker.patch('src.main.initialize_app', side_effect=lambda: sys.exit(1))
    mock_sys_exit = mocker.patch('sys.exit')
    mocker.patch('builtins.print') # Suppress print statements during test

    with pytest.raises(SystemExit) as excinfo:
        main()

    assert excinfo.value.code == 1
    mock_initialize_app.assert_called_once()
    mock_sys_exit.assert_not_called() # sys.exit from initialize_app already terminated.
```