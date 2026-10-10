# cython: language_level=3
"""Cython MCP2221A transport and PEC decoder. No reset, GPIO or EEPROM writes."""
import math
import sys
import time


class ReadError(Exception):
    def __init__(self, code, message, fatal=False):
        super().__init__(message)
        self.code = code
        self.fatal = fatal


cpdef unsigned int crc8(bytes data):
    cdef unsigned int crc = 0
    cdef unsigned char byte
    cdef int bit
    for byte in data:
        crc ^= byte
        for bit in range(8):
            crc = ((crc << 1) ^ 0x07) & 0xFF if crc & 0x80 else (crc << 1) & 0xFF
    return crc


cpdef tuple decode_word(bytes data, int address, int register):
    cdef unsigned int raw, expected
    if len(data) != 3:
        raise ReadError("LENGTH", "Expected a three-byte SMBus word including PEC.")
    raw = data[0] | (data[1] << 8)
    expected = crc8(bytes([address << 1, register, (address << 1) | 1, data[0], data[1]]))
    if data[2] != expected:
        raise ReadError("PEC", f"reg=0x{register:02X} raw={data.hex()} PEC=0x{data[2]:02X} expected=0x{expected:02X}")
    if raw & 0x8000:
        raise ReadError("SENSOR_FLAG", f"reg=0x{register:02X} raw=0x{raw:04X} sensor error flag")
    return raw * 0.02 - 273.15, raw


class Bridge:
    def __init__(self, device, address=0x5A, timeout_ms=100, trace=False):
        self.device = device
        self.address = address
        self.timeout_ms = timeout_ms
        self.trace = trace
        self.exchanges = 0
        self.closed = False

    def exchange(self, payload, deadline=None):
        # An explicit allowlist also prevents accidental USB soft reset (0x70).
        if self.closed:
            raise ReadError("CLOSED", "HID handle is closed.", True)
        if not payload or payload[0] not in (0x10, 0x94, 0x93, 0x40):
            raise ValueError("Command is outside this read-only sensor demo's allowlist.")
        if len(payload) > 64:
            raise ValueError("HID payload exceeds 64 bytes.")
        if deadline is None:
            deadline = time.perf_counter_ns() + self.timeout_ms * 1_000_000
        remaining = deadline - time.perf_counter_ns()
        if remaining <= 0:
            raise ReadError("I2C_TIMEOUT", "Register transaction exceeded its time budget.")
        packet = bytes(payload).ljust(64, b"\0")
        if self.trace:
            print("TX " + packet[:8].hex(" "), file=sys.stderr)
        try:
            written = self.device.write(b"\0" + packet)  # HIDAPI requires the zero report ID.
            self.exchanges += 1
            if written != 65:
                raise ReadError("HID_WRITE", f"Short HID write: {written}/65 bytes.", True)
            remaining = deadline - time.perf_counter_ns()
            if remaining <= 0:
                raise ReadError("HID_TIMEOUT", "Deadline passed after sending HID command.", True)
            response = bytes(self.device.read(64, max(1, math.ceil(remaining / 1_000_000))))
        except OSError as error:
            raise ReadError("HID_IO", str(error), True) from error
        if not response:
            # Stop rather than let a late same-command response contaminate another reading.
            raise ReadError("HID_TIMEOUT", f"No reply to 0x{packet[0]:02X}; stop and reopen the connection.", True)
        if len(response) != 64 or response[0] != packet[0]:
            raise ReadError("HID_REPORT", f"Unexpected reply to 0x{packet[0]:02X}: {response[:26].hex(' ')}", True)
        if self.trace:
            print("RX " + response[:26].hex(" "), file=sys.stderr)
        return response

    def configure(self):
        status = self.exchange(b"\x10")
        if status[1] != 0:
            raise ReadError("STATUS", "Status failed: " + status[:26].hex(" "))
        if status[25] != 0 or status[22] != 1 or status[23] != 1:
            raise ReadError("STARTUP_BUSY", "Pending read or low bus line; close other clients. Status: " + status[:26].hex(" "))
        if status[14] != 118:
            response = self.exchange(bytes([0x10, 0, 0, 0x20, 118]))
            if response[1] != 0 or response[3] != 0x20:
                raise ReadError("SPEED", "100 kHz speed setting rejected. Status: " + response[:26].hex(" "))
            status = self.exchange(b"\x10")
            if status[1] != 0 or status[14] != 118:
                raise ReadError("SPEED", "100 kHz divider verification failed: " + status[:26].hex(" "))
        return status

    def read_word(self, register):
        deadline = time.perf_counter_ns() + self.timeout_ms * 1_000_000
        for packet in (bytes([0x94, 1, 0, self.address << 1, register]),
                       bytes([0x93, 3, 0, (self.address << 1) | 1])):
            response = self.exchange(packet, deadline)
            if response[1] != 0:
                raise ReadError("I2C_BUSY" if response[1] == 1 else "I2C_COMMAND",
                                f"reg=0x{register:02X} command=0x{packet[0]:02X} reply=" + response[:8].hex(" "))
        data = bytearray()
        while len(data) < 3:
            response = self.exchange(b"\x40", deadline)
            count = response[3]
            if response[1] != 0 or count == 127:
                raise ReadError("I2C_DATA", f"reg=0x{register:02X} reply=" + response[:8].hex(" "))
            if count > 3 - len(data):
                raise ReadError("I2C_LENGTH", f"Unexpected data count {count}; reg=0x{register:02X}.")
            if count:
                data.extend(response[4:4 + count])
            else:
                time.sleep(0.001)
        return decode_word(bytes(data), self.address, register)

    def read_pair(self):
        ambient, ambient_raw = self.read_word(0x06)
        obj, object_raw = self.read_word(0x07)
        return obj, ambient, object_raw, ambient_raw

    def cancel(self):
        response = self.exchange(b"\x10\x00\x10")
        if response[1] != 0 or response[2] not in (0x10, 0x11):
            raise ReadError("CANCEL", "Cancellation failed: " + response[:26].hex(" "), True)
        time.sleep(0.001)

    def close(self):
        if not self.closed:
            self.closed = True
            self.device.close()
