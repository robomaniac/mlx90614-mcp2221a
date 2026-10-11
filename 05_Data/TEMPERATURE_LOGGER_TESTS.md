# Temperature Logger validation — 2026-10-10

The new [logger page and guide](../08_Software/temperature-logger/README.md) are separate from both existing dashboards. Software checks passed. **Local 3.101 firmware and native SD recording now passed physical tests:** 19 valid sensor reads, zero read errors, 9 saved rows, and **1,263 stored bytes matching the PC CSV exactly**. Original 2.0 truncation, official 3.1 write timeouts and intermittent sensor NACKs remain recorded below. The factory backup and official application are preserved; no changes are published.

| Check | Result |
| --- | --- |
| Native protocol/lifecycle | **19 tests passed**, with resource warnings treated as errors. Exclusive file creation, existing-file preservation, UTF-8 31-byte chunks, direct mutation-status reads, synchronization/size/close/readback, silently lost writes, stretched-read readiness/timeout, invalid data, unsupported-firmware rejection before file commands, NACK handling, forbidden commands, interval/name validation, CSV, worker lifetime and loopback origin/token guards. No physical USB used. |
| Standalone JavaScript | **PASS**, one embedded script/style, no external imports. Alarm hysteresis/opposite excursions, °C/°F, timestamp/CSV quoting, interval bounds, automatic required rate before file creation and rejection guard, skipped recording slots, SD framing, size verification, close behavior and reset/delete guards. |
| Actual Chrome / simulated WebHID | **PASS**, prior permission reused, custom names rendered as text, limits/acknowledgement/rearming, explicit audio unlock, notification permission only on click, Celsius/Fahrenheit including difference, precise hover, serial SD/sensor worker, CSV bytes matching simulated card file and real browser download. Freeze/Clear continue acquisition. Storage/read faults retained and HID closed. 390 px layout without horizontal overflow; reduced-motion preference recognized. Zero JavaScript exceptions; no physical USB opened. |
| Actual Chrome / simulated native API | **PASS**, native transport selected, recording start/stop, SD sync, whole-session CSV, units, reopening the page retains recording and restores channel names, disconnect and service shutdown. Zero JavaScript exceptions; fake sensor/card only. |
| Screenshot | Actual disconnected new-page UI, with no invented hardware readings or private content. Live cards/chart precede the settings panels. |
| Existing sources | Original infrared HTML, original thermocouple HTML, native monitor/sensor and compiled transport compared byte for byte with the previous commit; unchanged. Historical snapshots preserved. |
| Original 2.0 OpenLog hardware | **CSV RECORDING BLOCKED ON 2.0**: after one approved cancellation, ID 0x78/firmware 2.0/card-initialized response at 0x2A. Known new file `T1D64F68.CSV` stored 2 of 14 header bytes; exact readback `6b 69` (`ki`). Sync register 0x11 returned unsupported-command status 0x19. No existing file changed/deleted or firmware updated at this stage. |
| Firmware update | **FLASH VERIFIED** through replacement COM21: official pinned SparkFun 3.1 source, Uno/AVR core 1.8.8, SerialPort/SdFat 1.1.4, **21,698 application bytes verified**, exit 0. Full **32,768-byte original backup** and actual **`1e950f`** signature. First COM21 flash initialization failed before programming; read-only signature passed before traced retry. Earlier COM20 no-reply checks retained below. |
| Official 3.1 I2C/SD | **IDENTITY PASS / CSV FAIL**: 0x2A, ID 0x78, firmware 3.1, initialized status 0x1D. New `TBF8D92C.CSV` header write followed by `SD_TIMEOUT`; after one cancellation the file measured **0 bytes**. SparkFun write/sync pattern also failed during sync. Final engine **0x44**, SCL=0/SDA=1. No MCP USB reset, formatting or file deletion. |
| Local 3.101 SPI experiment | **BUILD / FLASH / NATIVE SD PASS**: 21,688 flash bytes verified; I2C version confirmed. 61-byte and 91-byte CSVs match exact readback, including one-second gaps. Native recording: **19 valid reads, zero read errors, 9 rows / 1,263 bytes**, SD equals PC CSV. Only SPI gating and version tag differ from pinned 3.1. |
| Actual disconnected FTDI loopback | **FAIL**: COM20 opened, 16 bytes submitted at 115200, **0 received** within two seconds; OpenLog disconnected. Only COM20 enumerated afterward, Windows device status OK, signed FTDI 2.12.36.20 driver. Adapter model/pinout/contact verification pending; no broken-adapter or missing-bootloader diagnosis inferred. |
| GPIO extension | Feasible design recorded in the logger README; no GPIO commands sent, pin settings changed or GPIO UI implemented. GP1 interrupt latch and electrical limits checked against Microchip; native ownership proposed for alarms/triggers. |
| Publication | **Local only, as requested.** No new commit, push or Pages deployment. Candidate files scanned for credential/private-path patterns; local helper profiles, generated measurements and native environments excluded. Workflow edits are prepared for possible future approval. |

## Hardware observations

The MCP2221A enumerated and 100 kHz was verified. The first check encountered an existing I2C error state. One I2C cancellation returned an unexpected acknowledgement; the HID response's engine state became idle. No USB soft reset was sent. Later checks used a helper with the cancellation branch removed.

At OpenLog address **0x2A**, a STOP-terminated write was accepted by the bridge, followed by this status with the address-NACK bit set:

```text
10 00 00 00 00 00 00 00 00 01 00 01 00 01 76 27 54 00 10 a8 40 60 01 01 00 00
```

At **0x29**, the next status contained I2C state 0x25 and address-NACK:

```text
10 00 00 00 00 00 00 00 25 01 00 00 00 00 76 2f 52 00 10 a8 40 60 01 01 00 00
```

A final check after wiring/address confirmation found state **0x25** still present and stopped before any I2C mutation:

```text
10 00 00 00 00 00 00 00 25 01 00 00 00 00 76 00 52 00 10 a8 40 60 01 01 00 00
```

SCL/SDA were high at these status instants. That does not identify the cause or establish successful communication. Card filesystem, board startup, continuity, actual device address and clock-stretch behavior remain unverified. No existing card file was opened, changed or deleted. The native thermocouple hardware results from the original dashboard do not validate the new SD transport.

## Next hardware test

### Replacement 32 GB card

The 8 GB card was replaced with a **32 GB** card; the power LED was reported steady and bridge USB was reported unplugged/reconnected. A new status-only check still found state 0x25 and stopped before contacting the replacement card. A subsequent read-only MCP9600 identity attempt was also rejected:

```text
Initial/final: 10 00 00 00 00 00 00 00 25 02 00 00 00 00 76 00 c1 00 10 28 40 60 01 01 00 00
Read request: 94 01 00 c0 20 00 00 00
Read response: 94 01 25 00 00 00 00 00
```

This confirmed rejection of a thermocouple transaction too; it did not diagnose the replacement card or explain why the state survived the reported replug. No cancellation, USB reset or SD write occurred during those initial follow-up checks. The proposed recovery was initially rejected by automatic approval review; explicit approval subsequently authorized the single cancellation described below. Microchip documents the subcommand in its [MCP2221A datasheet, section 3.1.1](https://ww1.microchip.com/downloads/en/DeviceDoc/MCP2221A-Data-Sheet-DS20005565D.pdf).

### Approved recovery and actual card readback

Exactly one I2C cancellation was sent after confirming the local readers were inactive. No USB reset occurred. The cancellation acknowledgement byte was unexpected, but a separate status read verified idle state and high SCL/SDA:

```text
Before: 10 00 00 00 00 00 00 00 25 02 00 00 00 00 76 00 c1 00 10 28 40 60 01 01 00 00
Request: 10 00 10
After:  10 00 00 00 00 00 00 00 00 02 00 00 00 00 76 00 c1 00 10 28 40 60 01 01 00 00
```

At 100 kHz the replacement card's OpenLog responded at **0x2A**, ID **0x78**, firmware **2.0**, status **0x15** (card initialized/root directory). The first creation response was fetched prematurely: `40 41 50 7f`. A later retrieval after the read completed returned `40 00 55 01 17`, confirming the create command succeeded. That random filename was not retained; an empty test file may remain. No deletion was attempted.

The separate native and WebHID SD adapters now wait for read state **0x54/0x55** within the existing 2-second transaction budget before issuing Get Data. They still reject NACKs, timeouts and invalid data, without automatic recovery. With this correction, a new **`T1D64F68.CSV`** was created and a 14-byte `kind,message\r\n` header was sent. The sync command failed with **`SD_COMMAND`**, register **0x11**, response status **0x19**. A bounded read-only file-size lookup closed this test's working file; stored size was **2**, and exact readback was **`6b 69`** (`ki`). No full CSV or test body was written successfully.

SparkFun's [v2.0 write implementation](https://github.com/sparkfun/Qwiic_OpenLog/blob/v2.0/Firmware/Qwiic_OpenLog/commands.ino) writes `sizeof(myData)` (a pointer), matching the observed two-byte truncation, and lacks the sync command. Its [3.x implementation](https://github.com/sparkfun/Qwiic_OpenLog/blob/master/Firmware/Qwiic_OpenLog/commands.ino) uses string length and adds sync. The logger now rejects non-3.x firmware with **`SD_FIRMWARE` before any directory/create/append command**. Simulations use 3.1 and explicitly test rejection of 1.x/2.x/unknown major versions. At that stage a 3.x physical session was pending; the subsequent update and successful local 3.101 session are recorded below.

A subsequent MCP9600 identity check at **0x60** returned **`I2C_DATA`**, `40 41 25 7f`, indicating an address NACK during that attempt. It produced no temperature reading. The error is retained; current sensor wiring/address and bus state require investigation. No second cancellation or USB reset was sent. File readback success does not establish sensor operation, measurement accuracy or reliable logger throughput.

### Authorized FTDI update preparation

The installed Arduino IDE 2 CLI **1.4.1**, AVR core **1.8.8** and AVRDUDE **8.0.0-arduino1** were reused. Firmware was fetched from SparkFun revision **`f3f6a3ec3f70fe4c14612b38fac360f26ee79a4c`**, with greiman SerialPort revision **`0a751d912af85b4a00ac4c4b8595e97df7b02166`** and SdFat **1.1.4**, without editing upstream source. The Qwiic OpenLog schematic confirms ATmega328P, a 16 MHz resonator and DTR capacitor, consistent with the official Uno target. Compilation passed: **21,698 / 32,256 flash bytes**, **1,368 / 2,048 SRAM bytes**. Application HEX SHA-256: **`61479e702b30a5718ecf46b0f3579c2f25032aaadd12883ab0a23ffe5900c2ac`**.

The FTDI USB serial adapter was identified at **COM20**, VID/PID **0403:6001**, separately from the MCP2221A UART. COM20 opened exclusively at 115200 baud. A read-only AVRDUDE backup attempt received no bootloader reply over ten retries. After wiring/DTR confirmation, a bounded two-retry backup check also returned:

```text
Warning: attempt 1 of 2: not in sync: resp=0x00
Warning: attempt 2 of 2: not in sync: resp=0x00
Error: unable to open port COM20 for programmer arduino
```

The final error string follows failed synchronization; the independent successful port-open check rules out treating it as proof the serial port was unavailable. After a confirmed physical **RX/TX crossover**, a separate two-attempt read-only backup check again reported `programmer is not responding` / `resp=0x00` and exited 1. Both local native readers were confirmed inactive before this check. **No signature was received, no backup completed and no firmware was written.** Neither serial orientation succeeded, so the next test is a **disconnected FTDI TX/RX loopback**. Reset and electrical continuity remain alternatives; AVRDUDE's normal DTR/RTS reset sequence is confirmed in its official source, but the physical reset pulse has not been measured. Normal FTDI DTR programming reset was attempted on OpenLog; no MCP2221A reset, second I2C cancellation, card formatting or deletion occurred. Complete commands, expected results, stop conditions, loopback helper and exact-readback checker are in [the firmware guide](../00_Documentations/OPENLOG_FIRMWARE.md).

### Actual disconnected FTDI loopback

After FTDI/OpenLog disconnection and TX/RX loopback setup were confirmed, `Test-FtdiLoopback.ps1` opened FTDI **COM20** at **115200, 8N1, no flow control**, with DTR/RTS disabled. Its 16-byte write returned without an exception, but **zero bytes** arrived within its two-second budget. The helper exited 1, closed the port and retained JSON evidence:

```text
Sent:     55 AA 00 FF 4F 50 45 4E 4C 4F 47 2D 46 54 44 49
Received: (empty)
Error:    FTDI loopback mismatch: received 0 of 16 bytes.
```

A separate read-only PnP/driver check listed **only COM20**, device status **OK**, provider **FTDI**, signed driver **2.12.36.20**. This confirms Windows enumeration, not physical serial continuity. With OpenLog outside the loop, its firmware cannot account for this test's missing echo. Adapter pinout, jumper/crossover contacts and adapter/driver behavior remain candidates. The next check needs the actual adapter model and shorted pin labels; bypass the crossover/inverter board in a direct labeled TX/RX loop before retrying. No firmware/EEPROM/fuse write, OpenLog reset or card access occurred in the loopback test.

### Replacement FTDI: backup and verified flash

The replacement enumerated as **COM21**, VID/PID **0403:6001**. Both native readers remained inactive. A bounded read-only backup succeeded and produced **32,768 flash bytes**, with Intel HEX checksums checked. Backup SHA-256: **`0a93c04feef4d813bf78ffbff05e1d1532cc0b396b74af1f2d66b52d97e6017d`**. It remains local/ignored as `.local/openlog-update/before-new-ftdi-COM21.hex`.

The first application flash command exited 1 during bootloader initialization, with `protocol expects sync byte 0x14 but got 0x00` / `cannot obtain SW version`; no programming was reported. Its error evidence is retained. A subsequent read-only serial trace received valid STK500 responses and **signature `1e950f`**. A fresh traced application flash then completed:

```text
Device signature = 1E 95 0F (ATmega328P, ATA6614Q, LGT8F328P)
Writing 21698 bytes to flash
21698 bytes of flash verified
Firmware flash/verification retry exit: 0
```

**3.1 application programming and verification are established.** The known source/image hash and below-bootloader address bounds were checked before writing. Normal signature/verification checks stayed enabled, with no EEPROM/fuse commands, forced signature or MCP2221A USB reset. The working replacement disproves a universal inability to contact this OpenLog bootloader, but does not identify the original adapter failure or explain the intermittent initialization failure. The later I2C/SD check below confirms the version but retains a new storage failure; current thermocouple operation remains untested.

### Post-update I2C and SD check

After FTDI power/wiring was removed and only MCP2221A reconnected, both native readers were inactive. The existing Cython/HIDAPI environment was reused, with **100 kHz I2C** and no transport rebuild or MCP USB soft reset. `check_openlog.py` returned address **0x2A**, ID **0x78**, firmware **3.1**, status **0x1D** (card initialized/root directory/file-open flag).

The exclusive new-file check created **`TBF8D92C.CSV`**, then sent the 14-byte `kind,message\r\n` header. Directory/create/append responses were **0x1F**. The following status read exceeded its **2-second** deadline (`SD_TIMEOUT`); the bridge remained in read state **0x50**, with no pending bytes. A later status showed both lines high; Get Data returned **`40 41 50 7f`**, with no completed data. One bounded cancellation of this failed read restored idle/high lines. A size/readback check of this new test file returned **0 bytes**, empty readback. This observation precedes the comparison below; it does not establish the file's size after the later failed attempt.

To isolate the extra immediate status read, a comparison used [SparkFun's library sequence](https://github.com/sparkfun/SparkFun_Qwiic_OpenLog_Arduino_Library/blob/master/src/SparkFun_Qwiic_OpenLog_Arduino_Library.cpp): append the same known-empty new test file, write the header without a following status read, then send sync without a following status read. This also failed during **sync**, with `HID_TIMEOUT`; a subsequent status-only check found:

```text
10 00 00 00 00 00 00 00 44 01 00 01 00 01 76 00 54 00 08 28 00 60 00 01 00 00
engine=0x44, SCL=0, SDA=1, pending=0
```

No queued HID reports were drained on reopening, and no further recovery was sent after this comparison. The extra status read is therefore **not sufficient to explain the failure**. Card free space, supply integrity and firmware callback behavior remain possible causes; none is established. Existing recordings were not modified/deleted, and no formatting occurred. The new test file may be empty or partial; preserve it. Do not start sensor readers on the observed stuck bus.

### Separate SPI experiment

The [pinned firmware](https://github.com/sparkfun/Qwiic_OpenLog/blob/f3f6a3ec3f70fe4c14612b38fac360f26ee79a4c/Firmware/Qwiic_OpenLog/Qwiic_OpenLog.ino) disables SPI after 500 ms idle, then restores it after the wake interrupt returns. Its Wire callbacks perform SD operations within interrupts. A callback that needs SD SPI while that peripheral is gated could therefore stall. **This is a hypothesis, not a diagnosis**; the recorded command sequence does not establish that sleep was active when the failure began. SD timeout handling inside an interrupt is a separate concern not addressed by this experiment.

A copy keeps SPI powered during sleep and tags itself **3.101** (local experiment, not a SparkFun release). Only those two lines differ; the upstream copy is unchanged. Compilation succeeded using the existing toolchain/libraries: **21,688 flash bytes**, highest address **0x54B7** (below **0x7E00**), **1,368 SRAM bytes**, **680 SRAM bytes free**. Intel HEX checksums and address bounds passed. SHA-256: **`ca930c7fd55c4fd5b75c2ef84dd1d6557b99f143fe2a4ed49101fce9453ae1ef`**. Flashing and native hardware tests subsequently passed, as recorded below. Keeping SPI powered may increase idle consumption. The official 3.1 image and original full-flash backup remain available. See [complete experiment and rollback instructions](../00_Documentations/OPENLOG_FIRMWARE.md#separate-spi-experiment).

### Verified 3.101 hardware recording

The working FTDI **COM21** read a new **32,768-byte** pre-experiment backup. Its application bytes matched the official 3.1 image, and **0x7E00–0x7FFF** matched the original bootloader. All Intel HEX checksums passed. Backup SHA-256: **`fa95537cb9123a2217a117597ca2fbf5a4ea17485a5b1ff92b86f5ad0b19f808`**. A PowerShell boolean typo interrupted the result-saving step after that read; the saved output and complete memory were independently validated before flashing. The subsequent experiment flash completed with **`21688 bytes of flash verified`**, exit **0**, signature **`1e950f`**. No EEPROM/fuse write, forced signature or MCP USB soft reset occurred.

After FTDI was removed and Qwiic/MCP2221A restored, OpenLog returned **3.101**, ID **0x78**, address **0x2A**, initialized status **0x1D**. Two new exclusive CSVs passed exact readback:

| New file | Test | Stored bytes | Result |
| --- | --- | --- | --- |
| `T645CD8F.CSV` | Header plus test row | 61 | Exact match |
| `T8F4AE50.CSV` | One-second gaps before creation, both row writes, sync and readback | 91 | Exact match |
| `T927E188.CSV` | Actual native thermocouple recording | 1,263 | Exact match to downloaded PC CSV |

The first MCP9600 identity read after the initial CSV check returned **`I2C_DATA` / `40 41 25 7f`**, despite confirmed board power and shared-bus connection. A status-only check found **engine 0x25 / SCL=1 / SDA=1 / pending=0**. One cancellation of this failed transaction restored idle/high lines, then the delayed SD test above passed. A bounded probe of MCP9600 addresses **0x60–0x67** stopped at its first address: **0x60 acknowledged**, STOP-separated ID read returned **`4014`**, and the existing native identify/sample calls passed. No other addresses or additional cancellations were needed. The sensor configuration stayed Type K, 18-bit, filter off, continuous conversion. The earlier NACK's cause remains unresolved; it is not discarded from the results.

The real native logger service at port **8768** was then tested through its existing API, with **2 Hz polling**, **1 second recording interval**, names **Bench probe / Cold junction**, and OpenLog enabled. Recording lasted **8.407 seconds**; the full acquisition session contained **19 attempted / 19 valid / zero failed reads**, with **9 rows selected for recording**. Stop reported **SD synchronized, size verified, file closed**. After disconnecting the reader, exact I2C readback of `T927E188.CSV` matched the downloaded PC recording CSV, **1,263 bytes**, SHA-256 **`5af65b4bf436075da7a4bd59b477650144cd176d059f727049d4325f22063bdd`** on both sides. Final bridge state was **0x00, SCL=1, SDA=1, pending=0**; both readers were disconnected.

Both local services were restarted to replace temporary session tokens exposed in a diagnostic output; the replacements were verified privately. Token values are excluded from retained/public evidence. The existing native build was reused. All earlier failure evidence and existing recordings remain, without formatting/deletion. These short tests support the SPI sleep hypothesis and verify this **native** storage path; they do not establish standalone browser SD operation, long-duration reliability or repeated cold-start behavior.

### Dropdown, viewport alert and 250 ms recording follow-up

The previous 250 ms validation error occurred with **2 Hz polling (500 ms)**, before creating an SD file. The UI now validates settings first, raises polling to the required **4 Hz** at Start recording, then starts the worker recording. Failed rate changes prevent recording/file creation. A hint explains the pending rate adjustment; rates are not lowered automatically.

All seven dropdowns use matching dark menus. Actual isolated Chrome tests with fake HID/native APIs passed keyboard selection, Escape/outside-click closing, selected labels and recording locks. The screen alert is now a **fixed viewport overlay**, with a bright border, warm tint and top label cycling every two seconds. Chrome verified six-second preview/early stop, reduced-motion steady styling, persistence while scrolling, disabling the option, acknowledgement, and stale/disconnected monitoring pause. Audio behavior is preserved. The final UI screenshots were captured and inspected. These UI tests use simulated sensors; they are distinct from the physical native SD test below.

With explicit approval, the real native service recorded to one new exclusive file at **4 Hz polling / 0.25 seconds recording**, using the already-built native extension and local OpenLog **3.101**. Previous PC CSV was backed up locally first. The reader was disconnected by the time the trial began, so it was connected for the test and returned to **disconnected / 2 Hz** afterward.

| Measurement | Observed result |
| --- | --- |
| File / elapsed recording | `T108E52A.CSV` / **8.4287 s** including the stop response |
| Attempts / valid / failures during trial | **34 / 34 / 0** |
| Recorded rows / faults | **34 / 0** |
| Recorded interval | Median **250 ms**, min **235 ms**, max **254 ms** |
| PC CSV / SD size | **4,148 bytes / 4,148 bytes** |
| Exact contents | **PASS**, complete I2C card readback equals downloaded PC CSV |
| PC and SD SHA-256 | `244d0712d3b735ccad3893154f5fffd750905e21d8a8260aa3879ec5d1658c3a` |
| Finalization | Synchronization/size verified; file closed; final bridge idle with high SCL/SDA |
| Recovery / existing files | No I2C cancellation, USB reset, flash, format or deletion |

This establishes a short successful native 250 ms SD run on this card. It does not guarantee sustained throughput or independent 4 Hz sensor conversions: the preserved 18-bit MCP9600 conversion time is **320 ms plus calculation**. The count divided by the stop-response duration includes the initial sample and is not an independent conversion-rate measurement. Follow the [updated-control steps](../08_Software/temperature-logger/README.md#try-the-updated-controls-on-the-running-native-logger) to repeat through the dashboard; stop and retain evidence on failure.

### Manual checks

1. **Completed:** local 3.101 flashing, Qwiic restoration, identity/sensor checks and exact native recording readback. For normal use, reuse **http://127.0.0.1:8768/** without rebuilding or reflashing. Keep other readers disconnected.
2. In desktop **Chrome/Edge**, open or reload **http://127.0.0.1:8768/**, select **2 Hz**, then **Connect sensor**. Expect valid MCP9600 temperatures. Set names and **Save every = 1 second**, enable **Also save to Qwiic OpenLog** at **0x2A**, then **Start recording**. Expect a new filename, increasing recorded rows and verified byte count. Stop on errors and retain the connection log.
3. Click **Stop & sync**, wait for **file closed**, download **Recorded CSV**, then **Disconnect**. To inspect the SD externally, remove power before moving the card. Preserve the earlier test files and current recording; do not format/delete existing contents. Compare the new card CSV with the downloaded CSV.
4. **Optional new-board/card check:** with all readers disconnected, follow [the complete identity/exact-readback commands](../00_Documentations/OPENLOG_FIRMWARE.md#check-the-firmware-and-one-new-sd-file). It creates one new exclusive test CSV. Original 2.0 must still report **SD_FIRMWARE** before file creation. Stop on the first failure; do not loop cancellation/reset or repeatedly change addresses.

If SD initialization fails, inspect the existing filesystem/configuration in a card reader before considering formatting. Preserve existing card contents. Config/address changes or formatting are outside this logger's commands.

Repeat executable software checks using the [complete README commands](../08_Software/temperature-logger/README.md#checks-and-return-to-the-old-page). Machine-readable simulated results and source hashes are in [TEMPERATURE_LOGGER_RESULTS.json](TEMPERATURE_LOGGER_RESULTS.json). No rate, calibrated accuracy, standalone operation or durable-storage guarantee is inferred from the simulations.

### Explicit Stop & sync completion result

The native service retained a successful close sentence, but the page mixed it with row/file/byte metadata in a small status line. The UI now adds a persistent result directly below the recording buttons: **Closing SD file…** while waiting, **SD file closed** in green only for a stopped recording with the service/browser's successful synchronized-size-and-close result, **SD close not confirmed** for faults/unconfirmed completion, and **Recording stopped · SD was off** for a PC-only recording. An active recording cannot display a stale successful close sentence. The completion uses the recording's actual SD settings, independent of the checkbox for the next recording.

JavaScript checks cover native/browser completion wording, pending-stop precedence, active/stale-message rejection, failed stop/sync, lost transport and PC-only outcomes. Isolated Chrome checks with fake WebHID/native readers verify the visible green result after Stop & sync, persistence across native reload, removal at the next recording start and the PC-only explanation. The result screenshot was captured and inspected. No additional physical card writes, cancellation/reset or service restart were needed; prior exact SD readback evidence remains unchanged. See [operation instructions](../08_Software/temperature-logger/README.md#record-on-sd).

## Guided UI and one sampling/recording schedule (2026-10-11)

This revision implements the selected guided layout: **Channels → Alarms & alerts → Recording**, threshold handles synchronized with exact numeric limits, aligned speaker/screen toggles and test buttons, a full-viewport red pulse, a session summary and a remembered light/dark theme. Original monitor pages and the compiled transport are preserved.

The former interval-based selection of readings is removed. **Every actual poll during recording becomes a recorded row**. The shared interval sets the exact polling frequency, including custom 400 ms / 2.5 Hz and hourly polling. There are no hidden fast polls at an hourly interval. Overdue acquisition slots are skipped rather than fabricated; read faults and SD faults remain in the PC CSV. Native and browser workers stay responsive to stop/disconnect during long waits.

**Software validation:** 22 native fake-device tests and standalone JS/protocol checks pass. Actual Chrome tests with simulated HID/native APIs verify continuous recorded sequence numbers, exact PC/SD CSV equality, error retention, units/names, dropdown keyboard behavior, slider keyboard/numeric synchronization, light/dark persistence, pulse/acknowledgement/reduced motion, CSV download, native reload continuity, and 1487/1024/768/390 px layouts. Browser Disconnect now retains a previously confirmed SD-close result. These are simulated device tests, not a new physical SD measurement.

The disconnected local service was restarted once to load scheduling changes; its previous state and CSV files were preserved locally. No sensor connection, new physical card write, USB reset, cancellation or firmware flash occurred. Prior hardware results above apply to the earlier source revision; source fingerprints in the machine-readable follow-up distinguish that revision from the current software checks. A new physical trial of the shared schedule remains pending. See [operation and exact recovery commands](../08_Software/temperature-logger/README.md#try-the-guided-ui).

## Readable error messages (2026-10-11)

**UI/protocol checks passed** for the reported native `reg=0x20 reply=40 41 25 7f…`, the current rejected `0x94` command, and the browser `Register 0x20: …` format. Checks also cover configuration/temperature failures, raw SD/USB replies, unchanged readable validation/close messages, unconfirmed SD-close warnings, and exact original error retention in CSV. Acquisition and transport source were unchanged; the earlier 22 native tests were not repeated for this presentation-only update.

An isolated Chrome test rendered the actual local service's error without connecting to hardware, verified readable banner/recording panels and the details link, and injected display-only faults to check raw action diagnostics and HTML escaping. The 390 px layout had no horizontal overflow. Before/after service snapshots were identical; the test browser made only GET requests, with no API writes, sensor/card commands or JavaScript exceptions. The communication failure remains unresolved. Current source fingerprints and the previous broader software revision are retained separately in [the machine-readable evidence](TEMPERATURE_LOGGER_RESULTS.json).

## SD-start isolation, bridge recovery and graph alarms (2026-10-11)

The supplied failure log showed the bridge still at engine state `0x25` after HID close, then a rejected identity-pointer command on reconnect. Code review found that every SD-start exception escaped the worker, while the shared native configuration check did not reject that non-idle engine state. The separate logger now checks startup state before sensor access, tracks SD outcomes separately, and offers **Clear bridge error** while its reader is stopped. Original sensor/native transport files and archived pages are preserved.

**32 native fake-device/lifecycle/API tests pass**, without resource warnings. They cover missing-SD PC fallback, original fault retention in both CSVs, subsequent PC-only sessions, partial-file warnings, refusal to continue after failed recovery or missing USB replies, one cancellation followed by an independent idle-status check, live-reader exclusion, origin/token guards and CSV preservation. The recovery helper accepts an observed omitted acknowledgement only when a separate status actually verifies idle/high/no pending; it never treats that reply alone as success. The low-level SD adapter still does not recover itself; cleanup is serialized through the logger that owns the failed transaction.

Standalone JS/protocol checks and isolated **Chrome WebHID/native API simulations pass** for SD fallback and its storage summary, reload continuity, the recovery action, matching border/label/banner red in dark/light and reduced-motion modes, high/low graph lines, alarm/reset markers, silence/rearm/automatic reset, °C/°F and 390 px layout. A separate read-only Chrome check against the existing real service confirmed the restart notice and guards against using old native code for SD start/recovery. Broader simulated CSV/download/SD-close checks also pass.

**Authorized physical follow-up: passed.** The old native worker was stopped through its API, its **1,573-row attempts CSV** preserved, and the updated worker started in the existing environment. With OpenLog physically disconnected from the shared bus, SD start returned `SD_I2C_STATE` / engine `0x25`. Exactly **one I2C cancellation** returned engine `0x00`; its acknowledgement byte was omitted, so only the **separate status** confirming idle, SCL/SDA high and no pending read established recovery. PC recording then retained **17 valid temperature pairs plus the original SD error**, with **zero sensor read errors**. The same error is present in the attempts CSV. The missing board was detected before file creation. Disconnect/reconnect passed, followed by a separate **8-valid-row PC-only recording**, without USB reset, USB power cycle or sample retry. The worker is left live at **one poll every 3.5 seconds**, recording idle and SD off. Read-only Chrome verified the updated service, no restart notice, enabled recording, restored interval and no JavaScript exceptions. This short native trial does not establish sustained/cold-start behavior or standalone WebHID recovery. No card write occurred because OpenLog was disconnected; earlier card-write results retain their original source fingerprints. See [operation and recovery steps](../08_Software/temperature-logger/README.md#recover-from-a-missing-sd-logger-or-bridge-error).

## Distinct high/low alarm signals (2026-10-11)

The logger HTML now distinguishes **red HIGH** alerts with **three short rising beeps** from **blue LOW** alerts with **two longer falling tones**. Banner, viewport border/label, highlighted sensor outline, graph limit/region/event and desktop-notification title follow the alarm direction. Explicit HIGH/LOW labels accompany the colors. Separate **Test high / Test low** buttons work without connecting and do not enable ongoing audio. Enabling sound within limits stays silent. A direct high-to-low change stops scheduled high tones before the low pattern; Silence alarm also cancels scheduled tones immediately.

**Chrome checks passed:** previews and live/repeating patterns; direct high-to-low transition; both monitored channels; silence/rearm and strict reset thresholds; matching colors in dark/light and reduced motion; °C/°F graph limits/markers; named notification titles; 390 px controls without horizontal overflow. Real Chrome **OfflineAudioContext** rendered both patterns and verified signal energy in every expected tone window, silence in the gaps and completed-node cleanup. Offline rendering does not play through speakers. The missing-SD/reconnect simulated regression and standalone JS/protocol checks also pass.

Read-only Chrome inspection of the actual native dashboard confirmed the two preview controls and color/sound key with the sensor still live and no new sensor errors. It made GET requests only. No hardware operation, native-worker restart or firmware change occurred; previous hardware evidence retains its original source hashes. Speaker output and browser/OS audio settings remain outside these checks. See [exact reload, preview and HTML rollback instructions](../08_Software/temperature-logger/README.md#set-alarms).
