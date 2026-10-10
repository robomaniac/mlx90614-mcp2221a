"""Separate terminal demo: native HIDAPI/Cython, absolute deadlines, CSV evidence."""
from collections import Counter, deque
from datetime import datetime, timezone
from pathlib import Path
import argparse
import csv
import json
import math
import sys
import time


def next_slot(origin, period, minimum_slot, now):
    """Skip elapsed deadlines, without cumulative drift or catch-up bursts."""
    return max(minimum_slot, (max(0, now - origin) + period - 1) // period)


def distribution(values):
    values = sorted(values)
    if not values:
        return {key: None for key in ("p50", "p95", "p99", "max")}
    return {key: round(values[max(0, math.ceil(len(values) * percentile) - 1)], 4)
            for key, percentile in (("p50", .5), ("p95", .95), ("p99", .99), ("max", 1))}


class SimulatedSensor:
    """Clearly labelled artificial readings; never opens a HID device."""
    def __init__(self, native):
        self.native = native
        self.index = 0
        self.exchanges = 0

    def read_pair(self):
        time.sleep(.002)
        self.index += 1
        values = []
        for register, celsius in ((0x06, 24.0), (0x07, 30 + math.sin(self.index / 10))):
            raw = round((celsius + 273.15) / .02)
            word = raw.to_bytes(2, "little")
            pec = self.native.crc8(bytes([0xB4, register, 0xB5]) + word)
            values.append(self.native.decode_word(word + bytes([pec]), 0x5A, register))
        return values[1][0], values[0][0], values[1][1], values[0][1]

    def cancel(self):
        pass

    def close(self):
        pass


FIELDS = ("mode", "slot", "scheduled_s", "start_s", "finish_s", "start_lateness_ms",
          "acquisition_ms", "successful_interval_ms", "object_c", "ambient_c",
          "object_raw", "ambient_raw", "repeated_raw_pair", "hid_exchanges",
          "status", "error_code", "error", "recovery_error")


def acquire(sensor, native, args, path):
    period = round(1_000_000_000 / args.hz)
    duration = round(args.seconds * 1_000_000_000)
    slots = (duration + period - 1) // period
    latency, lateness, intervals = (deque(maxlen=10000) for _ in range(3))
    errors = Counter()
    attempts = successes = failures = interrupted_pairs = missed = repeated = slot = 0
    last_success = last_raw = last_values = None
    interrupted = fatal = False
    mode = "SIMULATED" if args.simulate else "HARDWARE"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=FIELDS)
        writer.writeheader()
        stream.flush()
        origin = time.perf_counter_ns()
        end = origin + duration
        next_display = origin
        try:
            while slot < slots:
                planned = origin + slot * period
                while (remaining := planned - time.perf_counter_ns()) > 0:
                    time.sleep(remaining / 1_000_000_000)
                start = time.perf_counter_ns()
                if start >= end:
                    missed += slots - slot
                    break
                attempts += 1
                before = sensor.exchanges
                row = dict.fromkeys(FIELDS, "")
                row.update(mode=mode, slot=slot, scheduled_s=(planned - origin) / 1e9,
                           start_s=(start - origin) / 1e9,
                           start_lateness_ms=(start - planned) / 1e6, status="ok")
                try:
                    obj, ambient, object_raw, ambient_raw = sensor.read_pair()
                    finish = time.perf_counter_ns()
                    successes += 1
                    raw_pair = (object_raw, ambient_raw)
                    same = raw_pair == last_raw
                    repeated += int(same)
                    interval = (finish - last_success) / 1e6 if last_success is not None else None
                    if interval is not None:
                        intervals.append(interval)
                    row.update(object_c=round(obj, 4), ambient_c=round(ambient, 4),
                               object_raw=object_raw, ambient_raw=ambient_raw,
                               repeated_raw_pair=int(same), successful_interval_ms=interval if interval is not None else "")
                    last_success, last_raw, last_values = finish, raw_pair, (obj, ambient)
                except native.ReadError as error:
                    finish = time.perf_counter_ns()
                    failures += 1
                    errors[error.code] += 1
                    row.update(status="error", error_code=error.code, error=str(error))
                    print(f"ERROR slot={slot} {error.code}: {error}", file=sys.stderr, flush=True)
                    fatal = error.fatal
                    if not fatal:
                        try:
                            sensor.cancel()  # Failed attempt remains in CSV; no hidden sample retry.
                        except native.ReadError as recovery_error:
                            row["recovery_error"] = f"{recovery_error.code}: {recovery_error}"
                            errors["RECOVERY_" + recovery_error.code] += 1
                            print("ERROR recovery: " + row["recovery_error"], file=sys.stderr, flush=True)
                            fatal = True
                        except KeyboardInterrupt:
                            row["recovery_error"] = "INTERRUPTED during I2C cancellation"
                            interrupted = True
                except KeyboardInterrupt:
                    finish = time.perf_counter_ns()
                    interrupted_pairs += 1
                    row.update(status="interrupted", error_code="INTERRUPTED", error="Stopped during acquisition.")
                    interrupted = True
                row.update(finish_s=(finish - origin) / 1e9, acquisition_ms=(finish - start) / 1e6,
                           hid_exchanges=sensor.exchanges - before)
                latency.append(row["acquisition_ms"])
                lateness.append(row["start_lateness_ms"])
                writer.writerow(row)
                now = time.perf_counter_ns()
                if now >= next_display or row["status"] == "error":
                    stream.flush()
                    display = f" object={last_values[0]:.2f} C ambient={last_values[1]:.2f} C" if last_values else ""
                    print(f"{mode} attempts={attempts} valid={successes} missed_slots={missed}" + display, flush=True)
                    next_display = now + 1_000_000_000
                if fatal or interrupted:
                    break
                new_slot = min(slots, next_slot(origin, period, slot + 1, time.perf_counter_ns()))
                missed += new_slot - slot - 1
                slot = new_slot
            # Include the whole requested measurement window in the rate denominator.
            if not fatal and not interrupted:
                while (remaining := end - time.perf_counter_ns()) > 0:
                    time.sleep(remaining / 1_000_000_000)
        except KeyboardInterrupt:
            interrupted = True
            print("Stopped with Ctrl+C; saving completed measurements.")
        elapsed = (time.perf_counter_ns() - origin) / 1e9
    summary = {
        "mode": mode, "requested_hz": args.hz, "requested_seconds": args.seconds,
        "elapsed_seconds": round(elapsed, 6), "attempts": attempts, "valid_pairs": successes,
        "failed_pairs": failures, "interrupted_pairs": interrupted_pairs, "missed_slots": missed,
        "successful_pairs_per_second": round(successes / elapsed, 4) if elapsed else 0,
        "repeated_raw_pairs": repeated, "errors": dict(errors), "interrupted": interrupted,
        "fatal_transport_error": fatal, "timing_window_pairs": len(latency),
        "acquisition_ms": distribution(latency), "start_lateness_ms": distribution(lateness),
        "successful_interval_ms": distribution(intervals), "i2c_hz": 100000,
        "sensor_address": args.address, "register_budget_ms": args.timeout_ms,
        "timestamp_definition": "Host monotonic acquisition start/end; not sensor conversion timestamps.",
        "freshness_note": "Identical raw words can reflect a steady temperature or repeated sensor data.",
    }
    with path.with_suffix(".summary.json").open("x", encoding="utf-8") as stream:
        json.dump(summary, stream, indent=2)
        stream.write("\n")
    print(json.dumps(summary, indent=2))
    print("CSV: " + str(path))
    return 130 if interrupted else 1 if fatal or errors or not successes else 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--list", action="store_true", help="Enumerate matching HID devices without opening them.")
    parser.add_argument("--simulate", action="store_true", help="Artificial data; no USB access.")
    parser.add_argument("--hz", type=float, default=10, help="Requested pair rate, 0.1 to 50 Hz; default 10.")
    parser.add_argument("--seconds", type=float, default=30, help="Run duration in seconds; default 30.")
    parser.add_argument("--address", type=lambda value: int(value, 0), default=0x5A, help="7-bit address; default 0x5A.")
    parser.add_argument("--timeout-ms", type=int, default=100, help="Per-register transaction budget; default 100 ms.")
    parser.add_argument("--device-index", type=int, help="Index from --list; required when multiple matches exist.")
    parser.add_argument("--csv", type=Path, help="New CSV file; an existing file is never overwritten.")
    parser.add_argument("--trace", action="store_true", help="Print HID TX/RX bytes; affects timing.")
    args = parser.parse_args()
    if not math.isfinite(args.hz) or not .1 <= args.hz <= 50:
        parser.error("--hz must be finite and between 0.1 and 50.")
    if not math.isfinite(args.seconds) or args.seconds <= 0:
        parser.error("--seconds must be finite and positive.")
    if not 0x08 <= args.address <= 0x77 or not 1 <= args.timeout_ms <= 5000:
        parser.error("Use a non-reserved 7-bit address and --timeout-ms between 1 and 5000.")
    if args.list and args.simulate:
        parser.error("Choose --list or --simulate.")
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S_%fZ")
    path = args.csv or Path(__file__).resolve().parent / "output" / f"{'simulated' if args.simulate else 'hardware'}_{stamp}.csv"
    if not args.list and (path.exists() or path.with_suffix(".summary.json").exists()):
        parser.error("Output already exists. Choose a new --csv filename.")
    try:
        import hid
        if args.list:
            devices = hid.enumerate(0x04D8, 0x00DD)
            for index, device in enumerate(devices):
                print(f"[{index}] {device.get('product_string') or 'MCP2221A'} VID=04D8 PID=00DD")
            if not devices:
                print("No MCP2221/MCP2221A found (VID=04D8 PID=00DD).")
            return 0
        import mcp2221_native as native
    except ImportError as error:
        print(f"Setup incomplete: {error}. Run the README installation and build commands.", file=sys.stderr)
        return 2
    sensor = None
    try:
        if args.simulate:
            sensor = SimulatedSensor(native)
        else:
            devices = hid.enumerate(0x04D8, 0x00DD)
            if not devices:
                raise RuntimeError("No matching bridge. Connect MCP2221A and run --list again.")
            if args.device_index is None and len(devices) != 1:
                raise RuntimeError("Multiple matching devices. Run --list and supply --device-index.")
            index = args.device_index if args.device_index is not None else 0
            if not 0 <= index < len(devices):
                raise RuntimeError("Device index is outside the --list results.")
            device = hid.device()
            try:
                device.open_path(devices[index]["path"])
            except BaseException:
                device.close()
                raise
            sensor = native.Bridge(device, args.address, args.timeout_ms, args.trace)
            sensor.configure()
            print("HARDWARE: 100 kHz confirmed; native Cython transport + HIDAPI; no USB soft reset.")
        return acquire(sensor, native, args, path)
    except (native.ReadError, OSError, RuntimeError) as error:
        print("STOP: " + str(error), file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("Stopped during setup; HID handle closed.", file=sys.stderr)
        return 130
    finally:
        if sensor is not None:
            sensor.close()


if __name__ == "__main__":
    raise SystemExit(main())
