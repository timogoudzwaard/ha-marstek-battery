"""Tests for the Marstek UDP client."""

from __future__ import annotations

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.marstek_battery.api import (
    MarstekConnectionError,
    MarstekResponseError,
    MarstekUDPClient,
    _MarstekProtocol,
)


class TestMarstekProtocol:
    """Tests for the datagram protocol."""

    def test_datagram_received_resolves_future(self):
        """Test that a valid response resolves the matching pending future."""
        protocol = _MarstekProtocol()
        loop = asyncio.new_event_loop()
        future = loop.create_future()
        protocol.register_request(1, future)

        response = json.dumps(
            {"id": 1, "src": "VenusE", "result": {"bat_soc": 80}}
        ).encode()
        protocol.datagram_received(response, ("192.168.86.44", 30000))

        assert future.done()
        assert future.result() == {"bat_soc": 80}
        loop.close()

    def test_datagram_received_error_response(self):
        """Test that a JSON-RPC error sets exception on the future."""
        protocol = _MarstekProtocol()
        loop = asyncio.new_event_loop()
        future = loop.create_future()
        protocol.register_request(2, future)

        response = json.dumps(
            {"id": 2, "src": "VenusE", "error": {"code": -32601, "message": "Method not found"}}
        ).encode()
        protocol.datagram_received(response, ("192.168.86.44", 30000))

        assert future.done()
        with pytest.raises(MarstekResponseError):
            future.result()
        loop.close()

    def test_datagram_received_invalid_json(self):
        """Test that invalid JSON is ignored without errors."""
        protocol = _MarstekProtocol()
        protocol.datagram_received(b"not json", ("192.168.86.44", 30000))
        # Should not raise

    def test_datagram_received_unknown_id(self):
        """Test that a response with unknown ID is ignored."""
        protocol = _MarstekProtocol()
        response = json.dumps(
            {"id": 999, "src": "VenusE", "result": {}}
        ).encode()
        protocol.datagram_received(response, ("192.168.86.44", 30000))
        # Should not raise

    def test_cancel_request(self):
        """Test that cancelling removes the pending future."""
        protocol = _MarstekProtocol()
        loop = asyncio.new_event_loop()
        future = loop.create_future()
        protocol.register_request(5, future)
        protocol.cancel_request(5)
        assert 5 not in protocol._pending
        loop.close()

    def test_connection_lost_cancels_all(self):
        """Test that connection_lost cancels all pending futures."""
        protocol = _MarstekProtocol()
        loop = asyncio.new_event_loop()
        f1 = loop.create_future()
        f2 = loop.create_future()
        protocol.register_request(1, f1)
        protocol.register_request(2, f2)

        protocol.connection_lost(None)

        assert f1.done()
        assert f2.done()
        with pytest.raises(MarstekConnectionError):
            f1.result()
        loop.close()


class TestMarstekUDPClient:
    """Tests for the high-level UDP client."""

    @pytest.mark.asyncio
    async def test_send_command_success(self):
        """Test a successful send-receive cycle."""
        client = MarstekUDPClient("192.168.86.44", 30000)

        mock_transport = MagicMock()
        mock_protocol = _MarstekProtocol()
        mock_protocol._transport = mock_transport

        async def fake_endpoint(*args, **kwargs):
            return mock_transport, mock_protocol

        with patch.object(
            asyncio.get_event_loop(),
            "create_datagram_endpoint",
            side_effect=fake_endpoint,
        ):
            client._transport = mock_transport
            client._protocol = mock_protocol

            # Simulate response arriving after send
            async def simulate_response():
                await asyncio.sleep(0.01)
                response = json.dumps(
                    {"id": 1, "src": "VenusE", "result": {"bat_soc": 90}}
                ).encode()
                mock_protocol.datagram_received(response, ("192.168.86.44", 30000))

            task = asyncio.create_task(simulate_response())
            result = await client.async_send_command("ES.GetStatus", {"id": 0})
            await task

            assert result == {"bat_soc": 90}
            mock_transport.sendto.assert_called_once()

        client.close()

    @pytest.mark.asyncio
    async def test_send_command_timeout_retries(self):
        """Test that a timed-out command retries once."""
        client = MarstekUDPClient("192.168.86.44", 30000)

        mock_transport = MagicMock()
        mock_transport.is_closing.return_value = False
        mock_protocol = _MarstekProtocol()
        mock_protocol._transport = mock_transport

        client._transport = mock_transport
        client._protocol = mock_protocol

        # Both attempts will timeout
        with pytest.raises(MarstekConnectionError, match="Timeout"):
            await client.async_send_command("ES.GetStatus", {"id": 0}, timeout=0.1)

        # Should have tried twice (1 + 1 retry)
        assert mock_transport.sendto.call_count == 2

        client.close()

    @pytest.mark.asyncio
    async def test_send_command_error_response(self):
        """Test that a JSON-RPC error raises MarstekResponseError."""
        client = MarstekUDPClient("192.168.86.44", 30000)

        mock_transport = MagicMock()
        mock_transport.is_closing.return_value = False
        mock_protocol = _MarstekProtocol()
        mock_protocol._transport = mock_transport

        client._transport = mock_transport
        client._protocol = mock_protocol

        async def simulate_error():
            await asyncio.sleep(0.01)
            response = json.dumps({
                "id": 1,
                "src": "VenusE",
                "error": {"code": -32601, "message": "Method not found"},
            }).encode()
            mock_protocol.datagram_received(response, ("192.168.86.44", 30000))

        task = asyncio.create_task(simulate_error())

        with pytest.raises(MarstekResponseError, match="Method not found"):
            await client.async_send_command("Bad.Method", {"id": 0})

        await task
        client.close()

    def test_close(self):
        """Test that close shuts down the transport."""
        client = MarstekUDPClient("192.168.86.44", 30000)
        mock_transport = MagicMock()
        mock_transport.is_closing.return_value = False
        client._transport = mock_transport

        client.close()

        mock_transport.close.assert_called_once()
        assert client._transport is None

    def test_next_id_increments(self):
        """Test that request IDs increment monotonically."""
        client = MarstekUDPClient("192.168.86.44", 30000)
        ids = [client._next_id() for _ in range(5)]
        assert ids == [1, 2, 3, 4, 5]
