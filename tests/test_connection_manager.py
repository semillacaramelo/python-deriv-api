import asyncio
import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from deriv_api.connection_manager import ConnectionManager
from deriv_api.errors import ConnectionError

@pytest.fixture
def manager():
    return ConnectionManager()

@pytest.fixture
def app_id():
    return "1234"

@pytest.fixture
def endpoint():
    return "ws.derivws.com"

def test_init(manager):
    """Test initialization of the ConnectionManager."""
    assert manager.connection_counter == 0
    assert len(manager.connections) == 0

@patch('deriv_api.connection_manager.Connection')
def test_create_connection(mock_connection_class, manager, endpoint, app_id):
    """Test creating a new connection."""
    # Set up the mock
    mock_connection = mock_connection_class.return_value
    mock_connection.events = MagicMock()
    mock_connection.events.subscribe = MagicMock()

    # Create a connection
    connection_id = manager.create_connection(
        endpoint=endpoint,
        app_id=app_id
    )

    # Verify the connection was created with correct parameters
    mock_connection_class.assert_called_once_with(
        connection_id,
        endpoint=endpoint,
        app_id=app_id
    )

    # Verify the connection was stored
    assert connection_id == 0
    assert 0 in manager.connections
    assert manager.connections[0] == mock_connection

    # Verify the connection counter was incremented
    assert manager.connection_counter == 1

    # Verify the event subscription was set up
    mock_connection.events.subscribe.assert_called_once()
    
@patch('deriv_api.connection_manager.Connection')
def test_create_multiple_connections(mock_connection_class, manager, endpoint, app_id):
    """Test creating multiple connections."""
    # Set up the mock to return different connections for each call
    connections = [MagicMock(), MagicMock(), MagicMock()]
    for conn in connections:
        conn.events = MagicMock()
        conn.events.subscribe = MagicMock()
    mock_connection_class.side_effect = connections

    # Create multiple connections
    conn_ids = []
    for i in range(3):
        conn_id = manager.create_connection(
            endpoint=endpoint,
            app_id=app_id
        )
        conn_ids.append(conn_id)

    # Verify the connections were created with correct IDs
    assert conn_ids == [0, 1, 2]

    # Verify all connections were stored
    assert len(manager.connections) == 3
    for i in range(3):
        assert i in manager.connections
        assert manager.connections[i] == connections[i]

    # Verify the connection counter was updated
    assert manager.connection_counter == 3

@patch('deriv_api.connection_manager.Connection')
def test_get_connection(mock_connection_class, manager, endpoint, app_id):
    """Test retrieving a connection by ID."""
    # Set up mock connections
    mock_connection = mock_connection_class.return_value
    mock_connection.events = MagicMock()
    mock_connection.events.subscribe = MagicMock()

    # Create a connection
    conn_id = manager.create_connection(
        endpoint=endpoint,
        app_id=app_id
    )

    # Get the connection
    connection = manager.get_connection(conn_id)

    # Verify the correct connection was returned
    assert connection == mock_connection

    # Test getting a non-existent connection
    non_existent_connection = manager.get_connection(999)
    assert non_existent_connection is None

@patch('deriv_api.connection_manager.Connection', autospec=True)
def test_get_all_connections(mock_connection_class, manager, endpoint, app_id):
    """Test retrieving all connection IDs."""
    # Set up mock connections
    connections = [MagicMock(), MagicMock(), MagicMock()]
    for conn in connections:
        conn.events = MagicMock()
        conn.events.subscribe = MagicMock()
    mock_connection_class.side_effect = connections

    # Create multiple connections
    for _ in range(3):
        manager.create_connection(
            endpoint=endpoint,
            app_id=app_id
        )
    
    # Get all connection IDs
    conn_ids = manager.get_all_connections()

    # Verify all connection IDs were returned
    assert sorted(conn_ids) == [0, 1, 2]

@pytest.mark.asyncio
@patch('deriv_api.connection_manager.Connection', autospec=True)
async def test_connect_all(mock_connection_class, manager, endpoint, app_id):
    """Test connecting all connections."""
    # Set up mock connections
    connections = [AsyncMock(), AsyncMock(), AsyncMock()]
    for conn in connections:
        conn.events = MagicMock()
        conn.events.subscribe = MagicMock()
        conn.connected = MagicMock()
        conn.connected.is_pending = MagicMock(return_value=True)
        conn.connect = AsyncMock()
    mock_connection_class.side_effect = connections
    
    # Create multiple connections
    for _ in range(3):
        manager.create_connection(
            endpoint=endpoint,
            app_id=app_id
        )
    
    # Connect all connections
    results = await manager.connect_all()

    # Verify connect was called on all connections
    for conn in connections:
        conn.connect.assert_called_once()

    # Verify results were returned
    assert len(results) == 3
    assert all(results)

@pytest.mark.asyncio
@patch('deriv_api.connection_manager.Connection', autospec=True)
async def test_close_connection(mock_connection_class, manager, endpoint, app_id):
    """Test closing a connection."""
    # Set up mock connection
    mock_connection = AsyncMock()
    mock_connection.events = MagicMock()
    mock_connection.events.subscribe = MagicMock()
    mock_connection.disconnect = AsyncMock()
    mock_connection_class.return_value = mock_connection

    # Create a connection
    conn_id = manager.create_connection(
        endpoint=endpoint,
        app_id=app_id
    )

    # Close the connection
    await manager.close_connection(conn_id)

    # Verify disconnect was called
    mock_connection.disconnect.assert_called_once()

    # Verify connection was removed
    assert conn_id not in manager.connections
    
    # Test closing a non-existent connection
    with pytest.raises(ConnectionError):
        await manager.close_connection(999)

@pytest.mark.asyncio
@patch('deriv_api.connection_manager.Connection', autospec=True)
async def test_disconnect_all(mock_connection_class, manager, endpoint, app_id):
    """Test disconnecting all connections."""
    # Set up mock connections
    connections = [AsyncMock(), AsyncMock(), AsyncMock()]
    for conn in connections:
        conn.events = MagicMock()
        conn.events.subscribe = MagicMock()
        conn.connected = MagicMock()
        conn.connected.is_resolved = MagicMock(return_value=True)
        conn.disconnect = AsyncMock()
    mock_connection_class.side_effect = connections

    # Create multiple connections
    for _ in range(3):
        manager.create_connection(
            endpoint=endpoint,
            app_id=app_id
        )

    # Disconnect all connections
    await manager.disconnect_all()

    # Verify disconnect was called on all connections
    for conn in connections:
        conn.disconnect.assert_called_once()

@patch('deriv_api.connection_manager.Connection')
def test_handle_connection_event(mock_connection_class, manager, endpoint, app_id):
    """Test handling connection events."""
    # Set up mock connection
    mock_connection = mock_connection_class.return_value
    mock_connection.events = MagicMock()
    mock_connection.events.subscribe = MagicMock()

    # Set up test event receivers
    all_events = []
    error_events = []
    manager.events_subject.subscribe(lambda event: all_events.append(event))
    manager.error_subject.subscribe(lambda event: error_events.append(event))

    # Create a connection
    conn_id = manager.create_connection(
        endpoint=endpoint,
        app_id=app_id
    )

    # Capture the event handler that was registered with the connection
    event_handler = mock_connection.events.subscribe.call_args[0][0]

    # Test normal event
    event_handler({'name': 'connect', 'data': 'test'})
    assert len(all_events) == 1
    assert all_events[0]['name'] == 'connect'
    assert all_events[0]['connection_id'] == conn_id
    assert all_events[0]['data'] == 'test'
    assert len(error_events) == 0

    # Test error event
    event_handler({'name': 'error', 'data': 'test_error'})
    assert len(all_events) == 2
    assert all_events[1]['name'] == 'error'
    assert all_events[1]['connection_id'] == conn_id
    assert all_events[1]['data'] == 'test_error'
    assert len(error_events) == 1
    assert error_events[0]['name'] == 'error'
    assert error_events[0]['connection_id'] == conn_id
    assert error_events[0]['data'] == 'test_error'
