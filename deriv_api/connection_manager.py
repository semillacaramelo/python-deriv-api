import asyncio
import logging
from typing import Dict, Optional, List, Any

from reactivex.subject import Subject
from reactivex import Observable
import reactivex.operators as op

from deriv_api.connection import Connection
from deriv_api.errors import ConstructionError, ConnectionError

class ConnectionManager:
    """
    Manages multiple WebSocket connections to the Deriv API.
    
    This class is responsible for creating, tracking, and managing multiple WebSocket
    connections to the Deriv API. It provides methods for creating new connections,
    retrieving existing connections, and monitoring connection events and errors.
    
    Properties
    ----------
    error_subject : Subject
        An Observable that emits error events from all connections
    events_subject : Subject
        An Observable that emits all events from all connections
    """
    
    def __init__(self):
        """Initialize the connection manager."""
        self.connections: Dict[int, Connection] = {}
        self.connection_counter = 0
        self.error_subject = Subject()
        self.events_subject = Subject()
    
    def create_connection(self, **options) -> int:
        """
        Create a new connection with the given options.
        
        Parameters
        ----------
        **options
            Connection configuration options. See Connection class for details.
            
        Returns
        -------
        int
            The ID of the newly created connection
        """
        connection_id = self.connection_counter
        self.connection_counter += 1
        
        connection = Connection(connection_id, **options)
        
        # Register event handlers
        connection.events.subscribe(
            lambda event: self._handle_connection_event(connection_id, event)
        )
        
        self.connections[connection_id] = connection
        return connection_id
    
    def get_connection(self, connection_id: int) -> Optional[Connection]:
        """
        Get a connection by its ID.
        
        Parameters
        ----------
        connection_id : int
            The ID of the connection to retrieve
            
        Returns
        -------
        Optional[Connection]
            The connection if found, None otherwise
        """
        return self.connections.get(connection_id)
    
    def get_all_connections(self) -> List[int]:
        """
        Get all connection IDs.
        
        Returns
        -------
        List[int]
            A list of all connection IDs
        """
        return list(self.connections.keys())
    
    async def connect_all(self):
        """
        Connect all connections that haven't been connected yet.
        
        Returns
        -------
        List[bool]
            A list of booleans indicating whether each connection was successful
        """
        connection_tasks = [
            connection.connect() for connection in self.connections.values()
            if connection.connected.is_pending()
        ]
        
        if not connection_tasks:
            return []
        
        results = await asyncio.gather(*connection_tasks, return_exceptions=True)
        return [not isinstance(result, Exception) for result in results]
    
    async def disconnect_all(self):
        """
        Disconnect all connections.
        """
        disconnect_tasks = [
            connection.disconnect() for connection in self.connections.values()
            if connection.connected.is_resolved()
        ]
        
        if disconnect_tasks:
            await asyncio.gather(*disconnect_tasks)
    
    async def close_connection(self, connection_id: int):
        """
        Close and remove a connection.
        
        Parameters
        ----------
        connection_id : int
            The ID of the connection to close
            
        Raises
        ------
        ConnectionError
            If the connection doesn't exist
        """
        connection = self.get_connection(connection_id)
        if not connection:
            raise ConnectionError(f"Connection {connection_id} not found")
        
        await connection.disconnect()
        del self.connections[connection_id]
    
    def monitor_errors(self) -> Observable:
        """
        Get an Observable of all connection errors.
        
        Returns
        -------
        Observable
            An Observable that emits error events from all connections
        """
        return self.error_subject.pipe(op.share())
    
    def monitor_events(self) -> Observable:
        """
        Get an Observable of all connection events.
        
        Returns
        -------
        Observable
            An Observable that emits all events from all connections
        """
        return self.events_subject.pipe(op.share())
    
    def _handle_connection_event(self, connection_id: int, event: Dict[str, Any]):
        """
        Handle an event from a connection.
        
        Parameters
        ----------
        connection_id : int
            The ID of the connection that emitted the event
        event : Dict[str, Any]
            The event data
        """
        # Add connection_id to the event if not already present
        if 'connection_id' not in event:
            event['connection_id'] = connection_id
        
        # Forward all events to the events subject
        self.events_subject.on_next(event)
        
        # Forward error events to the error subject
        if event['name'] in ['error', 'connection_closed', 'reconnect_failed', 'reconnect_max_retries_exceeded']:
            self.error_subject.on_next(event)