# Known issues and next discriminating tests

## Latest native rerun and MCP9600 addition (2026-10-10)

The requested one-minute MLX90614 unpaced rerun completed **4,999 valid pairs from 5,000 attempts**, 83.3126 pairs/s. The first pair failed PEC (`ef3916`, received `0x16`, expected `0x3F`); the failure remained counted and the process returned exit code 1. Subsequent reads worked after the existing single I2C cancellation. This is another observed validation failure, not evidence of its cause or a fix.

The newly connected SparkFun Qwiic chip returned MCP9600 ID **`0x4014`** at **`0x60`**, configured Type K, 18-bit, filter off, continuous conversion. A separate dashboard/driver was added without editing the MLX90614 HTML or compiled transport. Native hardware/UI trials passed with errors retained, serial bridge ownership, disconnect awaiting the in-flight read and two reconnects. Direct WebHID has fake-protocol/UI coverage; its hardware check remains pending. See the [test record](../05_Data/QWIIC_THERMOCOUPLE_TESTS.md).

Next MCP9600 checks: a direct WebHID physical session; measured probe response against a known temperature reference; longer native logging; unplug/replug and actual input-range fault behavior. The physical probe type and SparkFun connector variant remain unconfirmed. No sensor configuration writes or USB reset were performed. Do not infer new conversions from the latched update flag or repeated raw words.

> **Migration update — 2026-10-09:** The fetched `https://jeromedemers.com/mlx.html` exactly matched historical revision 07, and the user reports it works. Active `08_Software/mlx90614-webhid/mlx.html` now blocks automatic USB reset and retains read-error/attempt evidence. Hardware validation of these edits is pending. See [current review](PROJECT_REVIEW.md) and [validation](../05_Data/VALIDATION.md). Earlier sections describe the original development history.

## Executive recommendation

**First A/B test the earlier reading baseline against the newest recovery build under exclusive device access.** This is more informative than piling more recovery code onto the latest file. Keep the single-file design; do not revert to the Python environment as the first troubleshooting reaction.

## Ranked observations, not guesses

| Observation (user logs) | What it establishes | What it does NOT establish |
| --- | --- | --- |
| WebHID connected with vendor `0x04D8`, product `0x00DD`, report ID 0 | USB/HID identification and command transport worked | MLX90614 I2C initialized correctly |
| Many `Read OK` lines at 10 Hz | End-to-end measurements worked for portions of the session | Perfect 10 Hz uptime or measurement accuracy |
| Temperature word error flag | Returned 16-bit word had error bit set under decoder | Hardware failure specifically |
| Periods of HID input-report timeout | Host did not receive matching HID response before deadline | Single cause among USB device state, concurrency, queuing, scheduling |
| Later `status byte3=0x21` during speed-set | MCP2221A did not accept requested speed-setting command | Why it rejected command |
| `SCL=1`, `SDA=1` | Lines reported high at sampled instant | Proof all I2C timing and wiring is healthy |
| `pending=0`, `requested=0`, `transferred=0`, `buffered=0`, `currentDivider=0x00` | Bridge response contained these specific values | Proof that `cancel` broke initialization or that another tab is responsible |
| Later `0x94` yielded busy response `0x01` | First sensor register write could not start | Specific source of bridge busy state |

## Issue 1: Startup speed command reports `0x21` (highest priority)

**Last user-reported failure:** Device authorization and HID transport succeed, `setI2CSpeed` keeps reporting byte3 `0x21`, later a `0x94` register-address write stays busy. This was a historical failure. The user now reports the hosted revision-07 app works; the migrated active revision blocks automatic reset, and its hardware test is pending.

**Candidate hypotheses (not a ranking of proven causes):**

- Another page or Python process is sending MCP2221A HID commands concurrently.
- The MCP2221A I2C engine remains in a problematic state after an earlier incomplete transfer/cancel.
- A timing or report-matching issue in the browser's asynchronous input queue produces stale/mismatched command responses.
- The startup command sequence, `cancel` order, or speed-set retry logic is wrong for the state encountered.
- A bus/electrical issue exists despite high line levels at the instant sampled.

### Next test, with expected information gain

1. Close every Chrome/Edge tab using WebHID and stop any Python/Flask test script that might access the MCP2221A.
2. If permissible, unplug/replug MCP2221A to reset the bridge. Confirm only one Chrome page is open.
3. **Test A:** Open `99_Archive/webhid-history/03-dropdown-last-reading-baseline.html` locally. Try Connect at **2 Hz**; save the whole startup log and whether sample count grows for 2 minutes.
4. Disconnect/close Test A. **Test B:** Open current `08_Software/mlx90614-webhid/mlx.html`, same machine/cable/sensor, **2 Hz**. Record startup log and results. **Automatic `0x70` reset is disabled in the active app.** Retain any reset-disabled failure log; reset-containing revision 07 requires explicit approval before a connected experiment.
5. Compare raw `0x10` response bytes before cancel and after speed-set; whether `0x94` was attempted; whether the bridge re-enumerated; and differences in recovery/cancel order.

**Interpretation:**
- **A works, B fails:** strong evidence of a code regression; isolate changes between `99_Archive/webhid-history/03` and latest, beginning with startup/cancel/speed-set paths.
- **A fails, B fails:** environmental/device state or a common protocol issue becomes more plausible, but is not proven. Test after a physical USB cycle and check wiring/pull-ups, 3.3 V/5 V logic, bus ownership.
- **A fails, B works:** recent recovery may help this state, but repeat multiple cold starts before calling it fixed.
- **Both work:** reproduce failure after running 10 Hz for several minutes and returning to Connect.

**Do not re-enable automatic USB reset without explicit approval.** Historical reset code is preserved for inspection, not enabled in the active app.

## Issue 2: high-rate word errors and HID timeouts

The user logged a 10 Hz sequence containing hundreds of successful readings, intermittent MLX90614 error flags, and later clusters of HID timeouts. At 1 Hz the sensor again returned readings, with occasional errors. No independent USB capture, scope trace, or bit-error analysis was done.

### First rate characterization

Use one hardware setup throughout. Test requested **1, 2, 5, 10 Hz** for **5 minutes per rate**, preferably from a clean connection. Capture:

- attempted read pairs and successful **object+ambient** pairs
- successful pairs per wall-clock second (actual effective Hz)
- CRC/PEC failures, raw word error flags, I2C busy responses, HID timeouts separately
- latency distribution for complete sample pairs (median, 95th percentile, maximum)
- browser focus/background status, wiring length, pull-up situation, supply/logic voltage

Do not call a pair successful if only one of ambient or object validated. Avoid silently smoothing away missed pairs in the graph. Success target should be decided from actual needs, not assumed from 10 Hz dropdown label.

### Hypothesis-isolation follow-ups

- If error rate grows with sample rate: examine overlapping requests, device busy handling, lack of time budget, retries, and browser USB event queue before changing hardware.
- If errors persist at 1 Hz: inspect SDA/SCL pull-ups and levels, connectors, power, cable, and protocol correctness.
- If only the hosted HTTPS site fails but the local HTML works: compare actual deployed source hash, page/tab count, Chrome profile/origin permissions, and background throttling. The host cannot directly make I2C transaction bytes different unless source/origin behavior or concurrent clients differ.
- If a reset temporarily helps and then failures recur: obtain a minimal reproducible timed sequence from cold start to first error.

## Issue 3: `\n` vs real newlines

Observed earlier: the debug panel rendered literal `\n` between log entries. Later source uses `state.logLines.join('\n')`, a **real JavaScript newline escape**, and caps the number of lines. This was a formatting bug, not an I2C malfunction. If it reappears, inspect the exact JavaScript string literal in the deployed HTML and compare with local file rather than editing sensor code.

## Issue 4: graph sample count apparently limited to 240

User reported apparent stop at 240. Later source retains at most **5000 points** but tracks `state.totalSamples` separately. Verify the displayed **total** continues increasing after history begins rolling; chart capacity should be explicit. Do not confuse `history.length` with total sample acquisitions.

## Issue 5: browser permission chooser reappears

Usually normal if the page has moved to another **origin** or permission was cleared. The page checks `navigator.hid.getDevices()` then falls back to `navigator.hid.requestDevice()`. Remembered access is not guaranteed across URL/origin/browser-profile changes. The working URL supplied during migration is `https://jeromedemers.com/mlx.html`; fetched bytes matched historical revision 07. The hosting server folder remains unknown, and a new origin can still request permission.

## Regression acceptance checklist

- [ ] Only one active tab/process talks to MCP2221A.
- [ ] Cold-start Connect produces a valid **ambient+object** reading at 2 Hz.
- [ ] Connect/Disconnect/reconnect works **10 times** without requiring power cycle.
- [ ] Both readings appear in Celsius; graph follows and hover displays exact stored values.
- [ ] 1/2/4/5/10 Hz selection changes scheduled polling; actual rate is measured independently.
- [ ] Chart displays >240 total samples and rolls data at 5000 plotted points.
- [ ] Log displays real line breaks, caps old messages, reports errors without per-sample spam.
- [ ] New code does not issue uncontrolled soft resets while another page is actively connected.
- [ ] 10 Hz long-run behavior is characterized, not labeled reliable without evidence.

## Issue 6: disconnect and in-flight samples

Code review found that Disconnect does not fully await an in-flight sample before closing HID. A final error or race during rapid reconnect is possible, but no hardware result establishes it as a cause. Keep this separate from the startup hypotheses. Record errors immediately after Disconnect and whether rapid reconnect differs from reconnect after a settled shutdown; defer transport changes until evidence warrants them.

## Separate native timing experiment (2026-10-10)

The [Cython + HIDAPI demo](../08_Software/mlx90614-hidapi-demo/README.md) is an additional experiment requested after the browser migration. It does not replace the active HTML or establish a fix for startup/read failures. Its transport compiles to a native extension, uses HIDAPI, retains PEC/error-bit validation, and keeps the verified 100 kHz setting. It never issues USB soft reset.

The discriminating test is the same hardware at 2/10/20 requested Hz with **one bridge client**, recording valid pairs/s, failed pairs, missed slots, start lateness and acquisition-time percentiles. Its shorter `0x94 → 0x93 → 0x40` path and lack of a fixed inter-register pause are intentional experimental differences. The demo stops on missing/malformed HID replies rather than reusing a potentially stale response, and counts nonfatal failed pairs before one I2C cancellation. No hidden sample retries are performed.

Windows native build/import, 23 fake-device/scheduler tests, simulated runs and HID enumeration are checked. Initial exclusive-access hardware trials on 2026-10-10 completed 20/20 pairs at 2 Hz for 10 seconds, 300/300 at 10 Hz for 30 seconds, and 600/600 at 20 Hz for 30 seconds, with zero read errors or missed slots. The 20 Hz trial measured 19.9997 successful pairs/s, acquisition p95 12.2658 ms and start lateness p95 0.7282 ms. Every valid pair used six HID exchanges. See the [hardware record](../05_Data/NATIVE_HARDWARE_TESTS.md) for conditions and additional runs. Sensor output refresh and host polling remain distinct; no matched browser benchmark was performed.

The subsequent [rate sweep](../05_Data/NATIVE_HARDWARE_TESTS.md#rate-sweep-and-timing-failure) increased the request to 100 Hz. Ascending 30-second trials passed through 70 Hz; 80 Hz missed 339/2,400 nominal slots and delivered 68.6992 pairs/s, while 100 Hz skipped every other slot and delivered 49.9993 pairs/s. Boundary checks missed 6 slots at 75 Hz and 1 at 72.5 Hz. One-minute repeats missed 4 slots at 70 Hz and 2 at 65 Hz; 60 Hz completed 3,600/3,600 with zero misses. All attempted pairs remained valid. This establishes a timing limit for the whole native demo, including host scheduling/output, without identifying a sensor-only maximum or resolving browser transport hypotheses.

The initial 30 Hz run exposed a separate counter artefact: rounding its period created a false final slot. Its CSV contains all 900 nominal slots with no gaps. Window count now uses nominal duration multiplied by rate independently of the rounded period, with a fake-clock regression covering integer/fractional rates. Original evidence is preserved. The CLI and launcher now accept up to 200 requested Hz for paced stress testing; this is an input bound, not a supported-throughput claim. The native extension and 100 kHz bus configuration are unchanged.

### Later unpaced comparison

The optional `-Unpaced` mode removes the target-period wait while keeping one complete HID/I2C operation at a time. Its [comparison](../05_Data/NATIVE_HARDWARE_TESTS.md#unpaced-acquisition-no-target-period) verified an avoidable scheduling gap: the new paced 100 Hz control had median 8.1601 ms between one acquisition finishing and the next starting, versus 0.0377 ms in a one-minute unpaced run. The control returned 1,500/1,500 pairs at 49.9997 pairs/s; the one-minute unpaced run returned 4,993/4,993 at 83.2022 pairs/s with no read errors. Acquisition remained around 12 ms. This supports removing the extra wait for maximum throughput; it does not establish sub-10 ms transactions or deterministic timing.

The first unpaced trial stopped at 14.9061 seconds after 1,240 valid pairs and one ambient-register `I2C_DATA` failure (`40 41 25 7f ...`), followed by an unexpected cancellation response (`10 00 00 ...`). The failed row and recovery error remain recorded. No USB reset occurred; the paced control and later 30/60-second unpaced repeats completed. Cause and recurrence rate remain unknown. Do not label the successful repeats as a fix. A subsequent discriminating test should capture the exact status before/after an error and check cancellation-response interpretation against the bridge specification, without silently retrying failed sensor samples or resetting USB.

In unpaced mode, deadline/missed-slot/lateness metrics are not applicable and are exported as null/blank. A regression verifies back-to-back reads with no target wait; additional tests verify retained read errors and stopping after a failed cancellation. The normal paced mode and its prior results remain available for comparison.

### Earlier startup and interruption evidence

The first native startup stopped before sensor reads because the bridge reported SCL low, SDA high, no pending read and divider 118. One controlled I2C cancellation, without USB soft reset, was followed by high SCL/SDA and successful runs. This establishes that recovery worked for that observed state. It does not explain the original low SCL, establish cold-start reliability, or resolve the historical browser speed-set `0x21` hypothesis.

A later 20 Hz run stopped with Ctrl+C: its CSV contains 474 valid rows, one interrupted acquisition and zero read-error rows. The original summary incorrectly counted the interrupted pair as a failure. Reporting now counts `failed_pairs` and `interrupted_pairs` separately; regression tests cover both interruption during acquisition and interruption after an actual read failure during cancellation. Original measurement files remain unchanged.

## Fill-in template for the next session

### New logger / Qwiic OpenLog

The enhanced page is a separate [Temperature Logger](../08_Software/temperature-logger/README.md). Alarms/units/recording and SD protocol have simulated checks; the original dashboards and transport remain unchanged. Actual OpenLog writes encountered address NACK at 0x2A and 0x29. A final read-only status still showed engine state 0x25, so its check stopped without cancellation/reset. Shared power/wiring and unchanged address were confirmed; the failure cause remains unknown. No card file was created. See [raw status evidence and the next hardware test](../05_Data/TEMPERATURE_LOGGER_TESTS.md). Do not report SD hardware success from simulated file/CSV equality.

With a replacement 32 GB card, steady power LED and reported USB replug, state 0x25 initially persisted. A read-only MCP9600 identity command also returned `94 01 25 ...`. Explicit approval then authorized **one** I2C cancellation: a separate status verified idle/high bus lines. OpenLog subsequently returned **0x78/firmware 2.0** at **0x2A** with card initialized. This rules out persistent absence at that address for the later session, without establishing the earlier NACK's cause.

Hardware exposed premature SD Get Data (`40 41 50 7f`); the separate new adapters now wait for read-ready state within their deadline, retaining errors. A new `T1D64F68.CSV` stored **2 of 14 header bytes**, exact readback `6b 69` (`ki`), and sync register 0x11 returned status 0x19. SparkFun v2.0 writes pointer size and lacks sync. The logger now rejects non-3.x firmware **before any card file command**. At that stage a firmware 3.x physical recording was still pending; no firmware/card reconfiguration, deletion or USB reset occurred. A later thermocouple ID read at 0x60 NACKed (`40 41 25 7f`); no additional cancellation was sent. Keep these changes local; no publish operation is authorized. GPIO alarm/record-trigger support is a documented proposal, with no pin changes or implementation yet.

An authorized FTDI firmware update is prepared: official pinned **3.1** compiled using the existing Uno/AVR toolchain, SerialPort and SdFat 1.1.4. FTDI **COM20** opens, but backup/synchronization checks at **115200** returned `resp=0x00`, including bounded retries after connection confirmation and after **physical RX/TX crossover**. No signature/backup/flash write succeeded with either arrangement. The next discriminating test is a **disconnected FTDI TX/RX loopback**; DTR/reset and serial continuity remain unproven. See [exact update, loopback and storage-test instructions](OPENLOG_FIRMWARE.md). Do not report the compilation as a completed hardware update or use repeated unchanged retries.

That disconnected FTDI loopback has now run: **0 of 16 bytes** returned within two seconds at 115200/8N1/no flow control, despite successful port-open/write calls. Windows afterward listed only COM20 with device status OK and a signed **FTDI 2.12.36.20** driver. The failed echo redirects diagnosis to the serial loop setup/adapter/driver path before OpenLog reset/bootloader testing. It does not prove a defective adapter. Actual adapter model, labeled TX/RX pins and jumper contact are the next required evidence; bypass the crossover/inverter board for a direct loop. No firmware write or additional card test was attempted.

**Later replacement-FTDI result:** the new adapter **COM21** completed a **32,768-byte original-flash backup**. The first flash command then failed during initialization, before programming was reported (`cannot obtain SW version`, unexpected sync `0x00`). A read-only traced check confirmed **ATmega328P signature `1e950f`** and valid parameter responses; the next application flash verified **all 21,698 bytes**, exit 0. **OpenLog 3.1 is now flashed.** This demonstrates working serial/bootloader communication with the replacement setup, without diagnosing the original COM20 failure or proving the intermittent initialization cause. MCP2221A was unplugged during programming; restore its Qwiic power/read connection and verify the I2C version plus a new exact-readback CSV before claiming SD recording success. No MCP2221A USB reset, EEPROM/fuse write or forced signature was used.

**Post-update SD result:** MCP2221A was restored and OpenLog returned **0x78 / 3.1 / status 0x1D** at **0x2A**, confirming the firmware and initialized card. The exclusive new `TBF8D92C.CSV` header write was followed by **SD_TIMEOUT**, read state **0x50**. One bounded cancellation of that failed read restored idle/high lines; this new file measured **0 bytes**, empty readback. A subsequent comparison without immediate write/sync status reads, matching SparkFun's library sequence, also timed out during sync. Final status: **engine 0x44, SCL=0, SDA=1, pending=0**; no subsequent recovery was sent. Extra status reads are therefore not the sole explanation. Current file size after the second attempt is unverified. Existing recordings were preserved, with no format/delete or MCP USB soft reset.

**SPI experiment result: native SD path passed.** The separate local **3.101** image keeps SPI powered during sleep; only that line and its version tag differ from pinned 3.1. A full pre-experiment backup matched official 3.1 plus the factory bootloader. **21,688 flash bytes verified**, exit 0; I2C confirmed **3.101**. New **61-byte** and **91-byte** CSVs matched exact readback, the latter with one-second idle gaps. A real native service trial at **2 Hz polling / 1 second recording** produced **19 valid reads, zero read errors, 9 saved rows**, with all **1,263 SD bytes matching the PC CSV**. Final bridge state was **0x00 / SCL=1 / SDA=1 / pending=0**, readers disconnected. The SPI sleep hypothesis is supported by these before/after results; the original failing callback was not instrumented, so other contributing causes are not ruled out. Keep this tested local image; rollback is optional, not a required next step. Standalone WebHID SD, sustained operation and repeated cold starts remain unverified. See [results](../05_Data/TEMPERATURE_LOGGER_TESTS.md#verified-3101-hardware-recording) and [reproduction/rollback](OPENLOG_FIRMWARE.md#separate-spi-experiment).

**Intermittent MCP9600 result:** the first post-3.101 check NACKed at 0x60, despite confirmed power/shared wiring. One cancellation of that failed transaction restored idle/high lines. After the delayed SD test, a bounded 0x60–0x67 probe acknowledged **0x60** immediately; STOP-separated ID and the existing native identify/sample calls returned **4014** and valid temperatures. No other addresses or extra probe cancellations were needed. The subsequent 19-read recording had no errors. This rules out persistent absence at 0x60 during the later session, without explaining the earlier NACK. Sensor configuration and wiring were unchanged. Preserve the failure in the evidence; do not silently add retries or claim cold-start reliability.

```text
Revision tested: <08_Software/mlx90614-webhid/mlx.html sha256 OR history filename>
URL/origin used: <file://, localhost, production HTTPS>
PC/OS/browser: <versions>
Exclusive USB access? <yes/no; other programs closed?>
MCP2221A USB replug first? <yes/no>
I2C wiring, voltage, pull-ups: <description>
Requested sample rate: <Hz>
Test duration: <seconds>
Attempts/successes/error types: <numbers>
Status bytes before I2C initialization: <raw hex + decoded>
First connection or read error: <literal log text>
What differed from baseline: <observed delta>
```

**250 ms follow-up:** the 2 Hz/500 ms validation mismatch is fixed by automatically raising polling at recording start. The real native 4 Hz / 250 ms SD trial passed **34 valid rows, zero errors**, median **250 ms** (235–254 ms), and **4,148 bytes of exact PC/SD equality**. No reset/cancel/reflash was used. Dark dropdown keyboard/lock behavior and the fixed viewport pulse/test button passed isolated Chrome simulations. Short native success does not establish sustained throughput or independent sensor conversions. See [the follow-up evidence](../05_Data/TEMPERATURE_LOGGER_TESTS.md#dropdown-viewport-alert-and-250-ms-recording-follow-up).


## Guided logger and shared sample schedule (2026-10-11)

The separate logger now uses Channels → Alarms & alerts → Recording, with aligned alert toggles, native threshold range controls, a full-window red pulse and a remembered light/dark theme. One interval controls acquisition and recording; every actual polling attempt during recording is retained. Custom 400 ms intervals use 2.5 Hz, and an hourly interval performs no hidden fast polls. Native commands and browser jobs remain responsive during long waits. The updated layout and cadence have fake-device/Chrome coverage; no new physical hardware test establishes the changed scheduling behavior. Previous SD measurements remain evidence for the earlier source revision. See [operation, limits and rollback](../08_Software/temperature-logger/README.md#try-the-guided-ui).

## Readable logger errors (2026-10-11)

Raw transport replies previously appeared in the main banner and recording panels without an explanation. The logger now describes the failed operation and offers **View technical details → Connection log**. A `reg=0x20` failure means the MCP9600 identity read failed; it does not establish a wiring, power or address fault by itself. Error codes and original replies remain in logs/CSV. The existing local service also reported a rejected `0x94` identity-pointer command with zero acquisition attempts; inspecting that state and rendering the new copy did not send a device command. The physical communication problem remains unresolved. No transport, recovery, sensor or firmware code changed. See [the explanation and manual checks](../08_Software/temperature-logger/README.md#understand-a-connection-error).

## Missing SD board and reconnect recovery (2026-10-11)

The supplied log and code review support a software failure chain: SD-start errors stopped the sensor worker; HID close did not clear the bridge's failed I2C state; reconnect attempted an identity read against that state. The separate logger now refuses a dirty startup before sensor access. A stopped-reader **Clear bridge error** action can cancel once and verify the released bus independently. A recoverable SD-start failure disables SD for that session while retaining PC recording and the original error; partial-file and failed-recovery warnings stay explicit. A sensor connection failure before recording no longer invents an SD session result. No automatic USB reset or sensor-sample retry was added.

32 native tests, JS checks and Chrome simulations pass, including graph alarm limits/events and consistent red alerts. The authorized physical follow-up also passed after restarting the native worker: with OpenLog disconnected, one cancellation released engine state `0x25`; a separate status verified idle/high/no pending. PC recording retained the original SD fault plus **17 valid rows at 250 ms**, with **zero sensor read errors**. Disconnect/reconnect and a subsequent **8-row PC-only recording** passed without a USB reset or power cycle. The earlier **1,573-row attempts CSV** was preserved. The reader is live again at its previous **3.5-second interval**, with SD off and recording idle. This short native trial supports the missing-SD recovery fix; cold-start, electrical and competing-reader conditions remain unverified. See [focused evidence](../05_Data/TEMPERATURE_LOGGER_TESTS.md#sd-start-isolation-bridge-recovery-and-graph-alarms-2026-10-11).

## Distinguishable alarm direction (2026-10-11)

An identical tone and red banner made a low excursion sound/look like a high excursion. The separate logger now uses **red + three short rising beeps for HIGH** and **blue + two longer falling tones for LOW**, with explicit direction labels. Pulse, sensor outline and graph alerts follow the same direction. Test high/Test low preview both sounds; enabling sound while within limits is silent. Chrome/UI checks pass, including real offline Web Audio signals, direction changes and immediate silence. The native reader remains running; reload the page to load this HTML-only change. No new device operations or firmware/backend changes occurred. Previous missing-SD hardware recovery results remain tied to their tested source revision. See [alarm operation and rollback](../08_Software/temperature-logger/README.md#set-alarms).
