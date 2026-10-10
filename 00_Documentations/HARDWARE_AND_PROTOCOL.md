# Hardware, protocol, code map, and extensibility

> **Migration update — 2026-10-09:** The fetched `https://jeromedemers.com/mlx.html` exactly matched historical revision 07, and the user reports it works. Active `08_Software/mlx90614-webhid/mlx.html` now blocks automatic USB reset and retains read-error/attempt evidence. Hardware validation of these edits is pending. See [current review](PROJECT_REVIEW.md) and [validation](../05_Data/VALIDATION.md). Earlier sections describe the original development history.

## Current hardware

| Component | Identity / role |
| --- | --- |
| Sensor | **Melexis MLX90614BAA**, supplied marking `BAA7160B20`; 3 V chip, breakout identity unknown |
| USB bridge | **MCP2221A**; Adafruit #4471 is the project reference board, physical board identity unconfirmed |
| Other board mentioned originally | **Adafruit FT232H breakout (#2264)**, *not* the board in the successful WebHID logs |
| Host | Windows PC with Google Chrome/Edge, WebHID-enabled secure page |
| USB identity seen in logs | MCP2221 USB-I2C/UART Combo, VID `0x04D8`, PID `0x00DD` |
| Report format seen in logs | **Unnumbered** HID input/output, `reportId = 0`. This is normal. |
| Site mentioned by user | `https://jeromedemers.com/mlx.html` (fetched source matched revision 07; server folder unknown) |

### Wiring

```text
PC USB  ->  Adafruit MCP2221A (#4471)
                  |        |        |        |
                 SDA      SCL      GND      VCC (appropriate breakout supply)
                  |        |        |        |
                 SDA      SCL      GND      VIN/VCC
                   Melexis MLX90614 sensor/breakout
```

I2C requires **SDA pull-up and SCL pull-up** to a supply compatible with **both** devices' logic levels. Existing breakouts may provide these resistors; inspect the actual board(s) before adding another pair. The chip marking identifies a 2.6–3.6 V MLX90614BAA. A confirmed Adafruit #4471 reference board provides default 3.3 V pull-ups of about 5.1 kΩ; actual board/module wiring and jumper settings remain unconfirmed. See the root BOM and its manufacturer references. Avoid assuming the bare MLX90614 and breakout share the same voltage tolerance.

## Why Chrome WebHID, not Web Serial

- The MCP2221A **HID** interface exposes I2C and GPIO commands. JavaScript uses `navigator.hid` to communicate with this interface.
- The MCP2221A **CDC/COM** interface exposes USB-to-UART functionality, **not** the I2C master commands used here.
- A separate MCU that streams JSON/CSV over UART/USB-CDC could use Web Serial, but that would require a different firmware/hardware architecture.
- Direct Chrome/WebHID has no required backend or install. The browser enforces origin-specific device permissions and may display a device picker.

## MLX90614 sensor data

- Default address: **7-bit `0x5A`**, unless its configuration has been changed.
- Ambient temperature register: **RAM `0x06`**.
- Object temperature channel 1 register: **RAM `0x07`**.
- Driver reads a **3-byte SMBus word + packet error code** (low data byte, high data byte, PEC).
- Raw data word error flag is checked (`word & 0x8000`), while temperature data is extracted from remaining bits.
- Decoding in current source:

```js
const rawWord = lsb | (msb << 8);
const sensorErrorFlag = Boolean(rawWord & 0x8000);
const value = rawWord & 0x7fff;
const tempC = value * 0.02 - 273.15;
```

- PEC: CRC-8 polynomial `0x07` over `[addrWrite, register, addrRead, lsb, msb]` as implemented. If PEC mismatches, the reading is rejected rather than plotted as a legitimate temperature.
- An error-flag report can represent a rejected/invalid sensor word; based on the log alone we cannot decide whether it originated from sensor state, timing, noisy bus, or a malformed read.

## MCP2221A I2C / HID packet flow

The page creates 64-byte HID packets and probes the device's reported input/output modes. In the user's case both report IDs are `0`. Commands currently used:

| Code | Function in current code |
| --- | --- |
| `0x10` | Status/Set Parameters (also I2C speed setting and cancellation). |
| `0x90` | I2C write with STOP, when requested. |
| `0x94` | I2C write **without STOP** (send MLX register address). |
| `0x91` | I2C read with STOP, when requested. |
| `0x93` | I2C **repeated-start read** for the word + PEC. |
| `0x40` | Retrieve buffered I2C data from the bridge. |
| `0x70` | MCP2221A reset command, **present only in historical revision 07; blocked before send in active source**. |

Normal MLX90614 word read sequence as implemented:

1. HID send `0x94` to I2C address `0xB4` (`0x5A << 1`) with one data byte containing the MLX register number.
2. HID send `0x93` to I2C address `0xB5` for 3 bytes with a repeated START.
3. Poll bridge readiness using `0x10`; retrieve 3 bytes using `0x40`.
4. Check sensor error bit and PEC; convert to °C; store the reading and update the graph.

The app normally sets I2C bus speed to **100 kHz** using the MCP2221A divider. As coded:

```text
divider = round(12,000,000 / 100,000 - 2) = 118 = 0x76
f_I2C ≈ 12,000,000 / (divider + 2)
```

The `0x10` speed-set response byte 3 is interpreted by the existing implementation as `0x20` accepted, `0x21` not accepted. The specific failure state must be interpreted alongside raw status and the datasheet. An apparently idle bus (`SCL=1`, `SDA=1`) does not by itself guarantee the MCP2221A command engine will accept a new speed.

**Do not infer that `currentDivider=0x00` alone definitively means a fresh/uninitialized device.** That was the old assistant's unverified interpretation, later encoded as a heuristic in recovery logic.

## Current JavaScript structure

Open **`08_Software/mlx90614-webhid/mlx.html`**, use VS Code search (`Ctrl+F` or `Ctrl+Shift+F`) for:

| Symbol / feature | Meaning |
| --- | --- |
| `getCandidateDevices` | Fetch prior permission via `getDevices()`; otherwise show WebHID chooser. |
| `detectWorkingTransport` | Inspect report descriptors and probe HID report transport. |
| `rawExchangeWithMode` / `exchange` | Send/receive HID reports; handle input event queue and timeouts. |
| `getStatus` / `setI2CSpeed` | MCP2221A state and I2C clock. |
| `cancelI2cTransfer` | Request I2C transfer cancellation. |
| `softResetAndReconnectDevice` | Throws `SOFT_RESET_DISABLED` before USB send; historical implementation reset/re-enumerated the bridge. |
| `prepareI2cEngineWithRecovery` | Startup sequence and retry/fallback behavior (recent regression area). |
| `i2cWrite` / `i2cReadStart` / `getI2cData` | Generic I2C operations over MCP2221A. |
| `readMlxWord` / `decodeMlxTemperature` | MLX90614 protocol and temperature conversion. |
| `validateMlxWord` / `readValidatedMlxWord` | Error-bit, PEC checking and retries. |
| `sampleSensor` / `pollingLoop` | Read ambient/object pair at requested rate. |
| `addPoint` / `drawChart` / `updateTooltip` | History, graph canvas, mouse-hover measurements. |
| `renderLog` / `log` | Bound log lines with actual newline separators. |

### Sample rate and graph limits

- User selectable: **1, 2, 4, 5, 10 Hz**.
- Default **2 Hz**. Nominal requested interval `1000 / rateHz` milliseconds.
- Actual rate may be lower if the pair of USB/I2C reads, retries, and browser scheduling takes longer than the interval. The current code polls sequentially, so higher requested Hz does not guarantee higher successful Hz.
- Graph stores at most **5000 latest points**, with a separate running total count. The older issue of an apparent hard stop at 240 was addressed in later versions.
- Debug view retains latest **700 lines** in later versions and throttles routine success logs.

## Page origin / device permissions

Chrome WebHID access must occur in a secure context. HTTPS hosting or local development via `http://localhost` / `http://127.0.0.1` works. `file://` may work depending on browser policy. Previously authorized HID devices are retrievable through `navigator.hid.getDevices()` on the **same origin**. Calling `requestDevice()` on a new origin shows the user the picker; scripts cannot bypass that permission control.

Potential contention: leave **only one sensor page or Python reader actively talking to the bridge**. Multiple tabs showing a page do not prove they both issued conflicting USB transactions, but simultaneous access is a serious troubleshooting variable.

## Adapting to more I2C sensors

Keep the WebHID transport and UI as a reusable shell. Replace `MLX90614_ADDRESS`, sensor-specific register writes/reads, byte order, CRC/PEC if applicable, conversion, units/labels and measurement latency. Test against each new sensor datasheet; do **not** reuse the MLX90614 `0.02 K/LSB` conversion by default.

## Manufacturer and platform references

- [Microchip MCP2221A product page](https://www.microchip.com/en-us/product/mcp2221a)
- [Microchip MCP2221A data sheet (DS20005565D)](https://ww1.microchip.com/downloads/en/DeviceDoc/MCP2221A-Data-Sheet-DS20005565D.pdf)
- [Melexis MLX90614 product and documentation](https://www.melexis.com/en/product/mlx90614/digital-plug-play-infrared-thermometer-to-can)
- [Adafruit MCP2221A breakout (#4471)](https://www.adafruit.com/product/4471)
- [Adafruit FT232H breakout (#2264)](https://www.adafruit.com/product/2264)
- [Chrome WebHID API docs](https://developer.chrome.com/docs/capabilities/hid)
- [MDN WebHID API](https://developer.mozilla.org/en-US/docs/Web/API/WebHID_API)

The links identify reference material; this handoff does not claim a fresh manufacturer review or exact byte-for-byte compliance audit of every code path.
