import pytest
import asyncio
from tests.test_deriv_api import MockedWs
import deriv_api

@pytest.fixture
async def mocked_ws():
    ws = MockedWs()
    yield ws
    ws.clear()

@pytest.fixture
async def deriv_api_fixture(mocked_ws):
    api = deriv_api.DerivAPI(connection=mocked_ws)
    yield api
    await api.clear()
