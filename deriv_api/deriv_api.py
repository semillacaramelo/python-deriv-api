import asyncio
import json
import logging
import re
from asyncio import Future
from typing import Dict, Optional, Union, Coroutine, Any, List

import websockets
from reactivex import operators as op
from reactivex.subject import Subject
from reactivex import Observable
from websockets.legacy.client import WebSocketClientProtocol
from websockets.exceptions import ConnectionClosedOK, ConnectionClosed
from websockets.frames import Close

from deriv_api.cache import Cache
from deriv_api.easy_future import EasyFuture
from deriv_api.deriv_api_calls import DerivAPICalls
from deriv_api.errors import APIError, ConstructionError, ResponseError, AddedTaskError, ConnectionError
from deriv_api.in_memory import InMemory
from deriv_api.subscription_manager import SubscriptionManager
from deriv_api.utils import is_valid_url
from deriv_api.middlewares import MiddleWares
from deriv_api.connection_manager import ConnectionManager

# TODO NEXT subscribe is not calling deriv_api_calls. that's , args not verified. can we improve it ?

logging.basicConfig(
    format="%(asctime)s %(message)s",
    level=logging.ERROR
)

__pdoc__ = {
    'deriv_api.deriv_api.DerivAPI.send_and_get_source': False,
    'deriv_api.deriv_api.DerivAPI.api_connect': False,
    'deriv_api.deriv_api.DerivAPI.get_url': False,
    'deriv_api.deriv_api.DerivAPI.add_task': False,
    'deriv_api.deriv_api.DerivAPI.delete_from_expect_response': False,
    'deriv_api.deriv_api.DerivAPI.disconnect': False,
    'deriv_api.deriv_api.DerivAPI.send': False,
    'deriv_api.deriv_api.DerivAPI.wsconnection': False,
    'deriv_api.deriv_api.DerivAPI.storage': False,
}


class DerivAPI(DerivAPICalls):
    """
    The minimum functionality provided by DerivAPI, provides direct calls to the API.
    `api.cache` is available if you want to use the cached data

    Examples
    --------
    - Pass the arguments needed to create a connection:
    >>> api = DerivAPI(endpoint='ws://...', app_id=1234)

    - create and use a previously opened connection:
    >>> connection = await websockets.connect('ws://...')
    >>> api = DerivAPI(connection=connection)
    
    - create multiple connections:
    >>> api = DerivAPI(endpoint='ws://...', app_id=1234)
    >>> second_conn_id = api.create_connection(endpoint='ws://...', app_id=5678)
    >>> response = await api.ping(connection_id=second_conn_id)

    Parameters
    ----------
        options : dict with following keys
            connection : websockets.WebSocketClientProtocol
                A ready to use connection
            endpoint : String
                API server to connect to
            app_id : String
                Application ID of the API user
            lang : String
                Language of the API communication
            brand : String
                Brand name
            middleware : MiddleWares
                middlewares to call on certain API actions. Now two middlewares are supported: sendWillBeCalled and
                sendIsCalled
            auto_reconnect : bool
                Whether to automatically reconnect on connection loss
                
    Properties
    ----------
    cache: Cache
        Temporary cache default to InMemory
    storage : Cache
        If specified, uses a more persistent cache (local storage, etc.)
    events: Observable
        An Observable object that will send data when events like 'connect', 'send', 'message' happen
    """

    storage: None

    def __init__(self, **options: Any) -> None:
        # First, create the connection manager and default connection
        self.connection_manager = ConnectionManager()
        
        # Extract common options
        endpoint = options.get('endpoint', 'ws.derivws.com')
        app_id = options.get('app_id')
        lang = options.get('lang', 'EN')
        brand = options.get('brand', '')
        auto_reconnect = options.get('auto_reconnect', False)
        
        # Set up cache and storage
        cache = options.get('cache', InMemory())
        storage: any = options.get('storage')
        self.middlewares: MiddleWares = options.get('middlewares', MiddleWares())
        
        # Set up global event observable
        self.events: Subject = Subject()
        
        # Connect connection manager events to API events for backward compatibility
        self.connection_manager.events_subject.subscribe(
            lambda event: self._handle_connection_event(event)
        )
        
        # Forward errors to sanity_errors
        self.sanity_errors: Subject = Subject()
        self.connection_manager.error_subject.subscribe(
            lambda event: self.sanity_errors.on_next(event.get('error', APIError("Unknown error")))
        )
        
        # Create the default connection
        if options.get('connection'):
            # Use the provided connection
            conn_options = {
                'connection': options.get('connection'),
                'lang': lang,
                'brand': brand,
                'auto_reconnect': auto_reconnect
            }
        else:
            # Create a new connection
            if not app_id:
                raise ConstructionError('An app_id is required to connect to the API')
            
            conn_options = {
                'endpoint': endpoint,
                'app_id': app_id,
                'lang': lang,
                'brand': brand,
                'auto_reconnect': auto_reconnect
            }
        
        self.default_connection = self.connection_manager.create_connection(**conn_options)
        
        # Set up storage and cache
        self.storage: Optional[Cache] = None
        if storage:
            self.storage = Cache(self, storage)
        # If we have the storage look that one up
        self.cache = Cache(self.storage if self.storage else self, cache)
        
        # Set up other state
        self.subscription_manager: SubscriptionManager = SubscriptionManager(self)
        self.expect_response_types = {}
        
        # Connect the default connection
        self.add_task(self._connect_default(), 'connect_default')
    
    async def _connect_default(self):
        """
        Connect the default connection.
        """
        connection = self.connection_manager.get_connection(self.default_connection)
        if connection:
            await connection.connect()
    
    def _handle_connection_event(self, event: Dict[str, Any]):
        """
        Handle events from connections.
        """
        # Only forward events from the default connection for backward compatibility
        if event.get('connection_id') == self.default_connection:
            # Map new event names to old event names for backward compatibility
            event_name = event.get('name')
            
            if event_name == 'message':
                self.events.on_next({'name': 'message', 'data': event.get('data')})
            elif event_name == 'send':
                self.events.on_next({'name': 'send', 'data': event.get('data')})
            elif event_name == 'connect':
                self.events.on_next({'name': 'connect'})
            elif event_name in ['close', 'connection_closed']:
                self.events.on_next({'name': 'close'})
    
    def create_connection(self, **options) -> int:
        """
        Create a new connection.
        
        Parameters
        ----------
        **options
            Connection options. See ConnectionManager.create_connection for details.
            
        Returns
        -------
        int
            The ID of the newly created connection
        """
        return self.connection_manager.create_connection(**options)
    
    def get_url(self, original_endpoint: str) -> Union[str, ConstructionError]:
        """
        Validate and return the url

        Parameters
        ----------
        original_endpoint : str
            endpoint argument passed to constructor

        Returns
        -------
            Returns api url. If validation fails then throws constructionError
        """
        if not isinstance(original_endpoint, str):
            raise ConstructionError(f"Endpoint must be a string, passed: {type(original_endpoint)}")

        match = re.match(r'((?:\w*://)*)(.*)', original_endpoint).groups()
        protocol = match[0] if match[0] == "ws://" else "wss://"
        endpoint = match[1]

        url = protocol + endpoint
        if not is_valid_url(url):
            raise ConstructionError(f'Invalid URL:{original_endpoint}')

        return url

    async def send(self, request: dict, connection_id: Optional[int] = None) -> dict:
        """
        Send the API call and returns response

        Parameters
        ----------
        request : dict
            API request
        connection_id : Optional[int]
            The connection ID to use. If None, uses the default connection.

        Returns
        -------
            API response
        """
        # Apply middleware
        send_will_be_called = self.middlewares.call('sendWillBeCalled', {'request': request})
        if send_will_be_called:
            return send_will_be_called
        
        # Use the specified connection or default
        conn_id = connection_id if connection_id is not None else self.default_connection
        connection = self.connection_manager.get_connection(conn_id)
        
        if not connection:
            raise ConnectionError(f"Connection {conn_id} not found")
        
        # Send the request
        response = await connection.send(request)
        
        # Cache the response
        self.cache.set(request, response)
        if self.storage:
            self.storage.set(request, response)
        
        # Apply middleware
        send_is_called = self.middlewares.call('sendIsCalled', {'response': response, 'request': request})
        if send_is_called:
            return send_is_called
        
        return response

    def send_and_get_source(self, request: dict, connection_id: Optional[int] = None) -> Subject:
        """
        Send message and returns Subject

        Parameters
        ----------
        request : dict
            API request
        connection_id : Optional[int]
            The connection ID to use. If None, uses the default connection.

        Returns
        -------
            Returns the Subject
        """
        # Use the specified connection or default
        conn_id = connection_id if connection_id is not None else self.default_connection
        connection = self.connection_manager.get_connection(conn_id)
        
        if not connection:
            raise ConnectionError(f"Connection {conn_id} not found")
        
        # Send the request and return the source
        return connection.send_and_get_source(request)

    async def subscribe(self, request: dict, connection_id: Optional[int] = None) -> Observable:
        """
        Subscribe to a given request

        Parameters
        ----------
            request : dict
                Subscribe request
            connection_id : Optional[int]
                The connection ID to use. If None, uses the default connection.

        Example
        -------
        >>> proposal_subscription = api.subscribe({"proposal_open_contract": 1, "contract_id": 11111111, "subscribe": 1})

        Returns
        -------
            Observable
        """
        return await self.subscription_manager.subscribe(request, connection_id)

    async def forget(self, subs_id: str, connection_id: Optional[int] = None) -> dict:
        """
        Forget / unsubscribe the specific subscription.

        Parameters
        ----------
            subs_id : str
                subscription id
            connection_id : Optional[int]
                The connection ID to use. If None, uses the default connection.

        Returns
        -------
            Returns dict
        """
        return await self.subscription_manager.forget(subs_id, connection_id)

    async def forget_all(self, *types, connection_id: Optional[int] = None) -> dict:
        """
        Forget / unsubscribe the subscriptions of given types.

        Possible values are: 'ticks', 'candles', 'proposal', 'proposal_open_contract', 'balance', 'transaction'

        Parameter
        ---------
            *types : Any number of non-keyword arguments
            connection_id : Optional[int]
                The connection ID to use. If None, uses the default connection.
                
        Example
        -------
            api.forget_all("ticks", "candles")

        Returns
        -------
            Returns the dict
        """
        return await self.subscription_manager.forget_all(*types, connection_id=connection_id)

    async def disconnect(self, connection_id: Optional[int] = None) -> None:
        """
        Disconnect the websockets connection

        Parameters
        ----------
        connection_id : Optional[int]
            The connection ID to disconnect. If None, disconnects the default connection.
        """
        if connection_id is not None:
            # Disconnect the specified connection
            connection = self.connection_manager.get_connection(connection_id)
            if connection:
                await connection.disconnect()
        else:
            # Disconnect the default connection
            connection = self.connection_manager.get_connection(self.default_connection)
            if connection:
                await connection.disconnect()

    async def disconnect_all(self) -> None:
        """
        Disconnect all websocket connections.
        """
        await self.connection_manager.disconnect_all()

    def expect_response(self, *msg_types):
        """
        Expect specific message types

        Parameters
        ----------
            *msg_types : variable number of non-key string argument
                Expect these types to be received by the API
        Returns
        -------
             Resolves to a single response or an array        
        """
        for msg_type in msg_types:
            if msg_type not in self.expect_response_types:
                future: Future = asyncio.get_event_loop().create_future()

                async def get_by_msg_type(a_msg_type):
                    nonlocal future
                    val = await self.cache.get_by_msg_type(a_msg_type)
                    if not val and self.storage:
                        val = self.storage.get_by_msg_type(a_msg_type)
                    if val:
                        future.set_result(val)

                self.add_task(get_by_msg_type(msg_type), 'get_by_msg_type')
                self.expect_response_types[msg_type] = future

        # expect on a single response returns a single response, not a list
        if len(msg_types) == 1:
            return self.expect_response_types[msg_types[0]]

        return asyncio.gather(*[self.expect_response_types[t] for t in msg_types])

    def delete_from_expect_response(self, request: dict):
        """
        Delete the given request message type from expect_response_types

        Parameters
        ----------
        request : dict

        """
        response_type = None
        for k in self.expect_response_types.keys():
            if k in request:
                response_type = k
                break

        if response_type and self.expect_response_types[response_type] \
                and self.expect_response_types[response_type].done():
            del self.expect_response_types[response_type]

    def add_task(self, coroutine: Coroutine, name: str) -> None:
        """
        Add coroutine object to execution

        Parameters
        ----------
        coroutine : Coroutine
            Coroutine object
        name: str
            name of the Coroutine

        """
        name = 'deriv_api:' + name

        async def wrap_coro(coru: Coroutine, pname: str) -> None:
            try:
                await coru
            except Exception as err:
                self.sanity_errors.on_next(AddedTaskError(err, pname))

        asyncio.create_task(wrap_coro(coroutine, name), name=name)

    async def clear(self):
        """
        Disconnect and cancel all the tasks        
        """
        await self.disconnect_all()
        for task in asyncio.all_tasks():
            if re.match(r"^deriv_api:", task.get_name()):
                task.cancel('deriv api ended')
