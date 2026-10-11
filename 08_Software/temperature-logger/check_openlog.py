"""Explicit Qwiic OpenLog identity/new-file check; no recovery or erase commands."""
from datetime import datetime, timezone
from pathlib import Path
import argparse
import hashlib
import json
import secrets
import sys
import urllib.error
import urllib.request

from sdcard import CardBus, OpenLog
from sensor import Bridge, Thermocouple


def check_readers():
    for port in (8766, 8768):
        try:
            with urllib.request.urlopen(f'http://127.0.0.1:{port}/api/state', timeout=2) as response:
                state = json.load(response)
        except urllib.error.URLError as error:
            if isinstance(error.reason, ConnectionRefusedError) or getattr(error.reason, 'winerror', None) == 10061:
                continue
            raise RuntimeError(f'Cannot confirm reader on port {port} is idle; disconnect/stop it first.') from error
        recording = state.get('recording') or {}
        if state.get('phase') not in ('disconnected', 'error') or recording.get('phase') in ('starting', 'recording', 'stopping'):
            raise RuntimeError(f'Reader on port {port} is active; disconnect it before this check.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--sd-address', type=lambda value: int(value, 0), choices=(0x29, 0x2A), default=0x2A)
    parser.add_argument('--write-test', action='store_true', help='Create one new CSV and verify its complete readback.')
    parser.add_argument('--check-sensor', action='store_true', help='Also read MCP9600 identity/temperatures at 0x60.')
    args = parser.parse_args()
    import hid

    output = Path(__file__).resolve().parent / 'output'
    output.mkdir(exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S_%fZ')
    result_path = output / f'openlog_check_{stamp}.json'
    result = dict(mode='ACTUAL_OPENLOG_HARDWARE', timestamp_utc=stamp,
                  write_test_requested=args.write_test, exact_readback=False,
                  i2c_hz=100000, usb_reset=False, i2c_cancel=False,
                  existing_files_deleted=False, existing_recording_files_modified=False)
    device, bridge, trace = None, None, []

    class TracedCardBus(CardBus):
        def exchange(self, payload, deadline):
            reply = super().exchange(payload, deadline)
            trace.append({'tx': bytes(payload).hex(' '), 'rx': reply[:26].hex(' ')})
            return reply

    exit_code = 0
    try:
        check_readers()
        devices = hid.enumerate(0x04D8, 0x00DD)
        if len(devices) != 1:
            raise RuntimeError('Expected exactly one MCP2221A; no device opened.')
        device = hid.device()
        device.open_path(devices[0]['path'])
        bridge = Bridge(device, address=0x60, timeout_ms=150)
        initial = bridge.exchange(b'\x10')
        result['initial_bridge_status'] = initial[:26].hex(' ')
        if initial[8] != 0 or initial[25] or initial[22] != 1 or initial[23] != 1:
            raise RuntimeError('Bridge is not idle with high bus lines. Stopped without cancellation or USB reset.')
        bridge.configure()
        card = OpenLog(TracedCardBus(bridge), args.sd_address)
        result['openlog'] = card.identify()
        print('OpenLog:', json.dumps(result['openlog']))
        if args.write_test:
            payload = 'kind,message\r\nSD_TEST,New-file write and exact I2C readback\r\n'
            filename = 'T' + secrets.token_hex(4).upper()[:7] + '.CSV'
            result['new_file_candidate'] = filename
            card.start('kind,message\r\n', filename)
            result['new_file'] = filename
            card.write('SD_TEST,New-file write and exact I2C readback\r\n')
            result['stored_bytes'] = card.finish()
            readback = card.read_file(result['stored_bytes'])
            if readback != payload.encode('utf-8'):
                raise RuntimeError('SD readback differs from the intended CSV.')
            result.update(exact_readback=True, sha256=hashlib.sha256(readback).hexdigest(),
                          expected_bytes=len(payload.encode('utf-8')))
            (output / filename).write_bytes(readback)
            print(f'PASS: {filename}, {len(readback)} bytes, complete CSV readback matches.')
        if args.check_sensor:
            sensor = Thermocouple(bridge)
            result['sensor'] = {'info': sensor.identify(), 'reading': sensor.sample()}
            print('MCP9600:', json.dumps(result['sensor']))
    except Exception as error:
        result.update(error_code=getattr(error, 'code', type(error).__name__), error=str(error))
        print('FAIL:', result['error_code'], result['error'], file=sys.stderr)
        exit_code = 1
    finally:
        try:
            if bridge is not None:
                bridge.close()
            elif device is not None:
                device.close()
        except Exception as error:
            result['close_error'] = str(error)
            exit_code = 1
        result['trace'] = trace
        result_path.write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
        print('Evidence:', result_path)
    return exit_code


if __name__ == '__main__':
    raise SystemExit(main())
