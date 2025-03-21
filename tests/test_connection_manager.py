import unittest
import asyncio
from unittest.mock import Mock, patch, AsyncMock, MagicMock
from deriv_api.connection_manager import ConnectionManager
from deriv_api.errors import ConnectionError

class TestConnectionManager(unittest.TestCase):
    """Test cases for the ConnectionManager class."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.manager = ConnectionManager()
        self.app_id = "1234"
        self.endpoint = "ws.derivws.com"
    
    def test_init(self):
        """Test initialization of the ConnectionManager."""
        self.assertEqual(self.manager.connection_counter, 0)
        self.assertEqual(len(self.manager.connections), 0)
    
    @patch('deriv_api.connection.Connection', autospec=True)
    def test_create_connection(self, mock_connection_class):
        """Test creating a new connection."""
        # Set up the mock
        mock_connection = MagicMock()
        mock_connection.events = MagicMock()
        mock_connection.events.subscribe = MagicMock()
        mock_connection_class.return_value = mock_connection
        
        # Create a connection
        connection_id = self.manager.create_connection(
            endpoint=self.endpoint,
            app_id=self.app_id
        )
        
        # Verify the connection was created with correct parameters
        mock_connection_class.assert_called_once_with(
            0,  # connection_id
            endpoint=self.endpoint,
            app_id=self.app_id
        )
        
        # Verify the connection was stored
        self.assertEqual(connection_id, 0)
        self.assertIn(0, self.manager.connections)
        self.assertEqual(self.manager.connections[0], mock_connection)
        
        # Verify the connection counter was incremented
        self.assertEqual(self.manager.connection_counter, 1)
        
        # Verify the event subscription was set up
        mock_connection.events.subscribe.assert_called_once()
    
    @patch('deriv_api.connection.Connection', autospec=True)
    def test_create_multiple_connections(self, mock_connection_class):
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
            conn_id = self.manager.create_connection(
                endpoint=self.endpoint,
                app_id=self.app_id
            )
            conn_ids.append(conn_id)
        
        # Verify the connections were created with correct IDs
        self.assertEqual(conn_ids, [0, 1, 2])
        
        # Verify all connections were stored
        self.assertEqual(len(self.manager.connections), 3)
        for i in range(3):
            self.assertIn(i, self.manager.connections)
            self.assertEqual(self.manager.connections[i], connections[i])
        
        # Verify the connection counter was updated
        self.assertEqual(self.manager.connection_counter, 3)
    
    @patch('deriv_api.connection.Connection', autospec=True)
    def test_get_connection(self, mock_connection_class):
        """Test retrieving a connection by ID."""
        # Set up mock connections
        mock_connection = MagicMock()
        mock_connection.events = MagicMock()
        mock_connection.events.subscribe = MagicMock()
        mock_connection_class.return_value = mock_connection
        
        # Create a connection
        conn_id = self.manager.create_connection(
            endpoint=self.endpoint,
            app_id=self.app_id
        )
        
        # Get the connection
        connection = self.manager.get_connection(conn_id)
        
        # Verify the correct connection was returned
        self.assertEqual(connection, mock_connection)
        
        # Test getting a non-existent connection
        non_existent_connection = self.manager.get_connection(999)
        self.assertIsNone(non_existent_connection)
    
    @patch('deriv_api.connection.Connection', autospec=True)
    def test_get_all_connections(self, mock_connection_class):
        """Test retrieving all connection IDs."""
        # Set up mock connections
        connections = [MagicMock(), MagicMock(), MagicMock()]
        for conn in connections:
            conn.events = MagicMock()
            conn.events.subscribe = MagicMock()
        mock_connection_class.side_effect = connections
        
        # Create multiple connections
        for _ in range(3):
            self.manager.create_connection(
                endpoint=self.endpoint,
                app_id=self.app_id
            )
        
        # Get all connection IDs
        conn_ids = self.manager.get_all_connections()
        
        # Verify all connection IDs were returned
        self.assertEqual(sorted(conn_ids), [0, 1, 2])
    
    @patch('deriv_api.connection.Connection', autospec=True)
    async def test_connect_all(self, mock_connection_class):
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
            self.manager.create_connection(
                endpoint=self.endpoint,
                app_id=self.app_id
            )
        
        # Connect all connections
        results = await self.manager.connect_all()
        
        # Verify connect was called on all connections
        for conn in connections:
            conn.connect.assert_called_once()
        
        # Verify results were returned
        self.assertEqual(len(results), 3)
        self.assertTrue(all(results))
    
    @patch('deriv_api.connection.Connection', autospec=True)
    async def test_close_connection(self, mock_connection_class):
        """Test closing a connection."""
        # Set up mock connection
        mock_connection = AsyncMock()
        mock_connection.events = MagicMock()
        mock_connection.events.subscribe = MagicMock()
        mock_connection.disconnect = AsyncMock()
        mock_connection_class.return_value = mock_connection
        
        # Create a connection
        conn_id = self.manager.create_connection(
            endpoint=self.endpoint,
            app_id=self.app_id
        )
        
        # Close the connection
        await self.manager.close_connection(conn_id)
        
        # Verify disconnect was called
        mock_connection.disconnect.assert_called_once()
        
        # Verify connection was removed
        self.assertNotIn(conn_id, self.manager.connections)
        
        # Test closing a non-existent connection
        with self.assertRaises(ConnectionError):
            await self.manager.close_connection(999)
    
    @patch('deriv_api.connection.Connection', autospec=True)
    async def test_disconnect_all(self, mock_connection_class):
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
            self.manager.create_connection(
                endpoint=self.endpoint,
                app_id=self.app_id
            )
        
        # Disconnect all connections
        await self.manager.disconnect_all()
        
        # Verify disconnect was called on all connections
        for conn in connections:
            conn.disconnect.assert_called_once()
    
    @patch('deriv_api.connection.Connection', autospec=True)
    def test_handle_connection_event(self, mock_connection_class):
        """Test handling connection events."""
        # Set up mock connection
        mock_connection = MagicMock()
        mock_connection.events = MagicMock()
        mock_connection.events.subscribe = MagicMock()
        mock_connection_class.return_value = mock_connection
        
        # Set up test event receivers
        all_events = []
        error_events = []
        self.manager.events_subject.subscribe(lambda event: all_events.append(event))
        self.manager.error_subject.subscribe(lambda event: error_events.append(event))
        
        # Create a connection
        conn_id = self.manager.create_connection(
            endpoint=self.endpoint,
            app_id=self.app_id
        )
        
        # Capture the event handler that was registered with the connection
        event_handler = mock_connection.events.subscribe.call_args[0][0]
        
        # Test normal event
        event_handler({'name': 'connect', 'data': 'test'})
        self.assertEqual(len(all_events), 1)
        self.assertEqual(all_events[0]['name'], 'connect')
        self.assertEqual(all_events[0]['connection_id'], conn_id)
        self.assertEqual(all_events[0]['data'], 'test')
        self.assertEqual(len(error_events), 0)
        
        # Test error event
        event_handler({'name': 'error', 'data': 'test_error'})
        self.assertEqual(len(all_events), 2)
        self.assertEqual(all_events[1]['name'], 'error')
        self.assertEqual(all_events[1]['connection_id'], conn_id)
        self.assertEqual(all_events[1]['data'], 'test_error')
        self.assertEqual(len(error_events), 1)
        self.assertEqual(error_events[0]['name'], 'error')
        self.assertEqual(error_events[0]['connection_id'], conn_id)
        self.assertEqual(error_events[0]['data'], 'test_error')

if __name__ == '__main__':
    unittest.main()