# Known issues and next discriminating tests

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

Windows native build/import, 19 fake-device/scheduler tests, a five-second 20 Hz simulation and HID enumeration passed. Actual exclusive-access hardware trials on 2026-10-10 then completed 20/20 pairs at 2 Hz for 10 seconds, 300/300 at 10 Hz for 30 seconds, and 600/600 at 20 Hz for 30 seconds, with zero read errors or missed slots. The 20 Hz trial measured 19.9997 successful pairs/s, acquisition p95 12.2658 ms and start lateness p95 0.7282 ms. Every valid pair used six HID exchanges. See the [hardware record](../05_Data/NATIVE_HARDWARE_TESTS.md) for conditions and additional runs. Sensor output refresh and host polling remain distinct; no matched browser benchmark was performed.

The first native startup stopped before sensor reads because the bridge reported SCL low, SDA high, no pending read and divider 118. One controlled I2C cancellation, without USB soft reset, was followed by high SCL/SDA and successful runs. This establishes that recovery worked for that observed state. It does not explain the original low SCL, establish cold-start reliability, or resolve the historical browser speed-set `0x21` hypothesis.

A later 20 Hz run stopped with Ctrl+C: its CSV contains 474 valid rows, one interrupted acquisition and zero read-error rows. The original summary incorrectly counted the interrupted pair as a failure. Reporting now counts `failed_pairs` and `interrupted_pairs` separately; regression tests cover both interruption during acquisition and interruption after an actual read failure during cancellation. Original measurement files remain unchanged.

## Fill-in template for the next session

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
