# python-deriv-api
A python implementation of deriv api library.

[![PyPI](https://img.shields.io/pypi/v/python_deriv_api.svg?style=flat-square)](https://pypi.org/project/python_deriv_api/)
[![Python 3.9.6](https://img.shields.io/badge/python-3.9.6-blue.svg)](https://www.python.org/download/releases/3.9.6/)
[![Test status](https://github.com/deriv-com/python-deriv-api/actions/workflows/build.yml/badge.svg)](https://github.com/deriv-com/python-deriv-api)

Go through [api.deriv.com](https://api.deriv.com/) to know simple easy steps on how to register and get access.
Use this all-in-one python library to set up and make your app running or you can extend it.

### Requirement
Python (3.9.6 or higher is recommended) and pip3

Note: There is bug in 'websockets' package with python 3.9.7, hope that will be fixed in 3.9.8 as mentioned in
https://github.com/aaugustin/websockets/issues/1051. Please exclude python 3.9.7.

# Installation

`python3 -m pip install python_deriv_api`

# Usage
This is basic deriv-api python library which helps to make websockets connection and
deal the API calls (including subscription).

Import the module

```
from deriv_api import DerivAPI
```

Access 

```
api = DerivAPI(endpoint='ws://...', app_id=1234);
response = await api.ping({'ping': 1})
print(response) 
```

## Creating a websockets connection and API instantiation
You can either create an instance of websockets and pass it as connection
    or
pass the endpoint and app_id to the constructor to create the connection for you.

If you pass the connection it's up to you to reconnect in case the connection drops (cause API doesn't know how to create the same connection).


- Pass the arguments needed to create a connection:
```
   api = DerivAPI(endpoint='ws://...', app_id=1234);
```

- create and use a previously opened connection:
```
   connection = await websockets.connect('ws://...')
   api = DerivAPI(connection=connection)
```

## Multi-Connection Support
Python Deriv API now supports multiple concurrent WebSocket connections, allowing you to:

- Connect to multiple Deriv API endpoints simultaneously
- Send requests through specific connections
- Subscribe to market data on dedicated connections
- Implement connection-specific error handling

### Creating and Using Multiple Connections

```python
import asyncio
from deriv_api import DerivAPI

async def main():
    # Create the API with a default connection
    api = DerivAPI(endpoint='ws.derivws.com', app_id=1234)
    
    # Create an additional connection for market data
    market_conn = api.create_connection(
        endpoint='ws.derivws.com', 
        app_id=1234,
        auto_reconnect=True
    )
    
    # Use the default connection for account operations
    account_info = await api.authorize({"authorize": "YOUR_API_TOKEN"})
    
    # Use the market connection for market data
    ticks = await api.subscribe({"ticks": "R_100"}, connection_id=market_conn)
    ticks.subscribe(lambda tick: print(f"Tick: {tick['tick']['quote']}"))
    
    # Close a specific connection when done
    await api.disconnect(connection_id=market_conn)

asyncio.run(main())
```

For more detailed examples and documentation on the multi-connection feature, see [Multi-Connection Support](docs/multi_connection.md).

# Documentation

#### API reference
The complete API reference is hosted [here](https://deriv-com.github.io/python-deriv-api/)

Examples [here](https://github.com/deriv-com/python-deriv-api/tree/master/examples)

# Development
```
git clone https://github.com/deriv-com/python-deriv-api
cd python-deriv-api
```
Setup environment
```
make setup
```

Setup environment and run test
```
make all
```

#### Run test

```
python setup.py pytest
```

or

```
pytest
```

or

```
make test
```
#### Generate documentations

Generate html version of the docs and publish it to gh-pages

```
make gh-pages
```

#### Build the package
```
make build
```
#### Run examples

set token and run example

```
export DERIV_TOKEN=xxxTokenxxx
PYTHONPATH=. python3 examples/simple_bot1.py
```

# Example with Multiple Connections

```
export DERIV_TOKEN=xxxTokenxxx
PYTHONPATH=. python3 examples/multi_connection.py
```

