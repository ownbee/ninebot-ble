from __future__ import annotations

import asyncio
import enum
import logging
import secrets
import time
from binascii import hexlify
from struct import pack
from typing import Any

from bleak import BleakClient
from bleak.backends.characteristic import BleakGATTCharacteristic
from bleak.backends.device import BLEDevice
from bleak_retry_connector import establish_connection, retry_bluetooth_connection_error
from miauth.nb.nbcrypto import NbCrypto

from .register import BmsIdx, CtrlIdx, get_register_desc

logger = logging.getLogger(__name__)

NORDIC_UART_RX_UUID = "6e400002-b5a3-f393-e0a9-e50e24dcca9e"
NORDIC_UART_TX_UUID = "6e400003-b5a3-f393-e0a9-e50e24dcca9e"


class Command(enum.Enum):
    READ = 0x01
    """Read control table data."""
    WRITE = 0x02
    """Write control table data, with reply."""
    WRITE_ACK_NO_REPLY = 0x03
    """Write control table data, without reply."""
    READ_ACK = 0x04
    """Response packet to instruction reading."""
    WRITE_ACK = 0x05
    """Response packet to instruction writing."""
    INIT = 0x5B
    PING = 0x5C
    PAIR = 0x5D


class DeviceId(enum.Enum):
    ES_CONTROL = 0x20
    """Master control of electric scooter (ES)"""
    ES_BLE = 0x21
    """Bluetooth instrument of ES"""
    ES_BATT = 0x22
    """Built-in battery of ES"""
    PC = 0x3D
    """PC upper computer connected through serial port/CAN debugger/IoT equipment"""


class Packet:
    MAGIC = [0x5A, 0xA5]
    """All packets sent to scooter must start with this preamble."""

    def __init__(
        self,
        source: DeviceId,
        target: DeviceId,
        command: Command,
        data_index: int,
        data_segment: list[int] | bytes | None = None,
    ) -> None:
        self.source = source
        self.target = target
        self.command = command
        self.data_index = data_index
        self.data_segment = list(data_segment) if data_segment else []

    def pack(self) -> bytearray:
        payload = pack(
            "BBBBB", len(self.data_segment), self.source.value, self.target.value, self.command.value, self.data_index
        ) + bytes(self.data_segment)
        return bytearray(bytes(self.MAGIC) + payload)

    @staticmethod
    def unpack(data: bytearray) -> Packet | None:
        if len(data) < 7 or list(data[:2]) != Packet.MAGIC:
            return None
        segment_len = data[2]
        if len(data) < 7 + segment_len:
            return None
        return Packet(DeviceId(data[3]), DeviceId(data[4]), Command(data[5]), data[6], list(data[7:]))

    def __str__(self):
        ds = ""
        if len(self.data_segment) > 0:
            ds = ", data=" + hexlify(bytes(self.data_segment)).upper().decode()
        return (
            f"Packet[{self.source.name} -> {self.target.name},"
            f" cmd={self.command.name}, idx={self.data_index:02X}{ds}]"
        )


class NinebotClient:
    APP_KEY = secrets.token_bytes(16)

    def __init__(self) -> None:
        self.crypto = NbCrypto()
        self.receive_queue: asyncio.Queue[Packet] = asyncio.Queue(100)
        self.receive_buffer = bytearray()
        self.client: BleakClient | None = None

    async def connect(self, device: BLEDevice) -> None:
        """Connect and handshake the scooter.

        This function must be called before any other.
        """
        self.crypto.set_name(device.name.encode() if device.name else b"Unnamed")

        logger.info("Connecting to %s (%s): ...", device.name, device.address)
        self.client = await establish_connection(BleakClient, device, device.address)
        await self.client.start_notify(NORDIC_UART_TX_UUID, self._read_callback)

        logger.debug("Authenticating ...")

        # Init
        resp = await self.request(Packet(DeviceId.PC, DeviceId.ES_BLE, Command.INIT, 0))
        received_key = resp.data_segment[:16]
        received_serial = resp.data_segment[16:]

        logger.debug("> BLE Key: %s", hexlify(bytes(received_key)).upper().decode())
        logger.debug("> Serial: %s", bytes(received_serial).decode())
        self.crypto.set_ble_data(received_key)

        # Ping
        resp = await self.request(Packet(DeviceId.PC, DeviceId.ES_BLE, Command.PING, 0, self.APP_KEY))
        if resp.data_index == 0:
            # Zero (0) indicates we are not paired yet.
            while True:
                await asyncio.sleep(1.0)
                # Sending pair request here seem to pair the device. Unclear why.
                await self.send(Packet(DeviceId.PC, DeviceId.ES_BLE, Command.PAIR, 0, received_serial))
                try:
                    resp = await self.receive()
                except TimeoutError:
                    pass
                if resp.command == Command.PING and resp.data_index == 1:
                    self.crypto.set_app_data(self.APP_KEY)
                    break
                if resp.command == Command.PAIR and resp.data_index == 1:
                    break
                # If we get here, the button on the scooter need to be pressed.
                logger.info("Please press power button on scooter!")

        # Pair
        await self.request(Packet(DeviceId.PC, DeviceId.ES_BLE, Command.PAIR, 0, received_serial))

        logger.debug("Connected and authenticated successfully!")

    async def disconnect(self) -> None:
        if self.client and self.client.is_connected:
            await self.client.stop_notify(NORDIC_UART_TX_UUID)
            await self.client.disconnect()
            self.client = None

    @retry_bluetooth_connection_error()
    async def send(self, packet: Packet) -> None:
        """Send a BLE-UART packet to scooter."""
        assert self.client is not None, "Must be connected first."
        logger.debug("Sending %s", packet)
        msg = self.crypto.encrypt(packet.pack())
        msg_len = len(msg)
        byte_idx = 0
        while msg_len > 0:
            tmp_len = msg_len if msg_len <= 20 else 20
            buf = msg[byte_idx : byte_idx + tmp_len]
            logger.debug("Sending chuck %d/%d: %s", byte_idx + tmp_len, len(msg), hexlify(buf).upper().decode())
            await self.client.write_gatt_char(NORDIC_UART_RX_UUID, buf)
            msg_len -= tmp_len
            byte_idx += tmp_len

    @property
    def is_connected(self) -> bool:
        """Returns True if scooter is connected, otherwise False."""
        return self.client is not None and self.client.is_connected

    async def receive(self, timeout: float = 1) -> Packet:
        """Receive one BLE-UART packet from scooter."""
        deadline = time.time() + timeout
        while time.time() < deadline:
            if self.receive_queue.empty():
                await asyncio.sleep(0.1)
                continue
            return await self.receive_queue.get()
        raise TimeoutError("Timeout receiving packet")

    async def request(self, request: Packet, timeout: float = 5) -> Packet:
        """Sends request and returns matching response.

        Helper that combines send() and receive(). This function only works for some types of
        messages (e.g. register and symmetric send/receive packets).
        """
        command_replies = {Command.READ: Command.READ_ACK}
        deadline = time.time() + timeout
        while time.time() < deadline:
            try:
                await self.send(request)

                while time.time() < deadline:
                    recv_packet = await self.receive()
                    if (
                        recv_packet.source == request.target
                        and recv_packet.target == request.source
                        and recv_packet.command == command_replies.get(request.command, request.command)
                        and (request.command.value > 0x5 or recv_packet.data_index == request.data_index)
                    ):
                        return recv_packet
                raise TimeoutError(f"Timeout waiting for response for: {request}")
            except TimeoutError:
                logger.debug("Retrying request ...")
        raise TimeoutError(f"Did not get a response on {request}")

    async def read_reg(self, index: CtrlIdx | BmsIdx) -> Any:
        """Read scooter memory register.

        Just tell which one and this function will do the rest.
        """
        if isinstance(index, CtrlIdx):
            target = DeviceId.ES_CONTROL
        else:
            target = DeviceId.ES_BATT

        reg = get_register_desc(index)

        data: list[int] = []
        for i in range(reg.index_len):
            resp = await self.request(Packet(DeviceId.PC, target, Command.READ, reg.index_start + i, [reg.read_len]))
            data.extend(resp.data_segment)

        unpacked = reg.unpacker(data)
        if reg.scaler:
            unpacked = reg.scaler(unpacked)
        return unpacked

    async def _read_callback(self, _: BleakGATTCharacteristic, data: bytearray) -> None:
        if list(data[:2]) == Packet.MAGIC:
            self.receive_buffer = data
        else:
            self.receive_buffer += data

        decrypted = self.crypto.decrypt(self.receive_buffer)
        total_len = self.receive_buffer[2] + 7
        logger.debug(f"Decrypted {len(decrypted)}/{total_len}: {hexlify(decrypted).upper().decode()}")
        if len(decrypted) == total_len:
            packet = Packet.unpack(decrypted)
            if packet is None:
                logger.warning("Failed to decode received packet")
            else:
                await self.receive_queue.put(packet)
        elif len(decrypted) >= total_len:
            self.receive_buffer = bytearray()
            logger.warning(
                "Malformed packet received, expected packet size %d bytes, received %d bytes",
                total_len,
                len(decrypted),
            )
