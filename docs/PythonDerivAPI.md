# Python Deriv API Guide

## Introduction and Overview

The `python-deriv-api` library is a Python implementation of the Deriv API, designed to facilitate seamless interaction with the Deriv trading platform. It provides a comprehensive set of tools for developers to build applications that require real-time market data, trading capabilities, and account management. The library is intended for developers who need to integrate Deriv's trading functionalities into their Python applications.

### Key Features
- Asynchronous API communication using WebSockets
- Reactive programming model using RxPY
- Real-time data subscriptions
- Comprehensive API method coverage
- Connection management with automatic reconnection

### Current Version
- Version: 0.1.7
- License: MIT

## Installation and Setup

### System Requirements
- Python 3.9.6 or higher (excluding 3.9.7)
- pip (Python package installer)

### Installing the Library

To install the `python-deriv-api` library, use the following pip command:

```sh
python3 -m pip install python_deriv_api
```

### Alternative Installation Methods

You can also install the library directly from the source code. First, clone the repository:

```sh
git clone https://github.com/deriv-com/python-deriv-api
cd python-deriv-api
```

Then, install the library using pip:

```sh
python3 -m pip install .
```

### Troubleshooting Installation Issues

- Ensure you are using a compatible Python version (3.9.6 or higher, excluding 3.9.7).
- Verify that pip is installed and updated to the latest version.
- Check for any network issues that might be preventing the installation.

## Authentication and Authorization

The `python-deriv-api` library supports authentication via API tokens. To interact with the Deriv API, you need to obtain an API token from your Deriv account.

### Obtaining an API Token
1. Log in to your Deriv account.
2. Navigate to the API token section in your account settings.
3. Generate a new API token with the required permissions.
4. Copy the generated token for use in your application.

### Authenticating with the API Token

To authenticate with the Deriv API, pass the API token when creating an instance of the `DerivAPI` class:

```python
from deriv_api import DerivAPI

api = DerivAPI(endpoint='wss://ws.binaryws.com/websockets/v3', app_id='your_app_id', token='your_api_token')
```

### Best Practices for Managing API Tokens
- Store API tokens securely, avoiding hardcoding them in your source code.
- Use environment variables to manage API tokens.
- Regenerate API tokens periodically and update your application accordingly.

## Core Modules and Classes

### DerivAPI Class

The `DerivAPI` class is the main entry point for interacting with the Deriv API. It handles WebSocket connections, request/response management, and provides methods for various API calls.

#### Class Diagram

```plaintext
+----------------+
|   DerivAPI     |
+----------------+
| - wsconnection |
| - cache        |
| - storage      |
| - events       |
+----------------+
| + send()       |
| + subscribe()  |
| + forget()     |
| + disconnect() |
+----------------+
```

#### Methods and Attributes

- `send(request: dict) -> dict`: Sends an API request and returns the response.
- `subscribe(request: dict) -> Observable`: Subscribes to a real-time data stream.
- `forget(subs_id: str) -> dict`: Unsubscribes from a specific subscription.
- `disconnect() -> None`: Disconnects the WebSocket connection.

#### Example Usage

```python
from deriv_api import DerivAPI

api = DerivAPI(endpoint='wss://ws.binaryws.com/websockets/v3', app_id='your_app_id', token='your_api_token')

# Send a ping request
response = await api.send({'ping': 1})
print(response)

# Subscribe to ticks for a specific symbol
ticks = await api.subscribe({'ticks': 'R_100'})
ticks.subscribe(lambda data: print(data))
```

### SubscriptionManager Class

The `SubscriptionManager` class manages subscription channels for real-time data. It ensures that there is only one subscription channel for each request type and handles the lifecycle of subscriptions.

#### Class Diagram

```plaintext
+-----------------------+
|  SubscriptionManager  |
+-----------------------+
| - api                 |
| - sources             |
| - orig_sources        |
| - subs_id_to_key      |
| - key_to_subs_id      |
| - buy_key_to_contract_id |
| - subs_per_msg_type   |
+-----------------------+
| + subscribe()         |
| + forget()            |
| + forget_all()        |
| + get_source()        |
| + source_exists()     |
| + create_new_source() |
+-----------------------+
```

#### Methods and Attributes

- `subscribe(request: dict) -> Observable`: Subscribes to a given request and returns a stream of new responses.
- `forget(subs_id: str) -> dict`: Unsubscribes from a specific subscription.
- `forget_all(*types) -> dict`: Unsubscribes from all subscriptions of given types.
- `get_source(request: dict) -> Optional[Subject]`: Retrieves the source from the source list.
- `source_exists(request: dict) -> bool`: Checks if a source exists for the given request.
- `create_new_source(request: dict) -> Observable`: Creates a new source observable and stores it in the source list.

#### Example Usage

```python
from deriv_api import DerivAPI

api = DerivAPI(endpoint='wss://ws.binaryws.com/websockets/v3', app_id='your_app_id', token='your_api_token')

# Subscribe to ticks for a specific symbol
ticks = await api.subscribe({'ticks': 'R_100'})
ticks.subscribe(lambda data: print(data))

# Unsubscribe from a specific subscription
await api.forget('subscription_id')

# Unsubscribe from all tick subscriptions
await api.forget_all('ticks')
```

## API Endpoints and Functionality

### Market Data Endpoints

#### Active Symbols

- **HTTP Method**: GET
- **URL**: `wss://ws.binaryws.com/websockets/v3?app_id=your_app_id&active_symbols=brief`
- **Request Parameters**:
  - `active_symbols`: (str) If you use `brief`, only a subset of fields will be returned.
  - `landing_company_short`: (str) [Optional] If specified, only symbols available for trading by that landing company will be returned.
  - `product_type`: (str) [Optional] If specified, only symbols that can be traded through that product type will be returned.

#### Example Request

```json
{
  "active_symbols": "brief",
  "landing_company_short": "svg",
  "product_type": "basic"
}
```

#### Example Response

```json
[
  {
    "symbol": "R_100",
    "display_name": "Volatility 100 Index",
    "market": "synthetic_index",
    "submarket": "random_index"
  }
]
```

### Trading Endpoints

#### Buy Contract

- **HTTP Method**: POST
- **URL**: `wss://ws.binaryws.com/websockets/v3?app_id=your_app_id&buy`
- **Request Parameters**:
  - `buy`: (str) The ID received from a Price Proposal (proposal call).
  - `price`: (float) Maximum price at which to purchase the contract.
  - `parameters`: (dict) Additional parameters for the contract.

#### Example Request

```json
{
  "buy": "1",
  "price": 100.0,
  "parameters": {
    "amount": 10,
    "basis": "stake",
    "contract_type": "CALL",
    "currency": "USD",
    "duration": 5,
    "duration_unit": "t",
    "symbol": "R_100"
  }
}
```

#### Example Response

```json
{
  "buy": {
    "contract_id": 123456789,
    "longcode": "Win payout if Volatility 100 Index is strictly higher than entry spot at 5 ticks after contract start time.",
    "payout": 195.0,
    "start_time": 1616161616,
    "transaction_id": 987654321
  }
}
```

### Account Management Endpoints

#### Get Account Balance

- **HTTP Method**: GET
- **URL**: `wss://ws.binaryws.com/websockets/v3?app_id=your_app_id&balance`
- **Request Parameters**:
  - `balance`: (int) Must be 1.
  - `account`: (str) [Optional] If set to `all`, return the balances of all accounts one by one.

#### Example Request

```json
{
  "balance": 1,
  "account": "all"
}
```

#### Example Response

```json
{
  "balance": {
    "balance": 1000.0,
    "currency": "USD"
  }
}
```

## Data Structures and Models

### Contract Parameters

The `ContractParameters` model defines the parameters required to create a contract.

#### Attributes

- `amount`: (float) The amount to stake.
- `basis`: (str) The basis for the contract (e.g., `stake`, `payout`).
- `contract_type`: (str) The type of contract (e.g., `CALL`, `PUT`).
- `currency`: (str) The currency for the contract.
- `duration`: (int) The duration of the contract.
- `duration_unit`: (str) The unit of duration (e.g., `t` for ticks).
- `symbol`: (str) The symbol for the contract.

#### Example Usage

```python
contract_params = {
  "amount": 10,
  "basis": "stake",
  "contract_type": "CALL",
  "currency": "USD",
  "duration": 5,
  "duration_unit": "t",
  "symbol": "R_100"
}
```

## Error Handling and Exception Management

The `python-deriv-api` library includes robust error handling mechanisms to ensure that exceptions are properly managed and communicated to the user.

### Common Exceptions

- `APIError`: Raised for general API errors.
- `ConstructionError`: Raised when there is an error in constructing the API request.
- `ResponseError`: Raised when the API response contains an error.
- `AddedTaskError`: Raised when there is an error in adding a task.

### Handling Exceptions

To handle exceptions, use try-except blocks around your API calls. Here is an example:

```python
from deriv_api import DerivAPI, APIError, ConstructionError, ResponseError

api = DerivAPI(endpoint='wss://ws.binaryws.com/websockets/v3', app_id='your_app_id', token='your_api_token')

try:
    response = await api.send({'ping': 1})
    print(response)
except APIError as e:
    print(f"APIError: {e}")
except ConstructionError as e:
    print(f"ConstructionError: {e}")
except ResponseError as e:
    print(f"ResponseError: {e}")
except Exception as e:
    print(f"Unexpected error: {e}")
```

## Usage Examples and Tutorials

### Fetching Market Data

This example demonstrates how to fetch market data for a specific symbol.

```python
from deriv_api import DerivAPI

api = DerivAPI(endpoint='wss://ws.binaryws.com/websockets/v3', app_id='your_app_id', token='your_api_token')

# Fetch active symbols
response = await api.send({'active_symbols': 'brief'})
print(response)
```

### Placing a Buy Order

This example demonstrates how to place a buy order.

```python
from deriv_api import DerivAPI

api = DerivAPI(endpoint='wss://ws.binaryws.com/websockets/v3', app_id='your_app_id', token='your_api_token')

# Place a buy order
response = await api.send({
    'buy': 1,
    'price': 100.0,
    'parameters': {
        'amount': 10,
        'basis': 'stake',
        'contract_type': 'CALL',
        'currency': 'USD',
        'duration': 5,
        'duration_unit': 't',
        'symbol': 'R_100'
    }
})
print(response)
```

## Advanced Topics

### Rate Limiting and Throttling

The `python-deriv-api` library does not implement rate limiting or throttling by default. However, you can implement your own rate limiting using libraries such as `ratelimit` or `asyncio` to ensure that you do not exceed the API rate limits.

### WebSocket Integration

The library uses the `websockets` package to manage WebSocket connections. You can customize the WebSocket connection by passing additional parameters to the `DerivAPI` class.

### Customization and Configuration Options

The `DerivAPI` class accepts various configuration options, such as `endpoint`, `app_id`, `token`, `cache`, and `middlewares`. You can customize these options to suit your needs.

### Asynchronous Programming

The library is designed to work with Python's `asyncio` module, allowing you to write asynchronous code that interacts with the Deriv API. Ensure that you use `await` when calling asynchronous methods provided by the library.

## Contribution Guidelines

We welcome contributions to the `python-deriv-api` library. To contribute, follow these steps:

1. Fork the repository on GitHub.
2. Create a new branch for your feature or bugfix.
3. Write tests for your changes.
4. Ensure that all tests pass.
5. Submit a pull request with a clear description of your changes.

### Coding Standards

- Follow PEP 8 guidelines for Python code.
- Write clear and concise docstrings for all functions and classes.
- Ensure that your code is well-documented and easy to understand.

### Testing Procedures

- Write unit tests for all new features and bugfixes.
- Use the `pytest` framework for testing.
- Ensure that all tests pass before submitting a pull request.

## Frequently Asked Questions (FAQ)

### How do I obtain an API token?

You can obtain an API token from your Deriv account settings. Navigate to the API token section and generate a new token with the required permissions.

### What Python versions are supported?

The library supports Python 3.9.6 or higher, excluding Python 3.9.7 due to a known issue with the `websockets` package.

### How do I report a bug or request a feature?

You can report bugs or request features by opening an issue on the GitHub repository.

## License and Copyright Information

The `python-deriv-api` library is licensed under the MIT License. See the `LICENSE` file for more information.

## Conclusion

This comprehensive guide provides detailed information about the `python-deriv-api` library, covering its installation, authentication, core modules, API endpoints, data structures, error handling, usage examples, advanced topics, contribution guidelines, and frequently asked questions. We hope this guide helps you effectively use the library to build applications that interact with the Deriv trading platform.