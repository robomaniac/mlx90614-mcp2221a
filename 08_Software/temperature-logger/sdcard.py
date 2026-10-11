"""Qwiic OpenLog protocol adapter. Creates new files; no erase/config/reset commands.

The sensor keeps using the existing compiled Cython transport. Only OpenLog's
STOP-terminated I2C commands need this small additional HIDAPI adapter.
"""
from pathlib import Path
import math
import re
import secrets
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'qwiic-thermocouple'))
from sensor import ReadError


class CardBus:
    def __init__(self, bridge, timeout_ms=2000):
        self.bridge, self.timeout_ms = bridge, timeout_ms
        self.poisoned = False

    def exchange(self, payload, deadline):
        if self.poisoned or self.bridge.closed:
            raise ReadError('HID_STATE', 'Stop and reopen the bridge before another command.', True)
        if not payload or payload[0] not in (0x10, 0x90, 0x91, 0x40) or len(payload) > 64:
            raise ValueError('Unsupported OpenLog bridge command.')
        remaining = deadline - time.perf_counter_ns()
        if remaining <= 0:
            self.poisoned = True
            raise ReadError('SD_TIMEOUT', 'OpenLog transaction exceeded its budget.', True)
        try:
            if payload[0] in (0x10, 0x40):
                return self.bridge.exchange(payload, deadline)
            packet = bytes(payload).ljust(64, b'\0')
            if self.bridge.device.write(b'\0' + packet) != 65:
                raise ReadError('HID_WRITE', 'Short HID write to OpenLog.', True)
            remaining = deadline - time.perf_counter_ns()
            if remaining <= 0:
                raise ReadError('SD_TIMEOUT', 'Deadline passed after the SD command.', True)
            response = bytes(self.bridge.device.read(64, max(1, math.ceil(remaining / 1_000_000))))
            if len(response) != 64 or response[0] != packet[0]:
                raise ReadError('HID_REPORT', 'Unexpected OpenLog HID reply: ' + response[:8].hex(' '), True)
            return response
        except (ReadError, OSError) as error:
            self.poisoned = True
            if isinstance(error, ReadError):
                raise
            raise ReadError('HID_IO', str(error), True) from error

    def deadline(self):
        return time.perf_counter_ns() + self.timeout_ms * 1_000_000

    @staticmethod
    def address(address):
        if address not in (0x29, 0x2A):
            raise ValueError('Select OpenLog address 0x29 or 0x2A.')

    def write(self, address, data):
        self.address(address)
        if not 1 <= len(data) <= 32:
            raise ValueError('OpenLog packets must contain 1..32 bytes.')
        deadline = self.deadline()
        response = self.exchange(bytes([0x90, len(data), 0, address << 1]) + data, deadline)
        if response[1]:
            raise ReadError('SD_I2C_WRITE', response[:8].hex(' '), True)
        while True:
            status = self.exchange(b'\x10', deadline)
            if status[1] or status[20] & 0x40 or status[8] in (0x12, 0x17, 0x23, 0x25, 0x44, 0x52, 0x62):
                raise ReadError('SD_I2C_STATE', status[:26].hex(' '), True)
            if status[8] == 0:
                return
            time.sleep(.001)

    def read(self, address, length):
        self.address(address)
        if not 1 <= length <= 32:
            raise ValueError('OpenLog reads must contain 1..32 bytes.')
        deadline = self.deadline()
        response = self.exchange(bytes([0x91, length, 0, (address << 1) | 1]), deadline)
        if response[1]:
            raise ReadError('SD_I2C_READ', response[:8].hex(' '), True)
        data = bytearray()
        while len(data) < length:
            # OpenLog can stretch SCL while creating/syncing a file. Fetching
            # data before the read completes produced 40 41 50 7F on hardware.
            # Wait within the same deadline; never treat that error as data.
            while True:
                status = self.exchange(b'\x10', deadline)
                if status[1] or status[20] & 0x40 or status[8] in (0x12, 0x17, 0x23, 0x25, 0x44, 0x52, 0x62):
                    raise ReadError('SD_I2C_STATE', status[:26].hex(' '), True)
                if status[8] in (0x54, 0x55):
                    break
                time.sleep(.001)
            response = self.exchange(b'\x40', deadline)
            count = response[3]
            if response[1] or response[2] == 0x25 or count == 127 or count > length - len(data):
                raise ReadError('SD_I2C_DATA', response[:8].hex(' '), True)
            data.extend(response[4:4 + count])
            if not count:
                time.sleep(.001)
        return bytes(data)


class OpenLog:
    def __init__(self, bus, address=0x2A):
        CardBus.address(address)
        self.bus, self.address = bus, address
        self.filename, self.bytes_written = None, 0
        self.active = False

    def value(self, register, length=1, argument=b''):
        if register not in (0, 1, 2, 3, 9, 13):
            raise ValueError('Unsupported read command.')
        self.bus.write(self.address, bytes([register]) + argument)
        return self.bus.read(self.address, length)

    def command(self, register, argument=b''):
        if register not in (6, 8, 11, 12, 17):
            raise ValueError('Unsupported SD command: no delete, reset or configuration writes.')
        self.bus.write(self.address, bytes([register]) + argument)
        # Read the previous command response directly. A new status command would
        # change the command-success flag in the current SparkFun firmware.
        status = self.bus.read(self.address, 1)[0]
        if status & 7 != 7:
            raise ReadError('SD_COMMAND', f'OpenLog command 0x{register:02X} status 0x{status:02X}.')
        return status

    def identify(self):
        identity = self.value(0)[0]
        if identity != 0x78:
            raise ReadError('SD_IDENTITY', f'Expected OpenLog ID 0x78; received 0x{identity:02X}.')
        status = self.value(1)[0]
        if not status & 1:
            raise ReadError('SD_NOT_READY', 'OpenLog did not initialize the card. Check FAT16/FAT32 and card seating.')
        return {'address': self.address, 'identity': identity, 'status': status,
                'firmware': f'{self.value(2)[0]}.{self.value(3)[0]}'}

    @staticmethod
    def name(filename):
        if not re.fullmatch(r'T[A-F0-9]{7}\.CSV', filename):
            raise ValueError('Use a generated Txxxxxxx.CSV filename.')
        return filename.encode('ascii')

    def start(self, header, filename=None):
        info = self.identify()
        # v2.0 writes sizeof(pointer), not the supplied string length, and has
        # no sync register. Observed: 14 input bytes became 2 stored bytes.
        # Fail before cd/create/append; retain read-only identity diagnostics.
        if info['firmware'].split('.')[0] != '3':
            raise ReadError('SD_FIRMWARE', f"OpenLog firmware {info['firmware']} is unsupported for CSV recording. Firmware 3.x is required; 2.0 truncates writes and lacks sync. No recording file created.")
        self.command(8, b'..')  # SparkFun defines '..' as return to the root.
        filename = filename or ('T' + secrets.token_hex(4).upper()[:7] + '.CSV')
        name = self.name(filename)
        # Retain the attempted filename even if creation/open/header fails.
        self.filename = filename
        self.command(6, name)  # Exclusive creation fails if the name already exists.
        self.command(11, name)
        self.filename, self.bytes_written, self.active = filename, 0, True
        self.write(header)
        self.checkpoint()
        return filename

    def write(self, text):
        if not self.active:
            raise ReadError('SD_CLOSED', 'Start an SD recording first.')
        data = text.encode('utf-8')
        if b'\0' in data:
            raise ValueError('OpenLog text cannot contain NUL bytes.')
        for offset in range(0, len(data), 31):
            self.command(12, data[offset:offset + 31])
        self.bytes_written += len(data)

    def size(self):
        # The firmware closes the working file while looking up its size.
        return int.from_bytes(self.value(13, 4, self.name(self.filename)), 'big', signed=True)

    def checkpoint(self, reopen=True):
        self.command(17)
        actual = self.size()
        if actual != self.bytes_written:
            raise ReadError('SD_SIZE', f'Expected {self.bytes_written} stored bytes, found {actual}.')
        if reopen:
            self.command(11, self.name(self.filename))
        else:
            self.active = False
        return actual

    def finish(self):
        return self.checkpoint(reopen=False) if self.active else self.bytes_written

    def read_file(self, length):
        if self.active or not 0 <= length <= 65536:
            raise ValueError('Stop the recording before a bounded readback.')
        self.bus.write(self.address, b'\x09' + self.name(self.filename))
        result = bytearray()
        while len(result) < length:
            result.extend(self.bus.read(self.address, min(32, length - len(result))))
        return bytes(result)
