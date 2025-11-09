import unittest
import asyncio
import pytest
from unittest.mock import Mock, patch, AsyncMock, MagicMock
from deriv_api import DerivAPI
from deriv_api.errors import ConnectionError

class TestMultiConnection(unittest.TestCase):
    """Integration tests for the multi-connection functionality."""
    
    @pytest.mark.asyncio
    @patch('deriv_api.connection.Connection', autospec=True)
    @patch('deriv_api.connection_manager.ConnectionManager', autospec=True)
    async def setUp(self, mock_manager_class, mock_connection_class):
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
        await asyncio.sleep(0.1) # wait for connect ready
    
    async def test_init(self):
        """Test initialization of DerivAPI with connection manager."""
        # Verify connection manager is created
        self.assertEqual(self.api.connection_manager, self.mock_manager)
        
        # Verify default connection is created
        self.mock_manager.create_connection.assert_called_once()
        self.assertEqual(self.api.default_connection, 0)
    
    async def test_create_connection(self):
        """Test creating a new connection through DerivAPI."""
        # Set up the mock
        self.mock_manager.create_connection.return_value = 1
        
        # Create a new connection
        new_conn_id = self.api.create_connection(
            endpoint=self.endpoint,
            app_id=self.app_id
        )
        
        # Verify a new connection was created
        self.assertEqual(new_conn_id, 1)
        self.mock_manager.create_connection.assert_called_with(
            endpoint=self.endpoint,
            app_id=self.app_id
        )
    
    async def test_disconnect(self):
        """Test disconnecting a connection."""
        await self.api.disconnect(1)
        self.mock_manager.get_connection.assert_called_once_with(1)

    async def test_disconnect_all(self):
        """Test disconnecting all connections."""
        await self.api.disconnect_all()
        self.mock_manager.disconnect_all.assert_called_once()

    async def test_send(self):
        """Test sending a request to a specific connection."""
        request = {"ping": 1}
        response = {"ping": 1, "req_id": 1}
        self.mock_connection.send.return_value = response

        # Send request to connection 1
        result = await self.api.send(request, connection_id=1)

        # Verify the correct connection was used
        self.mock_manager.get_connection.assert_called_once_with(1)
        self.mock_connection.send.assert_called_once_with(request)
        self.assertEqual(result, response)
    
    async def test_send_with_nonexistent_connection(self):
        """Test sending a request to a non-existent connection."""
        self.mock_manager.get_connection.return_value = None
        with self.assertRaises(ConnectionError):
            await self.api.send({"ping": 1}, connection_id=999)
    
    async def test_subscribe(self):
        """Test subscribing to a stream on a specific connection."""
        request = {"ticks": "R_50", "subscribe": 1}
        source = MagicMock()
        self.mock_connection.send_and_get_source.return_value = source

        # Subscribe to ticks on connection 1
        result = await self.api.subscribe(request, connection_id=1)

        # Verify the correct connection was used
        self.mock_manager.get_connection.assert_called_once_with(1)
        self.assertEqual(result, source)
    
    async def test_forget(self):
        """Test forgetting a subscription on a specific connection."""
        subs_id = "some_id"
        response = {"forget": 1}
        self.mock_manager.get_subscription.return_value = {"connection_id": 1}
        self.mock_connection.send.return_value = response

        # Forget subscription on connection 1
        result = await self.api.forget(subs_id)

        # Verify the correct connection was used
        self.mock_manager.get_subscription.assert_called_once_with(subs_id)
        self.mock_manager.get_connection.assert_called_once_with(1)
        self.assertEqual(result, response)
    
    async def test_forget_all(self):
        """Test forgetting all subscriptions of a certain type on a specific connection."""
        response = {"forget_all": "ticks"}
        self.mock_manager.get_all_subscriptions.return_value = [
            {"connection_id": 1, "subs_id": "a"},
            {"connection_id": 1, "subs_id": "b"},
        ]
        self.mock_connection.send.return_value = response

        # Forget all ticks subscriptions on connection 1
        result = await self.api.forget_all("ticks", connection_id=1)
        
        # Verify the correct connection was used
        self.mock_manager.get_all_subscriptions.assert_called_once_with("ticks")
        self.mock_manager.get_connection.assert_called_once_with(1)
        self.assertEqual(result, response)
