import asyncio
from bleak import BleakClient, BleakScanner

def crc8(data: bytes) -> int:
    crc = 0
    for b in data:
        crc ^= b
        for _ in range(8):
            if crc & 0x80:
                crc = ((crc << 1) & 0xFF) ^ 0x07
            else:
                crc = (crc << 1) & 0xFF
    return crc & 0xFF

def reverse_bits(b: int) -> int:
    b = ((b & 0b10101010) >> 1) | ((b & 0b01010101) << 1)
    b = ((b & 0b11001100) >> 2) | ((b & 0b00110011) << 2)
    return ((b & 0b11110000) >> 4) | ((b & 0b00001111) << 4)

def to_bytes(i: int, length: int = 1) -> bytes:
    return i.to_bytes(length, "little")

class MX10:
    TX = "0000ae01-0000-1000-8000-00805f9b34fb"
    RX = "0000ae02-0000-1000-8000-00805f9b34fb"

    CMD_FEED = 0xA1
    CMD_RETRACT = 0xA0
    CMD_BITMAP = 0xA2
    CMD_GET_STATUS = 0xA3
    CMD_APPLY_ENERGY = 0xBE
    CMD_GET_INFO = 0xA8
    CMD_SET_DPI = 0xA4
    CMD_SET_SPEED = 0xBD
    CMD_SET_ENERGY = 0xAF

    def __init__(self, address: str):
        self.address = address
        self.client: BleakClient | None = None
        self.status_callback = None

    async def connect(self):
        device = await BleakScanner.find_device_by_address(self.address, timeout=10)
        if not device:
            raise Exception("Printer not found")
        self.client = BleakClient(device)
        await self.client.connect()
        await self.client.start_notify(self.RX, self._rx_handler)

    async def disconnect(self):
        if self.client:
            await self.client.stop_notify(self.RX)
            await self.client.disconnect()

    def _rx_handler(self, sender, data: bytearray):
        if self.status_callback:
            self.status_callback(data)

    def make_packet(self, cmd: int, payload: bytes = b"", type_: int = 0) -> bytes:
        length = len(payload)
        header = bytes([0x51, 0x78, cmd, type_, length & 0xFF, (length >> 8) & 0xFF])
        crc = crc8(payload) if length > 0 else 0
        return header + payload + bytes([crc, 0xFF])

    async def send(self, packet: bytes):
        if not self.client:
            raise Exception("Not connected")
        await self.client.write_gatt_char(self.TX, packet, response=False)
        await asyncio.sleep(0.01)

    # ===== Команды =====
    async def feed(self, steps: int = 0x10):
        pkt = self.make_packet(self.CMD_FEED, to_bytes(steps, 2))
        await self.send(pkt)

    async def retract(self, steps: int = 0x10):
        pkt = self.make_packet(self.CMD_RETRACT, to_bytes(steps, 2))
        await self.send(pkt)

    async def print_bitmap(self, rows: list[bytes]):
        for row in rows:
            row_rev = bytes([reverse_bits(b) for b in row])
            pkt = self.make_packet(self.CMD_BITMAP, row_rev)
            await self.send(pkt)
        await self.feed(32)

    async def apply_energy(self):
        pkt = self.make_packet(self.CMD_APPLY_ENERGY, to_bytes(1))
        await self.send(pkt)

    async def get_status(self):
        pkt = self.make_packet(self.CMD_GET_STATUS, to_bytes(0))
        await self.send(pkt)

    async def get_info(self):
        pkt = self.make_packet(self.CMD_GET_INFO, to_bytes(0))
        await self.send(pkt)

    async def set_dpi(self, dpi: int = 200):
        pkt = self.make_packet(self.CMD_SET_DPI, to_bytes(dpi))
        await self.send(pkt)

    async def set_speed(self, speed: int):
        pkt = self.make_packet(self.CMD_SET_SPEED, to_bytes(speed))
        await self.send(pkt)

    async def set_energy(self, energy: int):
        pkt = self.make_packet(self.CMD_SET_ENERGY, to_bytes(energy, 2))
        await self.send(pkt)

    async def send_raw(self, cmd: int, payload: bytes = b""):
        """Отправка произвольной команды с payload"""
        pkt = self.make_packet(cmd, payload)
        await self.send(pkt)
