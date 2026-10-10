"""Protocol and reader-lifecycle tests with fake devices; no hardware access."""
from pathlib import Path
import json
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

import monitor
from sensor import ReadError, Thermocouple, configuration, temperature


class FakeBridge:
    address, timeout_ms = 0x60, 150

    def __init__(self, responses):
        self.responses = iter(responses)
        self.commands = []

    def exchange(self, payload, deadline):
        self.commands.append(bytes(payload))
        return next(self.responses)


def response(command, data=b"", status=0, count=None):
    packet = bytearray(64)
    packet[0], packet[1], packet[3] = command, status, len(data) if count is None else count
    packet[4:4+len(data)] = data
    return packet


def register(data):
    return [response(0x94), response(0x93), response(0x40, data)]


class SensorTests(unittest.TestCase):
    def test_signed_big_endian_temperature(self):
        for data, expected in ((b"\x01\x6A",22.625),(b"\xFF\x60",-10),(b"\x00\x01",.0625),(b"\x00\x00",0)):
            self.assertEqual(temperature(data), expected)
        with self.assertRaises(ReadError):
            temperature(b"\x01\x6A\x00")

    def test_configuration_and_wrong_identity(self):
        info = configuration(bytes.fromhex("4014"),0,0,0x60)
        self.assertEqual((info["thermocouple_type"],info["adc_bits"],info["conversion_ms"]),("K",18,320))
        self.assertEqual(configuration(bytes.fromhex("4014"),0x70,0xE0,0x62)["thermocouple_type"],"R")
        with self.assertRaises(ReadError):
            configuration(bytes.fromhex("1414"),0,0,0x60)

    def test_register_pointer_and_no_pec(self):
        bridge = FakeBridge(register(bytes.fromhex("016A")))
        self.assertEqual(Thermocouple(bridge).read_register(0,2),bytes.fromhex("016A"))
        self.assertEqual(bridge.commands,[bytes.fromhex("940100C000"),bytes.fromhex("930200C1"),b"\x40"])

    def test_partial_data_is_assembled(self):
        bridge = FakeBridge([response(0x94),response(0x93),response(0x40,b"\x01"),response(0x40,b"\x6A")])
        self.assertEqual(Thermocouple(bridge).read_register(0,2),bytes.fromhex("016A"))

    def test_bad_length_and_i2c_error_are_not_retried(self):
        for packet, code in ((response(0x40,count=3),"I2C_LENGTH"),(response(0x40,status=0x41,count=127),"I2C_DATA")):
            bridge = FakeBridge([response(0x94),response(0x93),packet])
            with self.assertRaises(ReadError) as error:
                Thermocouple(bridge).read_register(0,2)
            self.assertEqual(error.exception.code,code)
            self.assertEqual(len(bridge.commands),3)

    def test_identification_precedes_configuration(self):
        bridge = FakeBridge(register(bytes.fromhex("4110")))
        with self.assertRaises(ReadError):
            Thermocouple(bridge).identify()
        self.assertEqual(len(bridge.commands),3)

    def test_input_fault_during_pair_is_rejected(self):
        responses=register(b"\x40")+register(bytes.fromhex("016A"))+register(bytes.fromhex("0185"))+register(b"\x50")
        bridge=FakeBridge(responses)
        with self.assertRaises(ReadError) as error:
            Thermocouple(bridge).sample()
        self.assertEqual(error.exception.code,"INPUT_RANGE")
        self.assertEqual(len(bridge.commands),12)

    def test_configuration_writes_are_not_exposed(self):
        bridge=FakeBridge([])
        with self.assertRaises(ValueError):
            Thermocouple(bridge).read_register(0x08,1)
        self.assertFalse(bridge.commands)


class LifecycleTests(unittest.TestCase):
    def test_read_error_stops_and_retains_csv(self):
        class FakeSensor:
            closed=False
            def identify(self): return configuration(bytes.fromhex("4014"),0,0,0x60)
            def sample(self): raise ReadError("INPUT_RANGE","Fault retained")
            def close(self): self.closed=True
        fake=FakeSensor()
        with tempfile.TemporaryDirectory() as directory,patch.object(monitor,"ROOT",Path(directory)):
            reader=monitor.Monitor(factory=lambda:fake)
            reader.connect()
            reader.thread.join(2)
            state=reader.snapshot()
            self.assertEqual((state["attempts"],state["valid"],state["failed"]),(1,0,1))
            self.assertEqual(state["phase"],"error")
            self.assertIn("INPUT_RANGE",reader.path.read_text())
            self.assertTrue(fake.closed)

    def test_disconnect_awaits_inflight_read_then_closes(self):
        entered,release=threading.Event(),threading.Event()
        class FakeSensor:
            closed=False
            def identify(self): return configuration(bytes.fromhex("4014"),0,0,0x60)
            def sample(self):
                entered.set()
                release.wait(2)
                return dict(hot_c=22.625,cold_c=24.3125,hot_raw="016A",cold_raw="0185",sensor_status=0x4F)
            def close(self): self.closed=True
        fake=FakeSensor()
        with tempfile.TemporaryDirectory() as directory,patch.object(monitor,"ROOT",Path(directory)):
            reader=monitor.Monitor(factory=lambda:fake)
            reader.connect()
            self.assertTrue(entered.wait(1))
            stopping=threading.Thread(target=reader.disconnect)
            stopping.start()
            time.sleep(.02)
            self.assertFalse(fake.closed)
            release.set()
            stopping.join(2)
            self.assertFalse(stopping.is_alive())
            self.assertTrue(fake.closed)
            self.assertEqual(reader.snapshot()["valid"],1)
            self.assertEqual(reader.snapshot()["phase"],"disconnected")

    def test_invalid_rate_does_not_open_hardware(self):
        def factory(): raise AssertionError("Must not open hardware")
        reader=monitor.Monitor(factory=factory)
        for rate in (0,8,"2",None):
            with self.assertRaises(ValueError): reader.connect(rate)
            with self.assertRaises(ValueError): reader.set_rate(rate)


if __name__=="__main__":
    unittest.main()
