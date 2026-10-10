"""Read-only MCP9600 driver using the existing Cython/HIDAPI bridge.

MCP9600 words are signed, big-endian, 0.0625 C/LSB, without MLX90614 PEC.
Every read sets the register pointer, including on revision 0x14.
"""
from pathlib import Path
import sys
import time

NATIVE_ROOT = Path(__file__).resolve().parents[1] / "mlx90614-hidapi-demo"
sys.path.insert(0, str(NATIVE_ROOT))
from mcp2221_native import Bridge, ReadError

TYPES = ("K", "J", "T", "N", "S", "E", "B", "R")
ADC_BITS = (18, 16, 14, 12)
CONVERSION_MS = (320, 80, 20, 5)


def temperature(data):
    if len(data) != 2:
        raise ReadError("LENGTH", "MCP9600 temperature needs exactly two bytes.")
    return int.from_bytes(data, "big", signed=True) / 16


def configuration(identity, sensor_config, device_config, address):
    if len(identity) != 2 or identity[0] != 0x40:
        raise ReadError("IDENTITY", f"Expected MCP9600 ID 0x40; received {identity.hex()}.")
    index = (device_config >> 5) & 3
    return {"model": "MCP9600", "device_id": identity.hex().upper(),
            "address": address, "thermocouple_type": TYPES[(sensor_config >> 4) & 7],
            "adc_bits": ADC_BITS[index], "conversion_ms": CONVERSION_MS[index],
            "filter": sensor_config & 7, "cold_resolution_c": .25 if device_config & 128 else .0625,
            "power_mode": device_config & 3, "sensor_config": sensor_config,
            "device_config": device_config, "i2c_hz": 100000}


class Thermocouple:
    def __init__(self, bridge):
        if not 0x60 <= bridge.address <= 0x67:
            raise ValueError("MCP9600 address must be 0x60 through 0x67.")
        self.bridge = bridge

    def read_register(self, register, length):
        # Narrow allowlist: pointer writes only, no sensor configuration writes.
        if (register, length) not in ((0x20, 2), (0x05, 1), (0x06, 1), (0x04, 1),
                                      (0x00, 2), (0x02, 2)):
            raise ValueError("Unsupported read-only MCP9600 register.")
        deadline = time.perf_counter_ns() + self.bridge.timeout_ms * 1_000_000
        address = self.bridge.address
        for packet in (bytes([0x94, 1, 0, address << 1, register]),
                       bytes([0x93, length, 0, (address << 1) | 1])):
            response = self.bridge.exchange(packet, deadline)
            if response[1]:
                raise ReadError("I2C_COMMAND", f"reg=0x{register:02X} reply={response[:8].hex(' ')}")
        data = bytearray()
        while len(data) < length:
            response = self.bridge.exchange(b"\x40", deadline)
            count = response[3]
            if response[1] or count == 127:
                raise ReadError("I2C_DATA", f"reg=0x{register:02X} reply={response[:8].hex(' ')}")
            if count > length - len(data):
                raise ReadError("I2C_LENGTH", f"reg=0x{register:02X} unexpected count={count}")
            data.extend(response[4:4 + count])
            if not count:
                time.sleep(.001)
        return bytes(data)

    def identify(self):
        identity = self.read_register(0x20, 2)
        # Validate identity before accessing configuration registers.
        configuration(identity, 0, 0, self.bridge.address)
        sensor_config = self.read_register(0x05, 1)[0]
        device_config = self.read_register(0x06, 1)[0]
        info = configuration(identity, sensor_config, device_config, self.bridge.address)
        if info["power_mode"] != 0:
            raise ReadError("POWER_MODE", "Sensor is not in continuous conversion mode. Configuration was preserved.")
        return info

    def sample(self):
        before = self.read_register(0x04, 1)[0]
        hot = self.read_register(0x00, 2)
        cold = self.read_register(0x02, 2)
        after = self.read_register(0x04, 1)[0]
        if (before | after) & 0x10:
            raise ReadError("INPUT_RANGE", f"Thermocouple input exceeds the configured range. Status {before:02X}/{after:02X}.")
        return {"hot_c": temperature(hot), "cold_c": temperature(cold),
                "hot_raw": hot.hex().upper(), "cold_raw": cold.hex().upper(),
                "sensor_status": after}

    def close(self):
        self.bridge.close()


def open_sensor(address=0x60, device_index=None):
    import hid
    devices = hid.enumerate(0x04D8, 0x00DD)
    if not devices:
        raise ReadError("NO_BRIDGE", "No MCP2221A found. Check the USB connection.")
    if device_index is None and len(devices) != 1:
        raise ReadError("MULTIPLE_BRIDGES", "Multiple bridges found; restart with --device-index.")
    index = 0 if device_index is None else device_index
    if not 0 <= index < len(devices):
        raise ReadError("DEVICE_INDEX", "Selected bridge index is unavailable.")
    device = hid.device()
    try:
        device.open_path(devices[index]["path"])
        bridge = Bridge(device, address=address, timeout_ms=150)
        bridge.configure()
        return Thermocouple(bridge)
    except Exception:
        device.close()
        raise
