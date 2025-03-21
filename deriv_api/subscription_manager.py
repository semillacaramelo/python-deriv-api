from deriv_api.utils import dict_to_cache_key
from deriv_api.errors import APIError, ConnectionError
from deriv_api.streams_list import streams_list
from reactivex import operators as op
from reactivex.subject import Subject
from reactivex import Observable
from typing import Optional, Union, Dict, List, Any

__pdoc__ = {
    'deriv_api.subscription_manager.SubscriptionManager.complete_subs_by_ids': False,
    'deriv_api.subscription_manager.SubscriptionManager.complete_subs_by_key': False,
    'deriv_api.subscription_manager.SubscriptionManager.create_new_source': False,
    'deriv_api.subscription_manager.SubscriptionManager.get_source': False,
    'deriv_api.subscription_manager.SubscriptionManager.remove_key_on_error': False,
    'deriv_api.subscription_manager.SubscriptionManager.save_subs_id': False,
    'deriv_api.subscription_manager.SubscriptionManager.save_subs_per_msg_type': False,
    'deriv_api.subscription_manager.SubscriptionManager.source_exists': False,
    'deriv_api.subscription_manager.SubscriptionManager.forget': False,
    'deriv_api.subscription_manager.SubscriptionManager.forget_all': False,
    'deriv_api.subscription_manager.get_msg_type': False
}


class SubscriptionManager:
    """
        Subscription Manager - manage subscription channels

        Makes sure there is always only one subscription channel for all requests of subscriptions,
        keeps a history of received values for the subscription of ticks and forgets channels that
        do not have subscribers. It also ensures that subscriptions are revived after connection
        drop/account changed.

        Parameters
        ----------
            api : deriv_api.DerivAPI

        Example
        -------
        - create a new subscription for R_100
        >>> source_tick_50: Observable  = await api.subscribe({'ticks': 'R_50'})
        >>> subscription_id = 0
        >>> def tick_50_callback(data):
        >>>     global subscription_id
        >>>     subscription_id = data['subscription']['id']
        >>>     print(data)
        >>> source_tick_50.subscribe(tick_50_callback)

        - forget all ticks
        >>> await api.forget_all('ticks')

        - forget based on subscription id
        >>> await api.forget(subscription_id)
        
        - subscribe on a specific connection
        >>> source_tick_50 = await api.subscribe({'ticks': 'R_50'}, connection_id=second_conn_id)
        """

    def __init__(self, api):
        self.api = api
        # Organize subscriptions by connection_id
        self.sources_by_connection: Dict[int, Dict[bytes, Observable]] = {}
        self.orig_sources_by_connection: Dict[int, Dict[bytes, Observable]] = {}
        self.subs_id_to_key_by_connection: Dict[int, Dict[str, bytes]] = {}
        self.key_to_subs_id_by_connection: Dict[int, Dict[bytes, str]] = {}
        self.buy_key_to_contract_id_by_connection: Dict[int, Dict[bytes, Dict[str, Any]]] = {}
        self.subs_per_msg_type_by_connection: Dict[int, Dict[str, List[bytes]]] = {}
        
        # Initialize data structures for default connection
        self._ensure_connection_structures(self.api.default_connection)

    def _ensure_connection_structures(self, connection_id: int) -> None:
        """
        Ensure that all data structures for a connection are initialized.
        
        Parameters
        ----------
        connection_id : int
            The ID of the connection to initialize structures for
        """
        if connection_id not in self.sources_by_connection:
            self.sources_by_connection[connection_id] = {}
            self.orig_sources_by_connection[connection_id] = {}
            self.subs_id_to_key_by_connection[connection_id] = {}
            self.key_to_subs_id_by_connection[connection_id] = {}
            self.buy_key_to_contract_id_by_connection[connection_id] = {}
            self.subs_per_msg_type_by_connection[connection_id] = {}

    async def subscribe(self, request: dict, connection_id: Optional[int] = None) -> Observable:
        """
        Subscribe to a given request, returns a stream of new responses,
        Errors should be handled by the user of the stream

        Example
        -------
        >>> ticks = api.subscribe({ 'ticks': 'R_100' })
        >>> ticks.subscribe(call_back_function)

        Parameters
        ----------
        request : dict
            A request object acceptable by the API
        connection_id : Optional[int]
            The connection ID to use. If None, uses the default connection.

        Returns
        -------
            Observable
                An RxPY SObservable
        """
        conn_id = connection_id if connection_id is not None else self.api.default_connection
        self._ensure_connection_structures(conn_id)
        
        if not get_msg_type(request):
            raise APIError('Subscription type is not found in deriv-api')

        if self.source_exists(request, conn_id):
            return self.get_source(request, conn_id)

        new_request: dict = request.copy()
        new_request['subscribe'] = 1
        return await self.create_new_source(new_request, conn_id)

    def get_source(self, request: dict, connection_id: int) -> Optional[Subject]:
        """
        To get the source from the source list stored in sources

        Parameters
        ----------
        request : dict
            Request object
        connection_id : int
            The connection ID to get the source from

        Returns
        -------
            Returns source observable if exists, otherwise returns None
        """
        sources = self.sources_by_connection.get(connection_id, {})
        buy_key_to_contract_id = self.buy_key_to_contract_id_by_connection.get(connection_id, {})
        
        key: bytes = dict_to_cache_key(request)
        if key in sources:
            return sources[key]

        # if we have a buy subscription reuse that for poc
        for c in buy_key_to_contract_id.values():
            if request.get('contract_id') and c.get('contract_id') == request['contract_id']:
                return sources.get(c['buy_key'])

        return None

    def source_exists(self, request: dict, connection_id: int) -> bool:
        """
        Check if a source exists for the given request and connection

        Parameters
        ----------
        request : dict
            A request object
        connection_id : int
            The connection ID to check

        Returns
        -------
            Returns True if source exists, False otherwise
        """
        return self.get_source(request, connection_id) is not None

    async def create_new_source(self, request: dict, connection_id: int) -> Observable:
        """
        Create new source observable, stores it in source list and returns

        Parameters
        ----------
        request : dict
            A request object
        connection_id : int
            The connection ID to create the source for

        Returns
        -------
            Returns source observable
        """
        self._ensure_connection_structures(connection_id)
        
        key: bytes = dict_to_cache_key(request)

        def forget_old_source() -> None:
            key_to_subs_id = self.key_to_subs_id_by_connection.get(connection_id, {})
            if key not in key_to_subs_id:
                return
            # noinspection PyBroadException
            try:
                self.api.add_task(self.forget(key_to_subs_id[key], connection_id), 'forget old subscription')
            except Exception as err:
                self.api.sanity_errors.on_next(err)
            return

        orig_sources = self.orig_sources_by_connection[connection_id]
        sources = self.sources_by_connection[connection_id]
        
        orig_sources[key] = self.api.send_and_get_source(request, connection_id)
        source: Observable = orig_sources[key].pipe(
            op.finally_action(forget_old_source),
            op.share()
        )
        sources[key] = source
        self.save_subs_per_msg_type(request, key, connection_id)

        async def process_response() -> None:
            # noinspection PyBroadException
            try:
                response = await source.pipe(op.first(), op.to_future())
                if request.get('buy'):
                    buy_key_to_contract_id = self.buy_key_to_contract_id_by_connection[connection_id]
                    buy_key_to_contract_id[key] = {
                        'contract_id': response['buy']['contract_id'],
                        'buy_key': key
                    }
                self.save_subs_id(key, response.get('subscription'), connection_id)
            except Exception:
                self.remove_key_on_error(key, connection_id)

        self.api.add_task(process_response(), 'subs manager: process_response')
        return source

    async def forget(self, subs_id: str, connection_id: Optional[int] = None) -> dict:
        """
        Delete the source from source list, clears the subscription detail from subs_id_to_key and key_to_subs_id and
        make api call to unsubscribe the subscription
        
        Parameters
        ----------
        subs_id : str
            Subscription id
        connection_id : Optional[int]
            The connection ID to forget the subscription from. If None, uses the default connection.

        Returns
        -------
            Returns dict - api response for forget call
        """
        conn_id = connection_id if connection_id is not None else self.api.default_connection
        self.complete_subs_by_ids(conn_id, subs_id)
        return await self.api.send({'forget': subs_id}, conn_id)

    async def forget_all(self, *types, connection_id: Optional[int] = None) -> dict:
        """
        Unsubscribe all subscription's of given type. For each subscription, it deletes the source from source list,
        clears the subscription detail from subs_id_to_key and key_to_subs_id. Make api call to unsubscribe all the
        subscriptions of given types.
        
        Parameters
        ----------
        types : Positional argument
            subscription stream types example : ticks, candles
        connection_id : Optional[int]
            The connection ID to forget subscriptions from. If None, uses the default connection.

        Returns
        -------
            Response from API call
        """
        conn_id = connection_id if connection_id is not None else self.api.default_connection
        self._ensure_connection_structures(conn_id)
        
        subs_per_msg_type = self.subs_per_msg_type_by_connection[conn_id]
        
        # To include subscriptions that were automatically unsubscribed
        # for example a proposal subscription is auto-unsubscribed after buy
        for t in types:
            for k in (subs_per_msg_type.get(t) or []):
                self.complete_subs_by_key(k, conn_id)
            subs_per_msg_type[t] = []
            
        return await self.api.send({'forget_all': list(types)}, conn_id)

    def complete_subs_by_ids(self, connection_id: int, *subs_ids):
        """
        Completes the subscription for the given subscription id's - delete the source from source list, clears the
        subscription detail from subs_id_to_key and key_to_subs_id. Mark the original source as complete.

        Parameters
        ----------
        connection_id : int
            The connection ID to complete subscriptions for
        subs_ids : Positional argument
            subscription ids
        """
        self._ensure_connection_structures(connection_id)
        
        subs_id_to_key = self.subs_id_to_key_by_connection[connection_id]
        
        for subs_id in subs_ids:
            if subs_id in subs_id_to_key:
                key = subs_id_to_key[subs_id]
                self.complete_subs_by_key(key, connection_id)

    def save_subs_id(self, key: bytes, subscription: Union[dict, None], connection_id: int):
        """
        Saves the subscription detail in subs_id_to_key and key_to_subs_id

        Parameters
        ----------
        key : bytes
            API call request key. Key for key_to_subs_id
        subscription : dict or None
            subscription details - subscription id
        connection_id : int
            The connection ID to save subscription ID for
        """
        if not subscription:
            return self.complete_subs_by_key(key, connection_id)

        subs_id_to_key = self.subs_id_to_key_by_connection[connection_id]
        key_to_subs_id = self.key_to_subs_id_by_connection[connection_id]
        
        subs_id = subscription['id']
        if subs_id not in subs_id_to_key:
            subs_id_to_key[subs_id] = key
            key_to_subs_id[key] = subs_id

        return None

    def save_subs_per_msg_type(self, request: dict, key: bytes, connection_id: int):
        """
        Save the request's key in subscription per message type

        Parameters
        ----------
        request : dict
            API request object
        key : bytes
            API request key
        connection_id : int
            The connection ID to save subscription for
        """
        subs_per_msg_type = self.subs_per_msg_type_by_connection[connection_id]
        
        msg_type = get_msg_type(request)
        if msg_type:
            subs_per_msg_type[msg_type] = subs_per_msg_type.get(msg_type) or []
            subs_per_msg_type[msg_type].append(key)
        else:
            self.api.sanity_errors.on_next(APIError('Subscription type is not found in deriv-api'))

    def remove_key_on_error(self, key: bytes, connection_id: int):
        """
        Remove ths source from source list, clears the subscription detail from subs_id_to_key and key_to_subs_id.
        Mark the original source as complete.

        Parameters
        ----------
        key : bytes
            Request object key in bytes. Used to identify the subscription stored in key_to_subs_id
        connection_id : int
            The connection ID to remove key for
        """
        return lambda: self.complete_subs_by_key(key, connection_id)

    def complete_subs_by_key(self, key: bytes, connection_id: int):
        """
        Identify the source from source list based on request object key and removes it. Clears the subscription detail
        from subs_id_to_key and key_to_subs_id. Mark the original source as complete.

        Parameters
        ----------
        key : bytes
            Request object key to identify the subscription stored in key_to_subs_id
        connection_id : int
            The connection ID to complete subscription for
        """
        self._ensure_connection_structures(connection_id)
        
        sources = self.sources_by_connection[connection_id]
        orig_sources = self.orig_sources_by_connection[connection_id]
        key_to_subs_id = self.key_to_subs_id_by_connection[connection_id]
        subs_id_to_key = self.subs_id_to_key_by_connection[connection_id]
        buy_key_to_contract_id = self.buy_key_to_contract_id_by_connection[connection_id]
        
        if not key or key not in sources:
            return

        # Delete the source
        orig_source = orig_sources.pop(key, None)
        del sources[key]

        try:
            # Delete the subs id if exist
            if key in key_to_subs_id:
                subs_id = key_to_subs_id[key]
                del subs_id_to_key[subs_id]
                # Delete the key
                del key_to_subs_id[key]

            # Delete the buy key to contract_id mapping
            if key in buy_key_to_contract_id:
                del buy_key_to_contract_id[key]
        except KeyError:
            pass

        # Mark the source complete
        if orig_source:
            orig_source.on_completed()
            orig_source.dispose()


def get_msg_type(request: dict) -> str:
    """
    Get message type by request

    Parameters
    ----------
    request : dict
        Request

    Returns
    -------
        Returns the next item from the iterator
    """
    return next((x for x in streams_list if x in request), None)
