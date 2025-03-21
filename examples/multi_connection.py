import asyncio
from deriv_api import DerivAPI

async def main():
    """
    Example demonstrating the usage of multiple WebSocket connections.
    
    This example shows how to:
    1. Create a DerivAPI instance with a default connection
    2. Create additional connections
    3. Send requests through different connections
    4. Subscribe to market data on different connections
    5. Handle connection events
    """
    # Create the API with a default connection
    api = DerivAPI(endpoint='ws.derivws.com', app_id=1089, auto_reconnect=True)
    
    # Set up an error handler to monitor connection issues
    api.connection_manager.monitor_errors().subscribe(
        lambda event: print(f"Error on connection {event.get('connection_id')}: {event.get('name')}")
    )
    
    # Create a second connection for market data
    market_conn = api.create_connection(
        endpoint='ws.derivws.com',
        app_id=1089,
        auto_reconnect=True
    )
    
    print(f"Created connections: Default={api.default_connection}, Market={market_conn}")
    
    # Ping via the default connection
    ping_response = await api.ping()
    print(f"Default connection ping response: {ping_response}")
    
    # Ping via the market data connection
    ping_response_market = await api.ping(connection_id=market_conn)
    print(f"Market connection ping response: {ping_response_market}")
    
    # Subscribe to ticks for R_100 using the market connection
    ticks = await api.subscribe({"ticks": "R_100"}, connection_id=market_conn)
    
    # Handle tick data
    def process_tick(tick_data):
        print(f"Received tick: {tick_data['tick']['quote']} on connection {market_conn}")
    
    ticks.subscribe(
        on_next=process_tick,
        on_error=lambda err: print(f"Error in subscription: {err}"),
        on_completed=lambda: print("Subscription completed")
    )
    
    # Wait for some ticks to arrive
    await asyncio.sleep(5)
    
    # Forget all subscriptions on the market connection
    await api.forget_all("ticks", connection_id=market_conn)
    print("Unsubscribed from ticks")
    
    # Disconnect the market connection
    await api.disconnect(connection_id=market_conn)
    print(f"Disconnected connection {market_conn}")
    
    # Disconnect the default connection
    await api.disconnect()
    print("Disconnected default connection")
    
    # Clean up resources
    await api.clear()

if __name__ == "__main__":
    asyncio.run(main())