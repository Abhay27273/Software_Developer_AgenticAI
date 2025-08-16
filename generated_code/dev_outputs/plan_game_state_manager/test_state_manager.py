import pytest
from unittest.mock import Mock, call

from src.game_states.state_manager import GameStateManager
from src.game_states.states import GameStateEnum

@pytest.fixture
def mock_scene_manager():
    return Mock()

@pytest.fixture
def mock_event_bus():
    return Mock()

@pytest.fixture
def state_manager(mock_scene_manager, mock_event_bus):
    """Fixture to create a GameStateManager instance with mocked dependencies."""
    return GameStateManager(mock_scene_manager, mock_event_bus)

def test_initialization(state_manager, mock_scene_manager, mock_event_bus):
    """Test that the state manager initializes to the main menu correctly."""
    state_manager.initialize()
    
    assert state_manager.current_state_enum == GameStateEnum.MAIN_MENU
    assert isinstance(state_manager.current_state, state_manager._states[GameStateEnum.MAIN_MENU].__class__)
    
    # Check that the scene was loaded and event was published
    mock_scene_manager.load_scene.assert_called_once_with("main_menu")
    mock_event_bus.publish.assert_called_once_with(
        "gameStateChanged",
        old_state=GameStateEnum.NONE,
        new_state=GameStateEnum.MAIN_MENU
    )

def test_valid_transition(state_manager, mock_scene_manager, mock_event_bus):
    """Test a valid state transition from Main Menu to Gameplay."""
    state_manager.initialize()
    
    # Reset mocks after initialization
    mock_scene_manager.reset_mock()
    mock_event_bus.reset_mock()

    # Perform the transition
    state_manager.change_state(GameStateEnum.GAMEPLAY, level="level_2")

    assert state_manager.current_state_enum == GameStateEnum.GAMEPLAY
    
    # Verify scene manager was called for the new scene
    mock_scene_manager.load_scene.assert_called_once_with("level_2")
    
    # Verify event bus was called with correct parameters
    mock_event_bus.publish.assert_called_once_with(
        "gameStateChanged",
        old_state=GameStateEnum.MAIN_MENU,
        new_state=GameStateEnum.GAMEPLAY,
        level="level_2"
    )

def test_invalid_transition(state_manager, mock_scene_manager, mock_event_bus):
    """Test that an invalid state transition is prevented."""
    state_manager.initialize()
    
    # Reset mocks after initialization
    mock_scene_manager.reset_mock()
    mock_event_bus.reset_mock()

    # Attempt an invalid transition (e.g., Main Menu -> Paused)
    state_manager.change_state(GameStateEnum.PAUSED)

    # Assert that the state did NOT change
    assert state_manager.current_state_enum == GameStateEnum.MAIN_MENU
    
    # Assert that no methods were called on the mocks
    mock_scene_manager.load_scene.assert_not_called()
    mock_event_bus.publish.assert_not_called()

def test_full_game_flow(state_manager, mock_scene_manager, mock_event_bus):
    """Test a typical sequence of state transitions."""
    # 1. Initialize to Main Menu
    state_manager.initialize()
    assert state_manager.current_state_enum == GameStateEnum.MAIN_MENU
    
    # 2. Start game
    state_manager.change_state(GameStateEnum.GAMEPLAY)
    assert state_manager.current_state_enum == GameStateEnum.GAMEPLAY
    
    # 3. Pause game
    state_manager.change_state(GameStateEnum.PAUSED)
    assert state_manager.current_state_enum == GameStateEnum.PAUSED
    
    # 4. Resume game
    state_manager.change_state(GameStateEnum.GAMEPLAY)
    assert state_manager.current_state_enum == GameStateEnum.GAMEPLAY
    
    # 5. Game Over
    state_manager.change_state(GameStateEnum.GAME_OVER, score=1000)
    assert state_manager.current_state_enum == GameStateEnum.GAME_OVER
    
    # 6. Return to Main Menu
    state_manager.change_state(GameStateEnum.MAIN_MENU)
    assert state_manager.current_state_enum == GameStateEnum.MAIN_MENU

    # Check calls
    assert mock_scene_manager.load_scene.call_count == 5 # Init, Gameplay, GameOver, MainMenu (Pause has no scene)
    assert mock_event_bus.publish.call_count == 6 # Init + 5 changes

def test_transition_to_same_state(state_manager, mock_scene_manager, mock_event_bus):
    """Test that transitioning to the current state does nothing."""
    state_manager.initialize()
    
    mock_scene_manager.reset_mock()
    mock_event_bus.reset_mock()
    
    state_manager.change_state(GameStateEnum.MAIN_MENU)
    
    assert state_manager.current_state_enum == GameStateEnum.MAIN_MENU
    mock_scene_manager.load_scene.assert_not_called()
    mock_event_bus.publish.assert_not_called()