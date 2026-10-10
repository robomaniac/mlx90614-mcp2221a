# Full project conversation handoff (chronological reconstruction)

> **Migration update — 2026-10-09:** The fetched `https://jeromedemers.com/mlx.html` exactly matched historical revision 07, and the user reports it works. Active `08_Software/mlx90614-webhid/mlx.html` now blocks automatic USB reset and retains read-error/attempt evidence. Hardware validation of these edits is pending. See [current review](PROJECT_REVIEW.md) and [validation](../05_Data/VALIDATION.md). Earlier sections describe the original development history.

**Purpose:** Make a separate VS Code coding assistant productive without needing access to the original ChatGPT chat. This is a detailed reconstruction of the technical conversation, artifacts, tested behavior, and unresolved questions. It is **not** a verbatim transcript. Review `05_Data/SELECTED_LOGS.md` for literal log lines; the original chat contains much more repeated 10 Hz logging.

## A. User's original request

- Hardware: **Melexis MLX90614 IR temperature sensor**; considering Adafruit **FT232H breakout #2264** and **MCP2221A breakout #4471**.
- User had previously found MCP2221A easier to bring up than FT232H from Python.
- Desired modern iPhone-like UI: one Connect action, live temperature in **Celsius** as large numbers, and a live scrolling graph. Open to Python or Chrome. Wanted working code while they handled wiring.
- Actual WebHID hardware seen in logs: **`MCP2221 USB-I2C/UART Combo (0x04D8:0x00DD)`**.

## B. Initial Python version succeeded after setup fixes

1. A local **Flask + Adafruit Blinka + `adafruit-circuitpython-mlx90614`** web app was generated; Python talked to MCP2221A via `hidapi`, and Flask served an HTML/CSS/JS UI.
2. On Windows PowerShell, user first ran `source .venv/bin/activate`, a Unix command, instead of `.\.venv\Scripts\Activate.ps1`. Their `pip install` ended up in **global 32-bit Python 3.9**, visible as `C:\Program Files (x86)\Python39-32` and `...win32.whl`.
3. Clicking Connect gave HID DLL error `Unable to load any of ... hidapi.dll libhidapi-0.dll`. Installing `libusb` / `libusb1` alone did not fix it.
4. The assistant recommended using **64-bit Python 3.10/3.11 in a fresh venv** and installing requirements via `python -m pip`. The user later said these instructions made the **entire project work on the first try**. The successful Python implementation is preserved under `99_Archive/python-webapp/`.
5. User disliked a setup that depended on Python package and HID DLL management. A clearer README, a **double-click `run_win.bat`**, and `build_win_exe.bat` for a packaged PyInstaller executable were added to the Python project. Their final operation on the user's PC was not independently demonstrated here.

## C. Architectural pivot: native browser HID

- User asked whether Chrome's native serial API could replace Python and whether the entire app could be self-contained HTML.
- Key distinction: MCP2221A enumerates **CDC/COM for UART** and **HID for I2C/GPIO control**. Therefore **WebHID** (not Web Serial) matches the bridge's I2C control interface. A microcontroller streaming temperatures over COM would be a different Web Serial design.
- Browser-based approach requires **Chrome or Edge**, a **secure context** (`https://` or a trustworthy local origin), and per-origin user permission for the HID device.
- A complete **single HTML file** was created with embedded style and JavaScript, no Flask or Python at runtime. HID report 0 (unnumbered input/output) works for the device seen in the logs.
- The user reported the singlefile was notably easier: click Connect and get temperatures. User also contrasted it with versions that prompt to choose an HID device.

## D. Browser UI and features added iteratively

1. Live **object temperature** and **ambient temperature** in Celsius. Sensor register readings: object RAM `0x07`, ambient RAM `0x06`; basic word decoding `0.02 K/LSB - 273.15`.
2. I2C at **100 kHz**, default sensor address `0x5A`, MCP2221A HID command exchange.
3. Modern dark, translucent, rounded card UI. Two numerical temperature cards, dual-trace graph, Connect/Disconnect buttons, status badges, and diagnostic log.
4. User noticed sample count stopping around **240 points**. A later revision increased bounded graph history to **5000 points** while separately tracking **total samples**. Limit is a UI/history cap, not a physical sensor limit.
5. Sample rate dropdown added: **1, 2, 4, 5, and 10 Hz**. Default **2 Hz**; 10 Hz was treated as a high-rate/experimental setting.
6. **Mouse hover** on graph shows precise stored object and ambient Celsius values and sample timestamp/number.
7. User provided a screenshot of the desired dropdown. The UI was revised with a dark rounded button, blue glowing border, white dropdown, and blue hover selection. Screenshot preserved as `04_Media/sample-rate-dropdown-reference.png`.
8. User spotted literal `\n` strings in the debug log. Logging was later changed to actual newline characters, retained the latest **700 log lines**, and throttled high-frequency success logging.
9. Transient sensor errors were handled with read retries; yellow warning should occur only after **3 consecutive failures**, not a single skipped sample. User wanted to avoid alarming connection errors at 10 Hz.

## E. Browser permission behavior

- Sometimes clicking Connect immediately uses an already approved board; sometimes Chrome displays a permission chooser.
- Reason: `navigator.hid.getDevices()` returns previously authorized devices **for the current browser origin**; otherwise `navigator.hid.requestDevice()` opens the chooser after a click.
- Moving between `file://`, `http://127.0.0.1`, `localhost`, and `https://jeromedemers.com` changes permissions / origin, so one-time selection may recur.
- `Transport: output 0x00 / input 0x00` means **unnumbered HID reports**, normal for this device. Not a warning.
- User stated the hosted page URL: **https://jeromedemers.com/mlx**. No hosting provider, server folder, or actual deployed page bytes were established.

## F. Live-reading results and errors observed

- A long user log showed many successive successful samples at **10 Hz**, object ~35 deg C and ambient ~28 deg C. This proves that WebHID → MCP2221A → MLX90614 reads were working at least during portions of that session.
- During the 10 Hz run, occasional `Object temperature word reports the MLX90614 error flag` and `Ambient temperature word reports the MLX90614 error flag` occurred, followed by I2C cancel messages `byte2=0x10`. There were also long stretches of `Timed out waiting for HID input report`, followed by intermittent recovery.
- User changed the rate to **1 Hz** after 10 Hz failures; later logs show successful lower-rate reads interspersed with some errors. A detailed error rate / root-cause determination was **never established**.
- Candidate causes discussed: bus pull-ups, wiring, sensor timing, HID command sequencing, stale reports, concurrency between tabs/apps, and MCP2221A I2C engine state. None is proven solely from the transcript.
- The log's raw `\n` formatting was an **application logger bug**, separate from the hardware communication failures.

## G. Connection regression after subsequent patches (unresolved)

Following various logging, retry, and startup-sequence changes, the user reported repeated failure to connect:

**First diagnostic failure:**

```text
[10:11:05 PM] I2C cancel result: byte2=0x10
[10:11:05 PM] Connect failed: MCP2221A did not accept the new I2C speed. Status byte3=0x21.
```

**After a cancel-and-retry patch:**

```text
[10:53:02 PM] Set speed got busy status 0x21. Retrying after another cancel. SCL=1 SDA=1 pending=0 currentDivider=0x00.
[10:53:03 PM] Connect failed: MCP2221A kept reporting busy while setting I2C speed (status byte3=0x21). SCL=1 SDA=1 pending=0 currentDivider=0x00.
```

**After skipping an initial cancel on what the code called a 'fresh' engine:**

```text
[11:12:42 PM] Fresh MCP2221A I2C engine detected; skipping initial cancel before first speed set. SCL=1 SDA=1 pending=0 requested=0 transferred=0 buffered=0 currentDivider=0x00.
[11:12:42 PM] Set speed got busy status 0x21. Retrying after a short wait. SCL=1 SDA=1 pending=0 requested=0 transferred=0 buffered=0 currentDivider=0x00.
[11:12:44 PM] Speed-set command stayed busy even though the I2C engine now looks idle. ... Continuing with the MCP2221A current I2C speed and probing the MLX90614 anyway.
[11:12:45 PM] Connect failed: I2C engine stayed busy for command 0x94. Last response: 0x01
```

An assistant then recognized the **fallback to I2C reads when current divider was still `0x00` was not validated**. Patches were made to avoid this fallback and eventually try an MCP2221A **soft reset** (`0x70` + key), re-enumeration, and startup retry. The latest `08_Software/mlx90614-webhid/mlx.html` has this recovery code.

**Crucial:** The user **did not post new hardware results for the latest soft-reset build** before asking to move the project to VS Code. Do not assume it solved the `0x21` problem. The code's 'fresh engine' label is a **software heuristic**, not a hardware-proven diagnosis. `SCL=1/SDA=1` only excludes those lines being stuck low at that instant, not every electrical or timing issue.

The user's question, "Is it because I have some other page using it? What changed?", remains partly open. Multiple tabs/apps could interfere, but logs alone do not establish that as the cause. Earlier code revisions made the recovery more elaborate and sometimes moved the failure to a later step; the root fault was not shown to be fixed.

## H. Sensor-family extensibility request

The user asked if the entire project is just HTML and whether the same single file can operate other sensors. Answer: **yes, reusable shell, but sensor drivers must change**. The current source is sensor-specific: addresses, register sequence, PEC, 16-bit format, and Celsius conversion are MLX90614-specific. MCP2221A WebHID, UI, graph, and logging can be reused for other compatible I2C sensors. No reason to migrate to Web Serial unless the hardware architecture changes.

## I. Current handoff request

User now wants to **move the entire conversation into Visual Studio Code** and continue with a coding assistant. Deliver all available source snapshots, the reliable architectural decisions, UI desires, exact errors and failed experiments, and a prioritized next test. That is the purpose of this ZIP.

## What is verified vs not verified

| Claim | Evidence level |
| --- | --- |
| MLX90614 readout via MCP2221A was possible in Chrome | **Confirmed by user logs**, many successful values. |
| Python version worked after Windows environment fix | **Confirmed by user statement**, not re-run here. |
| HID report ID 0 works | **Confirmed by connection logs**. |
| Browser permissions can lead to chooser or remembered device | **Supported by WebHID model and user observations**. |
| Latest soft-reset HTML fixes 0x21 startup failures | **Unverified**. |
| Another open tab caused the 0x21 failures | **Hypothesis only**. |
| `currentDivider=0x00` proves a freshly powered I2C engine | **Not proven**; code uses it as a heuristic. |
| 10 Hz guaranteed indefinitely | **False as a practical guarantee**; user observed transient reads and timeouts. |
| Hosted production file is identical to any archive snapshot | **Unknown**. |

Continue with `00_Documentations/KNOWN_ISSUES_AND_TEST_PLAN.md` and `00_Documentations/NEXT_ASSISTANT_PROMPT.md`.
