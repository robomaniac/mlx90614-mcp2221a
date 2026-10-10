"""Protocol and scheduling checks with fake HID/clock; no physical USB commands."""
from contextlib import redirect_stdout, redirect_stderr
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import patch
import csv
import io
import json
import unittest

import demo
import mcp2221_native as native


def pec_reference(data):
    # Independent polynomial division, rather than the extension's byte/bit loop.
    value = int.from_bytes(data, "big") << 8
    for bit in range(value.bit_length() - 1, 7, -1):
        if value & (1 << bit):
            value ^= 0x107 << (bit - 8)
    return value


def word(register, raw=14908):
    data = raw.to_bytes(2, "little")
    return data + bytes([pec_reference(bytes([0xB4, register, 0xB5]) + data)])


def reply(command, code=0, count=0, data=b""):
    result = bytearray(64)
    result[0], result[1], result[3] = command, code, count
    result[4:4 + len(data)] = data
    return bytes(result)


def status(divider=118, speed=0):
    result = bytearray(reply(0x10))
    result[3], result[14], result[22], result[23] = speed, divider, 1, 1
    return bytes(result)


class FakeHid:
    def __init__(self, responses, written=65):
        self.responses = list(responses)
        self.written = written
        self.writes = []
        self.closed = False

    def write(self, packet):
        self.writes.append(packet)
        return self.written

    def read(self, length, timeout):
        assert length == 64 and timeout > 0
        return self.responses.pop(0) if self.responses else []

    def close(self):
        self.closed = True


class NativeTests(unittest.TestCase):
    def test_crc_known_vector_and_independent_pec(self):
        self.assertEqual(native.crc8(b"123456789"), 0xF4)
        for register in (6, 7):
            for raw in (0, 14908, 32767):
                celsius, decoded = native.decode_word(word(register, raw), 0x5A, register)
                self.assertEqual(decoded, raw)
                self.assertAlmostEqual(celsius, raw * .02 - 273.15)

    def test_rejects_bad_pec_error_flag_and_length(self):
        for data, code in ((word(6)[:2] + bytes([word(6)[2] ^ 1]), "PEC"),
                           (word(6, 0x8000), "SENSOR_FLAG"), (b"\x00", "LENGTH")):
            with self.assertRaises(native.ReadError) as raised:
                native.decode_word(data, 0x5A, 6)
            self.assertEqual(raised.exception.code, code)

    def test_configure_reuses_verified_100khz(self):
        device = FakeHid([status()])
        native.Bridge(device).configure()
        self.assertEqual([packet[1] for packet in device.writes], [0x10])
        self.assertTrue(all(len(packet) == 65 and packet[0] == 0 for packet in device.writes))

    def test_configure_sets_then_verifies_divider(self):
        device = FakeHid([status(0), status(118, 0x20), status(118)])
        native.Bridge(device).configure()
        self.assertEqual(device.writes[1][1:6], bytes([0x10, 0, 0, 0x20, 118]))

    def test_rejected_speed_does_not_probe_sensor(self):
        device = FakeHid([status(0), status(0, 0x21)])
        with self.assertRaises(native.ReadError) as raised:
            native.Bridge(device).configure()
        self.assertEqual(raised.exception.code, "SPEED")
        self.assertEqual(len(device.writes), 2)

    def test_complete_pair_and_repeated_start_packets(self):
        responses = []
        for register in (6, 7):
            responses.extend([reply(0x94), reply(0x93), reply(0x40, count=3, data=word(register))])
        device = FakeHid(responses)
        pair = native.Bridge(device).read_pair()
        self.assertAlmostEqual(pair[0], 25.01)
        self.assertAlmostEqual(pair[1], 25.01)
        self.assertEqual([packet[1] for packet in device.writes], [0x94, 0x93, 0x40] * 2)
        self.assertEqual(device.writes[0][1:6], bytes([0x94, 1, 0, 0xB4, 6]))
        self.assertEqual(device.writes[1][1:5], bytes([0x93, 3, 0, 0xB5]))

    def test_pending_and_partial_data_are_collected(self):
        data = word(6)
        device = FakeHid([reply(0x94), reply(0x93), reply(0x40),
                          reply(0x40, count=1, data=data[:1]), reply(0x40, count=2, data=data[1:])])
        self.assertEqual(native.Bridge(device).read_word(6)[1], 14908)

    def test_busy_and_invalid_data_are_explicit_errors(self):
        for responses, code in (([reply(0x94, 1)], "I2C_BUSY"),
                                ([reply(0x94), reply(0x93), reply(0x40, count=127)], "I2C_DATA")):
            with self.assertRaises(native.ReadError) as raised:
                native.Bridge(FakeHid(responses)).read_word(6)
            self.assertEqual(raised.exception.code, code)

    def test_missing_mismatched_or_short_hid_reply_is_fatal(self):
        for response, code in ((b"", "HID_TIMEOUT"), (reply(0x40), "HID_REPORT"), (b"\x10", "HID_REPORT")):
            with self.assertRaises(native.ReadError) as raised:
                native.Bridge(FakeHid([response])).exchange(b"\x10")
            self.assertTrue(raised.exception.fatal)
            self.assertEqual(raised.exception.code, code)

    def test_short_write_and_reset_guard(self):
        device = FakeHid([], written=64)
        with self.assertRaises(native.ReadError) as raised:
            native.Bridge(device).exchange(b"\x10")
        self.assertTrue(raised.exception.fatal)
        device = FakeHid([])
        with self.assertRaises(ValueError):
            native.Bridge(device).exchange(b"\x70\xAB\xCD\xEF")
        self.assertEqual(device.writes, [])

    def test_low_bus_stops_and_close_is_idempotent(self):
        low = bytearray(status())
        low[23] = 0
        device = FakeHid([bytes(low)])
        bridge = native.Bridge(device)
        with self.assertRaises(native.ReadError):
            bridge.configure()
        bridge.close()
        bridge.close()
        self.assertTrue(device.closed)


class SchedulingTests(unittest.TestCase):
    def test_absolute_deadlines_skip_stalls_without_drift(self):
        self.assertEqual(demo.next_slot(1000, 100, 1, 1099), 1)
        self.assertEqual(demo.next_slot(1000, 100, 1, 1100), 1)
        self.assertEqual(demo.next_slot(1000, 100, 1, 1350), 4)
        self.assertEqual(demo.next_slot(1000, 100, 50000, 1001), 50000)

    def test_percentiles_are_reported(self):
        self.assertEqual(demo.distribution(range(1, 101)), {"p50": 50, "p95": 95, "p99": 99, "max": 100})

    def run_fake(self, failure, work_ns, cancel_failure=None):
        clock = [0]
        class Sensor:
            exchanges = 0
            cancels = 0
            calls = 0
            def read_pair(self):
                clock[0] += work_ns
                self.calls += 1
                if self.calls == 1 and failure:
                    raise failure
                return 30, 24, 15158, 14858
            def cancel(self):
                self.cancels += 1
                if cancel_failure:
                    raise cancel_failure
        sensor = Sensor()
        args = SimpleNamespace(hz=10, seconds=.4, simulate=True, address=0x5A, timeout_ms=100)
        def sleep(seconds):
            clock[0] += round(seconds * 1e9)
        with TemporaryDirectory() as directory:
            path = Path(directory) / "test.csv"
            with patch.object(demo.time, "perf_counter_ns", lambda: clock[0]), patch.object(demo.time, "sleep", sleep), \
                    redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
                exit_code = demo.acquire(sensor, native, args, path)
            with path.open(encoding="utf-8") as stream:
                rows = list(csv.DictReader(stream))
            summary = json.loads(path.with_suffix(".summary.json").read_text(encoding="utf-8"))
        return exit_code, rows, summary, sensor

    def test_failed_pair_remains_in_csv_and_recovers_without_hidden_retry(self):
        result, rows, summary, sensor = self.run_fake(native.ReadError("PEC", "bad PEC"), 1_000_000)
        self.assertEqual(result, 1)
        self.assertEqual(rows[0]["status"], "error")
        self.assertEqual(rows[0]["object_c"], "")
        self.assertEqual(summary["failed_pairs"], 1)
        self.assertEqual(summary["valid_pairs"], 3)
        self.assertEqual(sensor.cancels, 1)

    def test_interrupted_acquisition_is_separate_from_read_failures(self):
        result, rows, summary, sensor = self.run_fake(KeyboardInterrupt(), 1_000_000)
        self.assertEqual(result, 130)
        self.assertEqual(summary["attempts"], 1)
        self.assertEqual(summary["valid_pairs"], 0)
        self.assertEqual(summary["failed_pairs"], 0)
        self.assertEqual(summary["interrupted_pairs"], 1)
        self.assertEqual(summary["errors"], {})
        self.assertTrue(summary["interrupted"])
        self.assertEqual(rows[0]["status"], "interrupted")
        self.assertEqual(rows[0]["object_c"], "")
        self.assertEqual(sensor.cancels, 0)

    def test_interrupted_recovery_preserves_the_original_read_failure(self):
        result, rows, summary, sensor = self.run_fake(
            native.ReadError("PEC", "bad PEC"), 1_000_000, KeyboardInterrupt())
        self.assertEqual(result, 130)
        self.assertEqual(summary["attempts"], 1)
        self.assertEqual(summary["valid_pairs"], 0)
        self.assertEqual(summary["failed_pairs"], 1)
        self.assertEqual(summary["interrupted_pairs"], 0)
        self.assertEqual(summary["errors"], {"PEC": 1})
        self.assertTrue(summary["interrupted"])
        self.assertEqual(rows[0]["status"], "error")
        self.assertIn("INTERRUPTED", rows[0]["recovery_error"])
        self.assertEqual(sensor.cancels, 1)

    def test_fatal_timeout_stops_without_cancel_or_further_reads(self):
        _, rows, summary, sensor = self.run_fake(native.ReadError("HID_TIMEOUT", "late reply", True), 1_000_000)
        self.assertEqual(len(rows), 1)
        self.assertTrue(summary["fatal_transport_error"])
        self.assertEqual(sensor.cancels, 0)

    def test_overruns_count_missed_slots_instead_of_bursting(self):
        _, rows, summary, _ = self.run_fake(None, 150_000_000)
        self.assertEqual([row["scheduled_s"] for row in rows], ["0.0", "0.2"])
        self.assertEqual(summary["attempts"], 2)
        self.assertEqual(summary["missed_slots"], 2)

    def test_rate_uses_the_full_measurement_window(self):
        _, rows, summary, _ = self.run_fake(None, 1_000_000)
        self.assertEqual(len(rows), 4)
        self.assertEqual(summary["elapsed_seconds"], .4)
        self.assertEqual(summary["successful_pairs_per_second"], 10)


if __name__ == "__main__":
    unittest.main(verbosity=2)
