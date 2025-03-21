import unittest
import asyncio
from unittest.mock import Mock, patch, AsyncMock, MagicMock
from deriv_api import DerivAPI
from deriv_api.errors import ConnectionError

class TestMultiConnection(unittest.TestCase):
    """Integration tests for the multi-connection functionality."""
    
    @patch('deriv_api.connection.Connection', autospec=True)
    @patch('deriv_api.connection_manager.ConnectionManager', autospec=True)
    def setUp(self, mock_manager_class, mock_connection_class):
        """Set up test fixtures."""
        self.app_id = "1234"
        self.endpoint = "ws.derivws.com"
        
        # Set up mock connection manager
        self.mock_manager = MagicMock()
        self.mock_manager.create_connection.return_value = 0
        self.mock_manager.events_subject = MagicMock()
        self.mock_manager.events_subject.subscribe = MagicMock()
        self.mock_manager.error_subject = MagicMock()
        self.mock_manager.error_subject.subscribe = MagicMock()
        mock_manager_class.return_value = self.mock_manager
        
        # Set up mock connection
        self.mock_connection = AsyncMock()
        self.mock_connection.events = MagicMock()
        self.mock_connection.send = AsyncMock()
        self.mock_connection.send_and_get_source = MagicMock()
        mock_connection_class.return_value = self.mock_connection
        
        # Create the API instance
        self.api = DerivAPI(
            endpoint=self.endpoint,
            app_id=self.app_id
        )
    
    def test_init(self):
        """Test initialization of DerivAPI with connection manager."""
        # Verify connection manager is created
        self.assertEqual(self.api.connection_manager, self.mock_manager)
        
        # Verify default connection is created
        self.mock_manager.create_connection.assert_called_once()
        self.assertEqual(self.api.default_connection, 0)
    
    def test_create_connection(self):
        """Test creating a new connection through DerivAPI."""
        # Set up the mock
        self.mock_manager.create_connection.return_value = 1
        
        # Create a connection
        connection_id = self.api.create_connection(
            endpoint=self.endpoint,
            app_id=self.app_id
        )
        
        # Verify the connection was created
        self.assertEqual(connection_id, 1)
        self.mock_manager.create_connection.assert_called_with(
            endpoint=self.endpoint,
            app_id=self.app_id
        )
    
    async def test_send(self):
        """Test sending a request through a specific connection."""
        # Set up mocks
        self.mock_manager.get_connection.return_value = self.mock_connection
        self.mock_connection.send.return_value = {"ping": "pong"}
        
        # Send a request through the default connection
        response = await self.api.send({"ping": 1})
        
        # Verify the request was sent through the default connection
        self.mock_manager.get_connection.assert_called_with(0)
        self.mock_connection.send.assert_called_with({"ping": 1})
        self.assertEqual(response, {"ping": "pong"})
        
        # Reset mocks
        self.mock_manager.get_connection.reset_mock()
        self.mock_connection.send.reset_mock()
        
        # Send a request through a specific connection
        response = await self.api.send({"ping": 1}, connection_id=1)
        
        # Verify the request was sent through the specified connection
        self.mock_manager.get_connection.assert_called_with(1)
        self.mock_connection.send.assert_called_with({"ping": 1})
        self.assertEqual(response, {"ping": "pong"})
    
    async def test_send_with_nonexistent_connection(self):
        """Test sending a request through a non-existent connection."""
        # Set up mock to simulate a non-existent connection
        self.mock_manager.get_connection.return_value = None
        
        # Verify a ConnectionError is raised
        with self.assertRaises(ConnectionError):
            await self.api.send({"ping": 1}, connection_id=999)
    
    @patch('deriv_api.subscription_manager.SubscriptionManager', autospec=True)
    async def test_subscribe(self, mock_subscription_manager):
        """Test subscribing through a specific connection."""
        # Set up mock
        mock_subscription_manager.subscribe = AsyncMock()
        mock_subscription_manager.subscribe.return_value = "subscription_result"
        self.api.subscription_manager = mock_subscription_manager
        
        # Subscribe through the default connection
        result = await self.api.subscribe({"ticks": "R_100"})
        
        # Verify the subscription was made through the default connection
        mock_subscription_manager.subscribe.assert_called_with({"ticks": "R_100"}, None)
        self.assertEqual(result, "subscription_result")
        
        # Reset mock
        mock_subscription_manager.subscribe.reset_mock()
        
        # Subscribe through a specific connection
        result = await self.api.subscribe({"ticks": "R_100"}, connection_id=1)
        
        # Verify the subscription was made through the specified connection
        mock_subscription_manager.subscribe.assert_called_with({"ticks": "R_100"}, 1)
        self.assertEqual(result, "subscription_result")
    
    @patch('deriv_api.subscription_manager.SubscriptionManager', autospec=True)
    async def test_forget(self, mock_subscription_manager):
        """Test forgetting a subscription through a specific connection."""
        # Set up mock
        mock_subscription_manager.forget = AsyncMock()
        mock_subscription_manager.forget.return_value = {"forget": 1}
        self.api.subscription_manager = mock_subscription_manager
        
        # Forget a subscription through the default connection
        result = await self.api.forget("subscription_id")
        
        # Verify the forget was called through the default connection
        mock_subscription_manager.forget.assert_called_with("subscription_id", None)
        self.assertEqual(result, {"forget": 1})
        
        # Reset mock
        mock_subscription_manager.forget.reset_mock()
        
        # Forget a subscription through a specific connection
        result = await self.api.forget("subscription_id", connection_id=1)
        
        # Verify the forget was called through the specified connection
        mock_subscription_manager.forget.assert_called_with("subscription_id", 1)
        self.assertEqual(result, {"forget": 1})
    
    @patch('deriv_api.subscription_manager.SubscriptionManager', autospec=True)
    async def test_forget_all(self, mock_subscription_manager):
        """Test forgetting all subscriptions through a specific connection."""
        # Set up mock
        mock_subscription_manager.forget_all = AsyncMock()
        mock_subscription_manager.forget_all.return_value = {"forget_all": ["ticks"]}
        self.api.subscription_manager = mock_subscription_manager
        
        # Forget all subscriptions through the default connection
        result = await self.api.forget_all("ticks")
        
        # Verify forget_all was called through the default connection
        mock_subscription_manager.forget_all.assert_called_with("ticks", connection_id=None)
        self.assertEqual(result, {"forget_all": ["ticks"]})
        
        # Reset mock
        mock_subscription_manager.forget_all.reset_mock()
        
        # Forget all subscriptions through a specific connection
        result = await self.api.forget_all("ticks", connection_id=1)
        
        # Verify forget_all was called through the specified connection
        mock_subscription_manager.forget_all.assert_called_with("ticks", connection_id=1)
        self.assertEqual(result, {"forget_all": ["ticks"]})
    
    async def test_disconnect(self):
        """Test disconnecting a specific connection."""
        # Set up mocks
        mock_connection1 = AsyncMock()
        mock_connection2 = AsyncMock()
        
        self.mock_manager.get_connection = MagicMock()
        self.mock_manager.get_connection.side_effect = lambda conn_id: {
            0: mock_connection1,
            1: mock_connection2
        }.get(conn_id)
        
        # Disconnect the default connection
        await self.api.disconnect()
        
        # Verify the default connection was disconnected
        mock_connection1.disconnect.assert_called_once()
        mock_connection2.disconnect.assert_not_called()
        
        # Reset mocks
        mock_connection1.disconnect.reset_mock()
        
        # Disconnect a specific connection
        await self.api.disconnect(connection_id=1)
        
        # Verify the specific connection was disconnected
        mock_connection1.disconnect.assert_not_called()
        mock_connection2.disconnect.assert_called_once()
    
    async def test_disconnect_all(self):
        """Test disconnecting all connections."""
        # Set up mock
        self.mock_manager.disconnect_all = AsyncMock()
        
        # Disconnect all connections
        await self.api.disconnect_all()
        
        # Verify the manager's disconnect_all method was called
        self.mock_manager.disconnect_all.assert_called_once()

if __name__ == '__main__':
    unittest.main()