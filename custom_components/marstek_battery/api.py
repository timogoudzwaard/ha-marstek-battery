"""Async UDP client for Marstek JSON-RPC protocol."""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
from typing import Any

_LOGGER = logging.getLogger(__name__)

DEFAULT_TIMEOUT = 5
MAX_RETRIES = 1


class MarstekUDPError(Exception):
    """Base exception for Marstek UDP client errors."""


class MarstekConnectionError(MarstekUDPError):
    """Raised when the device cannot be reached."""


class MarstekResponseError(MarstekUDPError):
    """Raised when the device returns a JSON-RPC error."""


class _MarstekProtocol(asyncio.DatagramProtocol):
    """Datagram protocol that resolves pending futures by request ID."""

    def __init__(self) -> None:
        self._pending: dict[int, asyncio.Future[dict[str, Any]]] = {}
        self._transport: asyncio.DatagramTransport | None = None

    def connection_made(self, transport: asyncio.BaseTransport) -> None:
        """Store the transport reference."""
        self._transport = transport  # type: ignore[assignment]

    def datagram_received(self, data: bytes, addr: tuple[str, int]) -> None:
        """Parse incoming JSON-RPC response and resolve the matching future."""
        try:
            response = json.loads(data.decode())
        except (json.JSONDecodeError, UnicodeDecodeError):
            _LOGGER.warning("Received invalid JSON from %s", addr)
            return

        request_id = response.get("id")
        if request_id is None:
            _LOGGER.debug("Response without id from %s: %s", addr, response)
            return

        # Coerce to int for matching (API uses numeric IDs)
        with contextlib.suppress(TypeError, ValueError):
            request_id = int(request_id)

        future = self._pending.pop(request_id, None)
        if future is not None and not future.done():
            if "error" in response:
                future.set_exception(
                    MarstekResponseError(
                        f"JSON-RPC error {response['error'].get('code')}: "
                        f"{response['error'].get('message')}"
                    )
                )
            else:
                future.set_result(response.get("result", {}))
        else:
            _LOGGER.debug("Unexpected response id=%s from %s", request_id, addr)

    def error_received(self, exc: Exception) -> None:
        """Handle protocol-level errors."""
        _LOGGER.debug("UDP protocol error: %s", exc)

    def connection_lost(self, exc: Exception | None) -> None:
        """Cancel all pending futures on connection loss."""
        for future in self._pending.values():
            if not future.done():
                future.set_exception(
                    MarstekConnectionError("UDP connection lost")
                )
        self._pending.clear()
        self._transport = None

    def register_request(
        self, request_id: int, future: asyncio.Future[dict[str, Any]]
    ) -> None:
        """Register a pending request future."""
        self._pending[request_id] = future

    def cancel_request(self, request_id: int) -> None:
        """Remove a pending request (e.g. on timeout)."""
        self._pending.pop(request_id, None)


class MarstekUDPClient:
    """Async UDP client for Marstek JSON-RPC protocol.

    Uses asyncio.DatagramProtocol for non-blocking communication.
    The transport is created once and reused across calls.
    """

    def __init__(self, host: str, port: int) -> None:
        self._host = host
        self._port = port
        self._transport: asyncio.DatagramTransport | None = None
        self._protocol: _MarstekProtocol | None = None
        self._request_id = 0

    @property
    def host(self) -> str:
        """Return the target host."""
        return self._host

    @property
    def port(self) -> int:
        """Return the target port."""
        return self._port

    def _next_id(self) -> int:
        """Return a monotonically increasing request ID."""
        self._request_id += 1
        return self._request_id

    async def async_connect(self) -> None:
        """Create the UDP transport if not already connected."""
        if self._transport is not None and not self._transport.is_closing():
            return

        loop = asyncio.get_running_loop()
        self._transport, self._protocol = await loop.create_datagram_endpoint(
            _MarstekProtocol,
            remote_addr=(self._host, self._port),
        )

    async def async_send_command(
        self,
        method: str,
        params: dict[str, Any] | None = None,
        timeout: float = DEFAULT_TIMEOUT,
    ) -> dict[str, Any]:
        """Send a JSON-RPC command and wait for the response.

        Retries once on timeout (UDP is unreliable).
        """
        last_error: Exception | None = None

        for attempt in range(1 + MAX_RETRIES):
            try:
                return await self._send_once(method, params, timeout)
            except TimeoutError:
                last_error = MarstekConnectionError(
                    f"Timeout waiting for response to {method} "
                    f"(attempt {attempt + 1}/{1 + MAX_RETRIES})"
                )
                _LOGGER.debug(
                    "Timeout on %s attempt %d/%d",
                    method,
                    attempt + 1,
                    1 + MAX_RETRIES,
                )
            except MarstekResponseError:
                raise
            except OSError as err:
                last_error = MarstekConnectionError(
                    f"UDP send error for {method}: {err}"
                )
                _LOGGER.debug("UDP send error on %s: %s", method, err)
                # Reconnect on OS-level errors
                self.close()
                await self.async_connect()

        raise last_error  # type: ignore[misc]

    async def _send_once(
        self,
        method: str,
        params: dict[str, Any] | None,
        timeout: float,
    ) -> dict[str, Any]:
        """Send a single JSON-RPC request and await the response."""
        await self.async_connect()
        assert self._transport is not None
        assert self._protocol is not None

        request_id = self._next_id()
        payload = {
            "id": request_id,
            "method": method,
            "params": params if params is not None else {"id": 0},
        }

        loop = asyncio.get_running_loop()
        future: asyncio.Future[dict[str, Any]] = loop.create_future()
        self._protocol.register_request(request_id, future)

        _LOGGER.debug("Sending to %s:%s: %s", self._host, self._port, payload)
        self._transport.sendto(json.dumps(payload).encode())

        try:
            async with asyncio.timeout(timeout):
                result = await future
        except TimeoutError:
            self._protocol.cancel_request(request_id)
            raise

        _LOGGER.debug("Received from %s:%s: %s", self._host, self._port, result)
        return result

    async def async_discover_broadcast(
        self,
        port: int = 30000,
        timeout: float = DEFAULT_TIMEOUT,
    ) -> list[dict[str, Any]]:
        """Send a broadcast Marstek.GetDevice and collect responses.

        Returns a list of device info dicts from all responding devices.
        """
        loop = asyncio.get_running_loop()
        devices: list[dict[str, Any]] = []

        class _DiscoveryProtocol(asyncio.DatagramProtocol):
            def __init__(self) -> None:
                self.transport: asyncio.DatagramTransport | None = None

            def connection_made(self, transport: asyncio.BaseTransport) -> None:
                self.transport = transport  # type: ignore[assignment]

            def datagram_received(
                self, data: bytes, addr: tuple[str, int]
            ) -> None:
                try:
                    response = json.loads(data.decode())
                except (json.JSONDecodeError, UnicodeDecodeError):
                    return
                result = response.get("result")
                if result and "ble_mac" in result:
                    result["_source_ip"] = addr[0]
                    devices.append(result)

        transport, _protocol = await loop.create_datagram_endpoint(
            _DiscoveryProtocol,
            local_addr=("0.0.0.0", 0),
            allow_broadcast=True,
        )

        payload = json.dumps(
            {"id": 0, "method": "Marstek.GetDevice", "params": {"ble_mac": "0"}}
        ).encode()

        try:
            transport.sendto(payload, ("255.255.255.255", port))
            await asyncio.sleep(timeout)
        finally:
            transport.close()

        return devices

    def close(self) -> None:
        """Close the UDP transport."""
        if self._transport is not None and not self._transport.is_closing():
            self._transport.close()
        self._transport = None
        self._protocol = None
