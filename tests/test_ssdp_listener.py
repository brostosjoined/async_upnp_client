"""Unit tests for ssdp_listener."""

from datetime import datetime, timedelta
from ipaddress import ip_address
from typing import AsyncGenerator
from unittest.mock import patch

try:
    from unittest.mock import AsyncMock
except ImportError:
    # For python 3.6/3.7
    from mock import AsyncMock  # type: ignore

import pytest

from async_upnp_client.advertisement import SsdpAdvertisementListener
from async_upnp_client.const import NotificationSubType, SsdpSource
from async_upnp_client.search import SsdpSearchListener
from async_upnp_client.ssdp_listener import SsdpListener, same_headers_differ
from async_upnp_client.utils import CaseInsensitiveDict

from .common import (
    ADVERTISEMENT_HEADERS_DEFAULT,
    ADVERTISEMENT_REQUEST_LINE,
    SEACH_REQUEST_LINE,
    SEARCH_HEADERS_DEFAULT,
)


@pytest.fixture
async def mock_start_listeners() -> AsyncGenerator:
    """Create listeners but don't call async_start()."""
    # pylint: disable=protected-access

    async def async_start(self: SsdpListener) -> None:
        target_ip = ip_address(self.target[0])
        self._advertisement_listener = SsdpAdvertisementListener(
            on_alive=self._on_alive,
            on_update=self._on_update,
            on_byebye=self._on_byebye,
            source_ip=self.source_ip,
            target_ip=target_ip,
            loop=self.loop,
        )

        self._search_listener = SsdpSearchListener(
            self._on_search,
            loop=self.loop,
            source_ip=self.source_ip,
            target=self.target,
            timeout=self.search_timeout,
        )

    with patch.object(SsdpListener, "async_start", new=async_start) as mock:
        yield mock


@pytest.mark.asyncio
@pytest.mark.usefixtures("mock_start_listeners")
async def test_see_advertisement_alive() -> None:
    """Test seeing a device through an ssdp:alive-advertisement."""
    # pylint: disable=protected-access
    callback = AsyncMock()
    listener = SsdpListener(async_callback=callback)
    await listener.async_start()
    advertisement_listener = listener._advertisement_listener
    assert advertisement_listener is not None

    # See device for the first time through alive-advertisement.
    headers = CaseInsensitiveDict(ADVERTISEMENT_HEADERS_DEFAULT)
    headers["NTS"] = NotificationSubType.SSDP_ALIVE
    await advertisement_listener._async_on_data(ADVERTISEMENT_REQUEST_LINE, headers)
    callback.assert_awaited()
    assert ADVERTISEMENT_HEADERS_DEFAULT["_udn"] in listener.devices

    # See device for the second time through alive-advertisement, not triggering callback.
    callback.reset_mock()
    headers = CaseInsensitiveDict(ADVERTISEMENT_HEADERS_DEFAULT)
    headers["NTS"] = NotificationSubType.SSDP_ALIVE
    await advertisement_listener._async_on_data(ADVERTISEMENT_REQUEST_LINE, headers)
    callback.assert_not_awaited()
    assert ADVERTISEMENT_HEADERS_DEFAULT["_udn"] in listener.devices

    await listener.async_stop()


@pytest.mark.asyncio
@pytest.mark.usefixtures("mock_start_listeners")
async def test_see_advertisement_byebye() -> None:
    """Test seeing a device through an ssdp:byebye-advertisement."""
    # pylint: disable=protected-access
    callback = AsyncMock()
    listener = SsdpListener(async_callback=callback)
    await listener.async_start()
    advertisement_listener = listener._advertisement_listener
    assert advertisement_listener is not None

    # See device for the first time through byebye-advertisement, not triggering callback.
    callback.reset_mock()
    headers = CaseInsensitiveDict(ADVERTISEMENT_HEADERS_DEFAULT)
    headers["NTS"] = NotificationSubType.SSDP_BYEBYE
    await advertisement_listener._async_on_data(ADVERTISEMENT_REQUEST_LINE, headers)
    callback.assert_not_awaited()
    assert ADVERTISEMENT_HEADERS_DEFAULT["_udn"] not in listener.devices

    # See device for the first time through alive-advertisement, triggering callback.
    callback.reset_mock()
    headers = CaseInsensitiveDict(ADVERTISEMENT_HEADERS_DEFAULT)
    headers["NTS"] = NotificationSubType.SSDP_ALIVE
    await advertisement_listener._async_on_data(ADVERTISEMENT_REQUEST_LINE, headers)
    callback.assert_awaited_once()
    assert callback.await_args is not None
    device, dst, _ = callback.await_args.args
    assert device.combined_headers(dst)["NTS"] == "ssdp:alive"
    assert ADVERTISEMENT_HEADERS_DEFAULT["_udn"] in listener.devices

    # See device for the second time through byebye-advertisement, triggering callback.
    callback.reset_mock()
    headers = CaseInsensitiveDict(ADVERTISEMENT_HEADERS_DEFAULT)
    headers["NTS"] = NotificationSubType.SSDP_BYEBYE
    await advertisement_listener._async_on_data(ADVERTISEMENT_REQUEST_LINE, headers)
    callback.assert_awaited_once()
    assert callback.await_args is not None
    device, dst, _ = callback.await_args.args
    assert device.combined_headers(dst)["NTS"] == "ssdp:byebye"
    assert ADVERTISEMENT_HEADERS_DEFAULT["_udn"] not in listener.devices

    await listener.async_stop()


@pytest.mark.asyncio
@pytest.mark.usefixtures("mock_start_listeners")
async def test_see_advertisement_update() -> None:
    """Test seeing a device through a ssdp:update-advertisement."""
    # pylint: disable=protected-access
    callback = AsyncMock()
    listener = SsdpListener(async_callback=callback)
    await listener.async_start()
    advertisement_listener = listener._advertisement_listener
    assert advertisement_listener is not None

    # See device for the first time through alive-advertisement, triggering callback.
    callback.reset_mock()
    headers = CaseInsensitiveDict(ADVERTISEMENT_HEADERS_DEFAULT)
    headers["NTS"] = NotificationSubType.SSDP_ALIVE
    await advertisement_listener._async_on_data(ADVERTISEMENT_REQUEST_LINE, headers)
    callback.assert_awaited()
    assert ADVERTISEMENT_HEADERS_DEFAULT["_udn"] in listener.devices

    # See device for the second time through update-advertisement, triggering callback.
    callback.reset_mock()
    headers = CaseInsensitiveDict(ADVERTISEMENT_HEADERS_DEFAULT)
    headers["NTS"] = NotificationSubType.SSDP_UPDATE
    headers["BOOTID.UPNP.ORG"] = "2"
    await advertisement_listener._async_on_data(ADVERTISEMENT_REQUEST_LINE, headers)
    callback.assert_awaited()
    assert ADVERTISEMENT_HEADERS_DEFAULT["_udn"] in listener.devices

    await listener.async_stop()


@pytest.mark.asyncio
@pytest.mark.usefixtures("mock_start_listeners")
async def test_see_search() -> None:
    """Test seeing a device through an search."""
    # pylint: disable=protected-access
    callback = AsyncMock()
    listener = SsdpListener(async_callback=callback)
    await listener.async_start()
    search_listener = listener._search_listener
    assert search_listener is not None

    # See device for the first time through search.
    headers = CaseInsensitiveDict(SEARCH_HEADERS_DEFAULT)
    await search_listener._async_on_data(SEACH_REQUEST_LINE, headers)
    callback.assert_awaited()
    assert ADVERTISEMENT_HEADERS_DEFAULT["_udn"] in listener.devices

    await listener.async_stop()


@pytest.mark.asyncio
@pytest.mark.usefixtures("mock_start_listeners")
async def test_see_search_then_alive() -> None:
    """Test seeing a device through a search, then a ssdp:update-advertisement."""
    # pylint: disable=protected-access
    callback = AsyncMock()
    listener = SsdpListener(async_callback=callback)
    await listener.async_start()
    advertisement_listener = listener._advertisement_listener
    assert advertisement_listener is not None
    search_listener = listener._search_listener
    assert search_listener is not None

    # See device for the first time through search.
    headers = CaseInsensitiveDict(SEARCH_HEADERS_DEFAULT)
    await search_listener._async_on_data(SEACH_REQUEST_LINE, headers)
    callback.assert_awaited()
    assert ADVERTISEMENT_HEADERS_DEFAULT["_udn"] in listener.devices

    # See device for the second time through alive-advertisement, not triggering callback.
    callback.reset_mock()
    headers = CaseInsensitiveDict(ADVERTISEMENT_HEADERS_DEFAULT)
    headers["NTS"] = NotificationSubType.SSDP_ALIVE
    await advertisement_listener._async_on_data(ADVERTISEMENT_REQUEST_LINE, headers)
    callback.assert_not_awaited()
    assert ADVERTISEMENT_HEADERS_DEFAULT["_udn"] in listener.devices

    await listener.async_stop()


@pytest.mark.asyncio
@pytest.mark.usefixtures("mock_start_listeners")
async def test_purge_devices() -> None:
    """Test if a device is purged when it times out given the value of the CACHE-CONTROL header."""
    # pylint: disable=protected-access
    callback = AsyncMock()
    listener = SsdpListener(async_callback=callback)
    await listener.async_start()
    search_listener = listener._search_listener
    assert search_listener is not None

    # See device for the first time through alive-advertisement.
    headers = CaseInsensitiveDict(SEARCH_HEADERS_DEFAULT)
    await search_listener._async_on_data(SEACH_REQUEST_LINE, headers)
    callback.assert_awaited()
    assert ADVERTISEMENT_HEADERS_DEFAULT["_udn"] in listener.devices

    # See device for the second time through alive-advertisement.
    headers = CaseInsensitiveDict(SEARCH_HEADERS_DEFAULT)
    await search_listener._async_on_data(SEACH_REQUEST_LINE, headers)
    callback.assert_awaited()
    assert ADVERTISEMENT_HEADERS_DEFAULT["_udn"] in listener.devices

    # "Wait" a bit... and purge devices.
    override_now = headers["_timestamp"] + timedelta(hours=1)
    listener._device_tracker.purge_devices(override_now)
    assert ADVERTISEMENT_HEADERS_DEFAULT["_udn"] not in listener.devices

    # See device for the first time through alive-advertisement.
    headers = CaseInsensitiveDict(SEARCH_HEADERS_DEFAULT)
    await search_listener._async_on_data(SEACH_REQUEST_LINE, headers)
    callback.assert_awaited()
    assert ADVERTISEMENT_HEADERS_DEFAULT["_udn"] in listener.devices

    # "Wait" a bit... and purge devices again.
    override_now = headers["_timestamp"] + timedelta(hours=1)
    listener._device_tracker.purge_devices(override_now)
    assert ADVERTISEMENT_HEADERS_DEFAULT["_udn"] not in listener.devices

    await listener.async_stop()


def test_same_headers_differ_profile() -> None:
    """Test same_headers_differ."""
    current_headers = CaseInsensitiveDict(
        {
            "Cache-Control": "max-age=1900",
            "location": "http://192.168.1.1:80/RootDevice.xml",
            "Server": "UPnP/1.0 UPnP/1.0 UPnP-Device-Host/1.0",
            "ST": "urn:schemas-upnp-org:device:WANDevice:1",
            "USN": "uuid:upnp-WANDevice-1_0-123456789abc::urn:schemas-upnp-org:device:WANDevice:1",
            "EXT": "",
            "_location_original": "http://192.168.1.1:80/RootDevice.xml",
            "_timestamp": datetime.now(),
            "_host": "192.168.1.1",
            "_port": "1900",
            "_udn": "uuid:upnp-WANDevice-1_0-123456789abc",
            "_source": SsdpSource.SEARCH,
        }
    )
    new_headers = CaseInsensitiveDict(
        {
            "Cache-Control": "max-age=1900",
            "location": "http://192.168.1.1:80/RootDevice.xml",
            "Server": "UPnP/1.0 UPnP/1.0 UPnP-Device-Host/1.0 abc",
            "Date": "Sat, 11 Sep 2021 12:00:00 GMT",
            "ST": "urn:schemas-upnp-org:device:WANDevice:1",
            "USN": "uuid:upnp-WANDevice-1_0-123456789abc::urn:schemas-upnp-org:device:WANDevice:1",
            "EXT": "",
            "_location_original": "http://192.168.1.1:80/RootDevice.xml",
            "_timestamp": datetime.now(),
            "_host": "192.168.1.1",
            "_port": "1900",
            "_udn": "uuid:upnp-WANDevice-1_0-123456789abc",
            "_source": SsdpSource.SEARCH,
        }
    )
    for _ in range(0, 10000):
        assert not same_headers_differ(current_headers, new_headers)
