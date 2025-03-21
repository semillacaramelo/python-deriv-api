import asyncio
import json
import logging
from asyncio import Future
from typing import Dict, Optional, Union, Coroutine

import websockets
from reactivex import operators as op
from reactivex.subject import Subject
from reactivex import Observable
from websockets.legacy.client import WebSocketClientProtocol
from websockets.exceptions import ConnectionClosedOK, ConnectionClosed
from websockets.frames import Close

from deriv_api.easy_future import EasyFuture
from deriv_api.errors import APIError, ConstructionError, ResponseError, AddedTaskError
from deriv_api.utils import is_valid_url

class Connection:
    """
    Encapsulates a single WebSocket connection to the Deriv API.
    
    This class handles the low-level connection management and message handling
    for a single WebSocket connection to the Deriv API.
    
    Parameters
    ----------
    connection_id : int
        Unique identifier for this connection
    options : dict
        Connection configuration options
        endpoint : str
            API server to connect to
        app_id : str
            Application ID of the API user
        connection : WebSocketClientProtocol
            A ready to use connection (optional)
        lang : str
            Language of the API communication
        brand : str
            Brand name
        auto_reconnect : bool
            Whether to automatically reconnect on connection loss
    
    Properties
    ----------
    events : Subject
        An Observable object that will send data when events like 'connect', 'send', 'message' happen
    connected : EasyFuture
        A future that resolves when the connection is established
    """
    
    def __init__(self, connection_id: int, **options):
        self.connection_id = connection_id
        self.endpoint = options.get('endpoint', 'ws.derivws.com')
        self.lang = options.get('lang', 'EN')
        self.brand = options.get('brand', '')
        self.app_id = options.get('app_id')
        self.auto_reconnect = options.get('auto_reconnect', False)
        self.max_retry_count = options.get('max_retry_count', 5)
        
        self.wsconnection: Optional[WebSocketClientProtocol] = None
        self.wsconnection_from_inside = True
        self.events = Subject()
        
        if options.get('connection'):
            self.wsconnection = options.get('connection')
            self.wsconnection_from_inside = False
        else:
            if not self.app_id:
                raise ConstructionError('An app_id is required to connect to the API')
            
            self.api_url = self._build_api_url()
        
        self.req_id = 0
        self.pending_requests: Dict[str, Subject] = {}
        self.connected = EasyFuture()
        self.receive_task = None
        self.reconnect_task = None
        self.is_closing = False
    
    def _build_api_url(self) -> str:
        """
        Construct the WebSocket URL for the API.
        
        Returns
        -------
        str
            The complete WebSocket URL
        """
        endpoint_url = self.get_url(self.endpoint)
        return f"{endpoint_url}/websockets/v3?app_id={self.app_id}&l={self.lang}&brand={self.brand}"
    
    def get_url(self, original_endpoint: str) -> str:
        """
        Validate and return the URL.
        
        Parameters
        ----------
        original_endpoint : str
            Endpoint argument passed to constructor
            
        Returns
        -------
        str
            Returns API URL. If validation fails then throws ConstructionError
        """
        if not isinstance(original_endpoint, str):
            raise ConstructionError(f"Endpoint must be a string, passed: {type(original_endpoint)}")
        
        import re
        match = re.match(r'((?:\w*://)*)(.*)', original_endpoint).groups()
        protocol = match[0] if match[0] == "ws://" else "wss://"
        endpoint = match[1]
        
        url = protocol + endpoint
        if not is_valid_url(url):
            raise ConstructionError(f'Invalid URL:{original_endpoint}')
        
        return url
    
    async def connect(self):
        """
        Establish the WebSocket connection.
        
        Returns
        -------
        WebSocketClientProtocol
            The established WebSocket connection
        """
        if not self.wsconnection and self.wsconnection_from_inside:
            self.events.on_next({'name': 'connect', 'connection_id': self.connection_id})
            self.wsconnection = await websockets.connect(self.api_url)
        
        if self.connected.is_pending():
            self.connected.resolve(True)
        else:
            self.connected = EasyFuture().resolve(True)
        
        # Start the message receiving task
        self.receive_task = asyncio.create_task(self._receive_messages())
        
        return self.wsconnection
    
    async def disconnect(self):
        """
        Disconnect the WebSocket connection.
        """
        self.is_closing = True
        
        if not self.connected.is_resolved():
            return
        
        self.connected = EasyFuture().reject(ConnectionClosedOK(None, Close(1000, 'Closed by disconnect')))
        self.connected.exception()  # Fetch exception to avoid the warning of 'exception never retrieved'
        
        if self.wsconnection_from_inside and self.wsconnection:
            self.events.on_next({'name': 'close', 'connection_id': self.connection_id})
            await self.wsconnection.close()
            self.wsconnection = None
        
        # Cancel tasks
        if self.receive_task and not self.receive_task.done():
            self.receive_task.cancel()
        
        if self.reconnect_task and not self.reconnect_task.done():
            self.reconnect_task.cancel()
    
    async def _receive_messages(self):
        """
        Receive and process messages from the WebSocket.
        """
        await self.connected
        
        while self.connected.is_resolved():
            try:
                data = await self.wsconnection.recv()
                await self._process_message(data)
            except ConnectionClosed as err:
                if self.connected.is_resolved():
                    self.connected = EasyFuture().reject(err)
                    self.connected.exception()  # Call it to hide the warning of 'exception never retrieved'
                
                self.events.on_next({'name': 'connection_closed', 'connection_id': self.connection_id, 'error': err})
                
                # Attempt reconnection if configured to do so
                if self.auto_reconnect and not self.is_closing:
                    self.reconnect_task = asyncio.create_task(self._attempt_reconnection())
                
                break
            except asyncio.CancelledError:
                # Task was cancelled, exit gracefully
                break
            except Exception as err:
                self.events.on_next({'name': 'error', 'connection_id': self.connection_id, 'error': err})
    
    async def _process_message(self, data):
        """
        Process a message received from the WebSocket.
        
        Parameters
        ----------
        data : str
            The raw message data received from the WebSocket
        """
        response = json.loads(data)
        
        self.events.on_next({'name': 'message', 'connection_id': self.connection_id, 'data': response})
        
        req_id = response.get('req_id', None)
        if not req_id or req_id not in self.pending_requests:
            self.events.on_next({'name': 'unmatched_response', 'connection_id': self.connection_id, 'data': response})
            return
        
        request = response.get('echo_req', {})
        
        # Check for error in response
        is_parent_subscription = request and request.get('proposal_open_contract') and not request.get('contract_id')
        if response.get('error') and not is_parent_subscription:
            self.pending_requests[req_id].on_error(ResponseError(response))
            return
        
        # Handle completed subscriptions
        if self.pending_requests[req_id].is_stopped and response.get('subscription'):
            # Source is already marked as completed. In this case we should
            # send a forget request with the subscription id and ignore the response received.
            subs_id = response['subscription']['id']
            self.events.on_next({'name': 'forget_subscription', 'connection_id': self.connection_id, 'subscription_id': subs_id})
            return
        
        # Forward the response to the appropriate Subject
        self.pending_requests[req_id].on_next(response)
    
    async def _attempt_reconnection(self):
        """
        Attempt to reconnect with exponential backoff.
        """
        retry_delay = 1  # Start with 1 second delay
        max_delay = 60   # Maximum delay of 60 seconds
        retries = 0
        
        while retries < self.max_retry_count and not self.is_closing:
            try:
                self.events.on_next({
                    'name': 'reconnecting', 
                    'connection_id': self.connection_id, 
                    'attempt': retries + 1
                })
                
                await asyncio.sleep(retry_delay)
                
                # Try to reconnect
                self.wsconnection = await websockets.connect(self.api_url)
                self.connected = EasyFuture().resolve(True)
                
                # Restart message receiving
                self.receive_task = asyncio.create_task(self._receive_messages())
                
                self.events.on_next({
                    'name': 'reconnected',
                    'connection_id': self.connection_id
                })
                
                return True
            except Exception as err:
                retries += 1
                retry_delay = min(retry_delay * 2, max_delay)  # Exponential backoff
                
                self.events.on_next({
                    'name': 'reconnect_failed', 
                    'connection_id': self.connection_id,
                    'error': err, 
                    'attempt': retries
                })
        
        # All retries failed
        self.events.on_next({
            'name': 'reconnect_max_retries_exceeded',
            'connection_id': self.connection_id
        })
        
        return False
    
    async def send(self, request: dict) -> dict:
        """
        Send a request and get the response.
        
        Parameters
        ----------
        request : dict
            The API request to send
            
        Returns
        -------
        dict
            The API response
        """
        response_future = self.send_and_get_source(request).pipe(op.first(), op.to_future())
        return await response_future
    
    def send_and_get_source(self, request: dict) -> Subject:
        """
        Send a message and return a Subject that will emit the response.
        
        Parameters
        ----------
        request : dict
            The API request to send
            
        Returns
        -------
        Subject
            A Subject that will emit the response
        """
        pending = Subject()
        
        if 'req_id' not in request:
            self.req_id += 1
            request['req_id'] = self.req_id
        
        self.pending_requests[request['req_id']] = pending
        
        async def send_message():
            try:
                await self.connected
                await self.wsconnection.send(json.dumps(request))
                self.events.on_next({'name': 'send', 'connection_id': self.connection_id, 'data': request})
            except Exception as err:
                pending.on_error(err)
        
        asyncio.create_task(send_message())
        return pending