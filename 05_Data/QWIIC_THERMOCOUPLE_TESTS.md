# Qwiic thermocouple hardware and UI checks

Recorded **2026-10-10**. The existing native Cython/HIDAPI environment and compiled MCP2221A transport were reused. Only one reader controlled the bridge at a time. The bus stayed at **100 kHz**; no USB reset or sensor configuration writes were issued. [Machine-readable evidence](QWIIC_THERMOCOUPLE_RESULTS.json) contains tested-source SHA-256 fingerprints, raw-file hashes, summaries and retained errors. Raw CSVs remain local under the respective ignored output folders.

## Requested MLX90614 rerun

The exact previously supplied unpaced command was executed for one minute:

| Result | Measurement |
| --- | --- |
| Requested duration / actual elapsed | 60 s / 60.002925 s |
| Attempts / valid / failed | **5,000 / 4,999 / 1** |
| Successful pairs per second | **83.3126** |
| Acquisition p50 / p95 / max | 11.9581 / 12.0178 / 12.9806 ms |
| Valid completion interval p50 / max | 12.0000 / 13.0203 ms |
| Error | One **PEC** failure, first pair |
| Command exit status | **1**, because a read failed |

The ambient register's first returned bytes were `ef3916`: received PEC `0x16`, expected `0x3F`. The pair was rejected and logged. One existing I2C cancellation completed; subsequent 4,999 pairs validated. This trial did not pass a zero-error criterion and does not identify the cause of the first failure. In unpaced mode, missed-slot and lateness metrics are not applicable.

The original CSV is `hardware_unpaced_20261010T194637_599055Z.csv`, accompanied by its unchanged summary. Both hashes and the actual error row are recorded in the evidence JSON. Earlier [unpaced trials and their failure](NATIVE_HARDWARE_TESTS.md#unpaced-acquisition-no-target-period) remain preserved.

## Connected thermocouple sensor

A targeted read of the MCP9600 ID/configuration/temperature registers found:

| Field | Actual returned data |
| --- | --- |
| I2C address | `0x60` |
| Device / revision | **`0x4014`**: MCP9600, revision 0x14 |
| Sensor configuration | `0x00`: **Type K**, digital filter off |
| Device configuration | `0x00`: **18-bit ADC**, 0.0625 °C cold-junction resolution, continuous operation |
| Status | `0x4F`, input-range bit clear |
| First probe / board values | **22.625 / 24.3125 °C**, raw words `016A / 0185` |

These identify the chip and its configured type. They do not identify the exact SparkFun connector variant, supply voltage, physical thermocouple type or probe/cable ratings. The board/probe BOM marks those unknowns in the [operating guide](../08_Software/qwiic-thermocouple/README.md#hardware-and-bom).

The new driver sets the pointer before every read and handles two-byte **big-endian signed** temperature words at **0.0625 °C/LSB**, without MLX90614 PEC. It checks input-range status before and after each pair. Sensor configuration, latched conversion-update bits and alert settings are preserved. It stops on read faults instead of retrying, cancelling or resetting.

## Final native dashboard hardware sessions

Chrome drove the actual loopback dashboard through its controls. The first session ran at 2 Hz for about 30 seconds, then switched to 4 Hz while testing chart controls. Two short reconnect sessions used 4 Hz.

| Session | Actual elapsed | Valid / attempts | Errors | Acquisition p50 / p95 / max |
| --- | ---: | ---: | ---: | --- |
| Main UI test, 2 → 4 Hz | 36.961 s | **86 / 86** | 0 | 23.9556 / 24.4280 / 25.5655 ms |
| Reconnect 1, 4 Hz | 3.147 s | **13 / 13** | 0 | 23.7796 / 24.1818 / 24.1818 ms |
| Reconnect 2, 4 Hz | 3.153 s | **13 / 13** | 0 | 23.9367 / 24.5792 / 24.5792 ms |

**112/112 valid pairs** in these final sessions. CSV row counts, statuses and temperature decoding were checked independently against the reported counters. The acquisition includes four register reads: status, probe, board, status. The original infrared app and native extension were unchanged.

| UI / operation check | Result |
| --- | --- |
| Native setup / launcher reuse | PASS: existing dependencies and extension reused; no rebuild |
| Connect / actual readings / sensor configuration display | PASS with the physical sensor |
| 2 → 4 Hz polling control | PASS; changes host rate while sensor configuration is preserved |
| Chart freeze | PASS; valid count continues increasing while the plot is frozen |
| Precise hover | PASS; tooltip shows stored temperatures to four decimal places and acquisition time |
| Clear chart | PASS; earlier data remains in the session CSV |
| CSV button download | PASS; actual browser download created; server CSV row count matches attempts after disconnect |
| Disconnect / stale last values | PASS; stops acquisition, waits for the in-flight sample, closes HID and dims retained values |
| Two reconnects | PASS; new chart/counters/CSV, correctly identified sensor on each connection |
| Stop local server | PASS; reader closes and the loopback server exits through the UI |
| Responsive layout | PASS at 1,344 px desktop and 390 px mobile viewport, with no horizontal overflow; screenshots inspected |
| Native address field | PASS; hidden because the server owns the selected address |
| Unauthenticated connection request | PASS; rejected before any bridge access |
| JavaScript exceptions | None during the final native hardware/UI checks |

![Actual native thermocouple dashboard](../04_Media/qwiic-thermocouple-live.png)

## Software and standalone WebHID checks

**11 native fake-device/lifecycle tests passed**, including negative temperatures, byte order, exact read length without PEC, partial data, malformed/failed I2C data without hidden retries, identity validation before configuration reads, an input-range fault appearing during a pair, prohibited register access, retained error CSVs and disconnect awaiting an in-flight read.

The dependency-free JS checker passed syntax, single-file packaging and fake HID protocol tests, including wrong identity, negative words, stale/mismatched reply stop and reset-command guard.

A separate real Chrome tab exercised the **standalone WebHID UI with fake reports**: remembered permission reuse, negative Celsius values, disconnect/reconnect, input-range failure stopping acquisition, failed-attempt/CSV evidence, closed handle and no USB reset. No physical USB operation occurred in that test. The harness was adjusted to wait for initialization instead of assuming it finished after a fixed delay; the completed test had no JavaScript exceptions.

## Limits and next checks

Physical tests exercised **native Cython/HIDAPI**, not the direct WebHID thermocouple transport. Public delivery checks do not validate USB behavior. These short sessions do not establish calibrated temperature accuracy, longer-run reliability or independent conversion timestamps.

At the observed 18-bit setting, Microchip specifies nominal ADC conversion of **320 ms**, plus calculation time. Polling at 4 Hz can reread a conversion. Update bit 6 is latched and is not cleared by this read-only driver, so it is not counted as a fresh sample. Microchip also describes self-heating from frequent I2C activity; the MLX90614's unpaced stress mode was not applied to this board. See the [datasheet](https://ww1.microchip.com/downloads/en/DeviceDoc/MCP960X-L0X-RL0X-Data-Sheet-20005426F.pdf) and [errata](https://ww1.microchip.com/downloads/aemDocuments/documents/OTH/ProductDocuments/Errata/MCP9600-Data-Sheet-Errata-80000741.pdf).

Remaining: direct WebHID hardware test, longer native recording, unplug/replug behavior, physical probe/range-fault checks and a comparison against a known temperature reference. Use the [complete operating/check/cleanup commands](../08_Software/qwiic-thermocouple/README.md); no repeat installation/build is needed with the existing environment.
