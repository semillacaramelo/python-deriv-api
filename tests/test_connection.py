import unittest
import asyncio
from unittest.mock import Mock, patch, AsyncMock
from deriv_api.connection import Connection
from deriv_api.errors import ConstructionError

class TestConnection(unittest.TestCase):
    """Test cases for the Connection class."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.connection_id = 1
        self.app_id = "1234"
        self.endpoint = "ws.derivws.com"
    
    def test_init_with_app_id(self):
        """Test initializing a connection with app_id."""
        connection = Connection(
            connection_id=self.connection_id,
            app_id=self.app_id,
            endpoint=self.endpoint
        )
        
        self.assertEqual(connection.connection_id, self.connection_id)
        self.assertEqual(connection.app_id, self.app_id)
        self.assertEqual(connection.endpoint, self.endpoint)
        self.assertFalse(connection.auto_reconnect)
        self.assertIsNone(connection.wsconnection)
    
    def test_init_without_app_id(self):
        """Test that initializing without app_id raises an error."""
        with self.assertRaises(ConstructionError):
            Connection(connection_id=self.connection_id, endpoint=self.endpoint)
    
    def test_init_with_auto_reconnect(self):
        """Test initializing with auto_reconnect=True."""
        connection = Connection(
            connection_id=self.connection_id,
            app_id=self.app_id,
            endpoint=self.endpoint,
            auto_reconnect=True
        )
        
        self.assertTrue(connection.auto_reconnect)
    
    def test_build_api_url(self):
        """Test building the API URL."""
        connection = Connection(
            connection_id=self.connection_id,
            app_id=self.app_id,
            endpoint=self.endpoint,
            lang="FR",
            brand="binary"
        )
        
        expected_url = f"wss://{self.endpoint}/websockets/v3?app_id={self.app_id}&l=FR&brand=binary"
        self.assertEqual(connection._build_api_url(), expected_url)
    
    @patch('websockets.connect', new_callable=AsyncMock)
    async def test_connect(self, mock_connect):
        """Test connecting to the WebSocket."""
        mock_ws = AsyncMock()
        mock_connect.return_value = mock_ws
        
        connection = Connection(
            connection_id=self.connection_id,
            app_id=self.app_id,
            endpoint=self.endpoint
        )
        
        # Capture events emitted by the connection
        events = []
        connection.events.subscribe(lambda event: events.append(event))
        
        # Connect
        result = await connection.connect()
        
        # Verify the WebSocket was connected
        mock_connect.assert_called_once_with(connection.api_url)
        self.assertEqual(result, mock_ws)
        
        # Verify the connected future was resolved
        self.assertTrue(connection.connected.is_resolved())
        
        # Verify connect event was emitted
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]['name'], 'connect')
        self.assertEqual(events[0]['connection_id'], self.connection_id)
    
    @patch('websockets.connect', new_callable=AsyncMock)
    async def test_send_message(self, mock_connect):
        """Test sending a message through the connection."""
        mock_ws = AsyncMock()
        mock_connect.return_value = mock_ws
        
        connection = Connection(
            connection_id=self.connection_id,
            app_id=self.app_id,
            endpoint=self.endpoint
        )
        
        # Connect
        await connection.connect()
        
        # Send a message
        request = {"ping": 1}
        source = connection.send_and_get_source(request)
        
        # Verify the request ID was set
        self.assertEqual(request['req_id'], 1)
        
        # Verify the request was stored in pending_requests
        self.assertIn(1, connection.pending_requests)
        
        # Verify the WebSocket send method was called
        mock_ws.send.assert_called_once()
        
        # Return a response from the WebSocket
        response = {"ping": "pong", "req_id": 1}
        mock_ws.recv.return_value = '{"ping": "pong", "req_id": 1}'
        
        # Simulate message processing
        await connection._process_message('{"ping": "pong", "req_id": 1}')
        
        # Complete the observable
        return source

if __name__ == '__main__':
    unittest.main()