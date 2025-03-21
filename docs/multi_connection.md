# Multi-Connection Support in Python Deriv API

## Overview

The Python Deriv API now supports multiple concurrent WebSocket connections to the Deriv servers. This feature allows you to:

- Connect to multiple Deriv API endpoints simultaneously
- Send requests through specific connections
- Subscribe to market data on dedicated connections
- Implement connection-specific error handling
- Optimize performance by separating different types of operations

## Key Concepts

### Connections

Each connection represents a separate WebSocket connection to the Deriv API. Connections are identified by a numeric ID and are managed through the `ConnectionManager` class.

- The first connection created during initialization is the **default connection**
- Additional connections can be created as needed
- Each connection has its own state, event stream, and subscription management

### Connection Manager

The `ConnectionManager` handles the creation, tracking, and management of connections. It provides methods to:

- Create new connections
- Retrieve existing connections
- Monitor connection events and errors

## Basic Usage

### Creating and Managing Connections

```python
import asyncio
from deriv_api import DerivAPI

async def main():
    # Create the API with a default connection
    api = DerivAPI(endpoint='ws.derivws.com', app_id=YOUR_APP_ID)
    
    # Create an additional connection
    second_conn_id = api.create_connection(
        endpoint='ws.derivws.com',
        app_id=YOUR_APP_ID,
        auto_reconnect=True
    )
    
    # Use the default connection
    ping_response = await api.ping()
    
    # Use the second connection
    ping_response2 = await api.ping(connection_id=second_conn_id)
    
    # Disconnect specific connection
    await api.disconnect(connection_id=second_conn_id)
    
    # Disconnect default connection
    await api.disconnect()
    
    # Disconnect all connections
    await api.disconnect_all()

# Run the example
asyncio.run(main())
```

### Subscribing to Market Data on Different Connections

```python
# Create a dedicated connection for market data
market_conn = api.create_connection(
    endpoint='ws.derivws.com',
    app_id=YOUR_APP_ID,
    auto_reconnect=True
)

# Subscribe to ticks using the market connection
ticks = await api.subscribe({"ticks": "R_100"}, connection_id=market_conn)

# Handle tick data
def process_tick(tick_data):
    print(f"Received tick: {tick_data['tick']['quote']}")

ticks.subscribe(
    on_next=process_tick,
    on_error=lambda err: print(f"Error in subscription: {err}"),
    on_completed=lambda: print("Subscription completed")
)

# Forget all subscriptions on the market connection
await api.forget_all("ticks", connection_id=market_conn)
```

### Monitoring Connection Events and Errors

```python
# Monitor all connection errors
api.connection_manager.monitor_errors().subscribe(
    lambda event: print(f"Error on connection {event.get('connection_id')}: {event.get('name')}")
)

# Monitor all connection events
api.connection_manager.monitor_events().subscribe(
    lambda event: print(f"Event on connection {event.get('connection_id')}: {event.get('name')}")
)
```

## Advanced Usage

### Auto-Reconnection

Connections can be configured to automatically reconnect when disconnected:

```python
conn_id = api.create_connection(
    endpoint='ws.derivws.com',
    app_id=YOUR_APP_ID,
    auto_reconnect=True,
    max_retry_count=5  # Maximum number of reconnection attempts
)
```

### Connection-Specific Configuration

Each connection can have its own configuration:

```python
# Create a connection with different app_id
alt_conn = api.create_connection(
    endpoint='ws.derivws.com',
    app_id=DIFFERENT_APP_ID,
    lang='FR',  # Different language
    brand='binary'  # Different brand
)
```

### Optimizing for Different Use Cases

You can optimize your application by dedicating connections to specific purposes:

```python
# Create a connection for high-frequency market data
market_conn = api.create_connection(endpoint='ws.derivws.com', app_id=YOUR_APP_ID)

# Create a connection for account operations
account_conn = api.create_connection(endpoint='ws.derivws.com', app_id=YOUR_APP_ID)

# Create a connection for trading operations
trading_conn = api.create_connection(endpoint='ws.derivws.com', app_id=YOUR_APP_ID)

# Subscribe to multiple market symbols on the market connection
symbols = ["R_100", "EURUSD", "GBPUSD"]
subscriptions = []

for symbol in symbols:
    subscription = await api.subscribe({"ticks": symbol}, connection_id=market_conn)
    subscriptions.append(subscription)

# Use the account connection for account-related operations
account_info = await api.authorize({"authorize": "YOUR_API_TOKEN"}, connection_id=account_conn)

# Use the trading connection for trading operations
buy_response = await api.buy({"buy": "1", "price": 100}, connection_id=trading_conn)
```

## Backward Compatibility

The multi-connection feature is designed to be fully backward compatible with existing code. If you don't specify a connection ID, all operations will use the default connection, maintaining the same behavior as previous versions.

## Best Practices

1. **Use dedicated connections for different purposes**: Separate market data subscriptions from account operations and trading to improve performance and reliability.

2. **Enable auto-reconnect for critical connections**: Set `auto_reconnect=True` for connections that need to be maintained.

3. **Monitor connection errors**: Subscribe to connection errors to detect and handle issues.

4. **Clean up unused connections**: Call `disconnect()` when a connection is no longer needed to free resources.

5. **Use consistent connection IDs**: Keep track of your connection IDs and use them consistently throughout your application.

## Error Handling

The new `ConnectionError` class is used for connection-specific errors:

```python
from deriv_api.errors import ConnectionError

try:
    response = await api.ping(connection_id=999)  # Non-existent connection
except ConnectionError as e:
    print(f"Connection error: {e}")
```