"""Bounded recovery of an owned I2C transaction; never reset USB or retry a sample."""
import time
from sensor import Bridge, ReadError, Thermocouple


def open_bridge(address=0x60, device_index=None):
    import hid
    devices = hid.enumerate(0x04D8, 0x00DD)
    if not devices:
        raise ReadError('NO_BRIDGE', 'No MCP2221A found. Check the USB connection.')
    if device_index is None and len(devices) != 1:
        raise ReadError('MULTIPLE_BRIDGES', 'Multiple bridges found; use --device-index.')
    index = 0 if device_index is None else device_index
    if not 0 <= index < len(devices):
        raise ReadError('DEVICE_INDEX', 'Selected bridge index is unavailable.')
    device = hid.device()
    try:
        device.open_path(devices[index]['path'])
        return Bridge(device, address=address, timeout_ms=150)
    except Exception:
        device.close()
        raise


def idle(status):
    return (len(status) == 64 and status[0] == 0x10 and status[1] == 0
            and status[8] == 0 and status[25] == 0 and status[22:24] == b'\x01\x01')


def open_sensor_checked(address, device_index=None):
    bridge = open_bridge(address, device_index)
    try:
        status = bridge.exchange(b'\x10')
        if not idle(status):
            raise ReadError('BRIDGE_DIRTY', 'Bridge has an unfinished I2C operation. Use Clear bridge error with other readers closed. Status: ' + status[:26].hex(' '))
        bridge.configure()
        return Thermocouple(bridge)
    except Exception:
        bridge.close()
        raise


def clear_i2c_error(bridge, log=lambda message: None):
    """Inspect first; at most one cancellation, then independently verify idle."""
    deadline = time.perf_counter_ns() + 300_000_000
    status = bridge.exchange(b'\x10', deadline)
    log('I2C recovery status before: ' + status[:26].hex(' '))
    if idle(status):
        log('I2C already idle; no cancellation sent.')
        return
    response = bridge.exchange(b'\x10\x00\x10', deadline)
    log('I2C cancellation reply: ' + response[:26].hex(' '))
    if len(response) != 64 or response[0] != 0x10 or response[1] or response[2] not in (0, 0x10, 0x11):
        raise ReadError('RECOVERY_REPLY', 'Bridge did not accept I2C recovery: ' + response[:26].hex(' '))
    # Some observed replies omit the cancellation acknowledgement. Such a reply
    # alone is never success: a separate status must prove idle/high/no pending.
    for _ in range(12):
        time.sleep(.002)
        status = bridge.exchange(b'\x10', deadline)
        if idle(status):
            log('I2C recovery verified idle, SCL/SDA high, no pending read: ' + status[:26].hex(' '))
            return
    raise ReadError('RECOVERY_BUSY', 'Bridge remains busy after one I2C cancellation. Status: ' + status[:26].hex(' '))
