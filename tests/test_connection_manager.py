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
    mock_connection = mock_connection_class.return_value
    mock_connection.events = MagicMock()
    mock_connection.events.subscribe = MagicMock()

    connection_id = manager.create_connection(endpoint=endpoint, app_id=app_id)

    mock_connection_class.assert_called_once_with(connection_id, endpoint=endpoint, app_id=app_id)
    assert connection_id == 0
    assert 0 in manager.connections
    assert manager.connections[0] == mock_connection
    assert manager.connection_counter == 1
    mock_connection.events.subscribe.assert_called_once()
    
@patch('deriv_api.connection_manager.Connection')
def test_create_multiple_connections(mock_connection_class, manager, endpoint, app_id):
    """Test creating multiple connections."""
    connections = [MagicMock(), MagicMock(), MagicMock()]
    for conn in connections:
        conn.events = MagicMock()
        conn.events.subscribe = MagicMock()
    mock_connection_class.side_effect = connections

    conn_ids = [manager.create_connection(endpoint=endpoint, app_id=app_id) for _ in range(3)]

    assert conn_ids == [0, 1, 2]
    assert len(manager.connections) == 3
    for i in range(3):
        assert i in manager.connections
        assert manager.connections[i] == connections[i]
    assert manager.connection_counter == 3

@patch('deriv_api.connection_manager.Connection')
def test_get_connection(mock_connection_class, manager, endpoint, app_id):
    """Test retrieving a connection by ID."""
    mock_connection = mock_connection_class.return_value
    mock_connection.events = MagicMock()
    mock_connection.events.subscribe = MagicMock()

    conn_id = manager.create_connection(endpoint=endpoint, app_id=app_id)
    connection = manager.get_connection(conn_id)

    assert connection == mock_connection
    assert manager.get_connection(999) is None

@pytest.mark.asyncio
@patch('deriv_api.connection_manager.Connection', autospec=True)
async def test_connect_all(mock_connection_class, manager, endpoint, app_id):
    """Test connecting all connections."""
    connections = [AsyncMock(), AsyncMock(), AsyncMock()]
    for conn in connections:
        conn.events = MagicMock()
        conn.events.subscribe = MagicMock()
        conn.connected = MagicMock()
        conn.connected.is_pending.return_value = True
        conn.connect = AsyncMock()
    mock_connection_class.side_effect = connections
    
    for _ in range(3):
        manager.create_connection(endpoint=endpoint, app_id=app_id)
    
    results = await manager.connect_all()

    for conn in connections:
        conn.connect.assert_called_once()

    assert len(results) == 3
    assert all(results)

@pytest.mark.asyncio
@patch('deriv_api.connection_manager.Connection', autospec=True)
async def test_close_connection(mock_connection_class, manager, endpoint, app_id):
    """Test closing a connection."""
    mock_connection = AsyncMock()
    mock_connection.events = MagicMock()
    mock_connection.events.subscribe = MagicMock()
    mock_connection.disconnect = AsyncMock()
    mock_connection_class.return_value = mock_connection

    conn_id = manager.create_connection(endpoint=endpoint, app_id=app_id)

    await manager.close_connection(conn_id)

    mock_connection.disconnect.assert_called_once()
    assert conn_id not in manager.connections
    
    with pytest.raises(ConnectionError):
        await manager.close_connection(999)

@pytest.mark.asyncio
@patch('deriv_api.connection_manager.Connection', autospec=True)
async def test_disconnect_all(mock_connection_class, manager, endpoint, app_id):
    """Test disconnecting all connections."""
    connections = [AsyncMock(), AsyncMock(), AsyncMock()]
    for conn in connections:
        conn.events = MagicMock()
        conn.events.subscribe = MagicMock()
        conn.connected = MagicMock()
        conn.connected.is_resolved.return_value = True
        conn.disconnect = AsyncMock()
    mock_connection_class.side_effect = connections

    for _ in range(3):
        manager.create_connection(endpoint=endpoint, app_id=app_id)

    await manager.disconnect_all()

    for conn in connections:
        conn.disconnect.assert_called_once()

@patch('deriv_api.connection_manager.Connection')
def test_handle_connection_event(mock_connection_class, manager, endpoint, app_id):
    """Test handling connection events."""
    mock_connection = mock_connection_class.return_value
    mock_connection.events = MagicMock()
    mock_connection.events.subscribe = MagicMock()

    all_events = []
    error_events = []
    manager.events_subject.subscribe(lambda event: all_events.append(event))
    manager.error_subject.subscribe(lambda event: error_events.append(event))

    conn_id = manager.create_connection(endpoint=endpoint, app_id=app_id)
    event_handler = mock_connection.events.subscribe.call_args[0][0]

    event_handler({'name': 'connect', 'data': 'test'})
    assert len(all_events) == 1
    assert all_events[0]['name'] == 'connect'
    assert all_events[0]['connection_id'] == conn_id
    assert all_events[0]['data'] == 'test'
    assert len(error_events) == 0

    event_handler({'name': 'error', 'data': 'test_error'})
    assert len(all_events) == 2
    assert all_events[1]['name'] == 'error'
    assert all_events[1]['connection_id'] == conn_id
    assert all_events[1]['data'] == 'test_error'
    assert len(error_events) == 1
    assert error_events[0]['name'] == 'error'
    assert error_events[0]['connection_id'] == conn_id
    assert error_events[0]['data'] == 'test_error'
