# Coding-assistant project instructions

## User preferences

Give complete numbered setup, operation, test and cleanup instructions. Name the application/shell, working directory and prerequisites. Define inputs before using them, provide complete copyable commands, explain success/failure and where to stop. Mark optional actions and distinguish completed work from remaining user actions. Explain why repeating a build, restart or configuration is necessary and when an existing session can be reused. Keep executable instructions in the main README or a clearly linked guide. Keep credentials and private URLs out of documentation, screenshots and chat.

## Goal and source authority

Continue this self-contained single-file Chrome/Edge WebHID app reading a Melexis MLX90614 through a Microchip MCP2221A. Preserve its modern dark UI and usability. Read `README.md`, `00_Documentations/PROJECT_REVIEW.md`, `00_Documentations/PROJECT_HISTORY.md`, `00_Documentations/KNOWN_ISSUES_AND_TEST_PLAN.md`, `05_Data/SELECTED_LOGS.md`, `00_Documentations/HARDWARE_AND_PROTOCOL.md` and `05_Data/VALIDATION.md` before changing device code.

- Active source: `08_Software/mlx90614-webhid/mlx.html`. It derives from revision 07 with automatic USB reset blocked and diagnostics corrected. Hardware validation of this edited revision is pending.
- `99_Archive/webhid-history/07-latest-soft-reset-recovery.html` exactly matched the fetched `https://jeromedemers.com/mlx.html` before migration. The user reports that site works. This is source identity plus user testimony, not independent validation of error rates.
- `99_Archive/webhid-history/03-dropdown-last-reading-baseline.html` is the closest surviving comparison before high-rate logs; it is a candidate, not a confirmed identical deployed revision.
- History is immutable provenance: copy a baseline for experiments; never rewrite snapshots in place.
- Original ZIPs, legacy Python/early prototype and the complete original handoff are local-only ignored archives. They are not browser dependencies.
- Do not import professional requirements, confidential skill content or other projects into this personal experiment. Preserve existing skills; do not create new ones unless asked.

## Hard constraints

1. Keep one deployable HTML, with embedded CSS/JS, no mandatory external libraries/CDNs/build/backend.
2. Target desktop Chrome/Edge WebHID. MCP2221A CDC/COM carries UART; I2C commands use HID, not Web Serial.
3. Preserve Connect, prior-permission reuse via `navigator.hid.getDevices()` and chooser fallback, Disconnect, object/ambient °C, live chart, precise mouse hover, 1/2/4/5/10 Hz, custom dropdown and bounded chart/log history.
4. Retain every failed register attempt and failed sample in the bounded log. Distinguish successful valid pairs from attempted pairs and recovered retries. Never guarantee 10 Hz.
5. Preserve normal 100 kHz I2C unless hardware evidence motivates a change.
6. Automatic MCP2221A soft reset is disabled. Do not reintroduce or test automatic `0x70` reset without describing HID/UART disconnection implications and obtaining explicit user approval. Historical revision 07 still contains it.
7. Never claim a hardware fix verified without actual hardware tests or supplied proving logs.
8. Keep edits small, diffable and reversible; do not replace a working version merely to refactor.

## Debugging method

Establish the specific next discriminating test; separate observations from hypotheses. Compare candidate vs active with one bridge client. For speed-set `0x21`, inspect raw `0x10` requests/responses, ordering, status, bus levels, pending state and contention. SCL/SDA high describes one instant; divider `0x00` alone does not prove power-on state. Examine cancel ordering and stale input reports before assigning blame. For rate failures measure successful pair rate, missed pairs and time to timeout at 1/2/5/10 Hz with unchanged wiring. Log essential transport bytes and throttle recurring success only, not errors.

## Protocol boundaries

Reported VID/PID `0x04D8:0x00DD`; confirm other firmware separately. Default sensor address `0x5A`, ambient register `0x06`, object register `0x07`. Reject MSB error flag; decode valid 15-bit word as `raw * 0.02 - 273.15`. Verify SMBus PEC using CRC-8 poly `0x07`. This device uses unnumbered HID reports (`reportId=0`). Commands include status/parameters `0x10`, write-no-stop `0x94`, repeated-start read `0x93`, buffered data `0x40`. No external browser imports.

## Checks, layout and publishing

Use the numbered layout shown in the main README. Run from repository root:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\08_Software\mlx90614-webhid\tools\Check-Html.ps1 -Diagnostics
```

This checks syntax and simulated diagnostic behavior only. The public target is `robomaniac/mlx90614-mcp2221a`, MIT, `main`. Verify authenticated owner before publishing. Stage only curated files, inspect the staged diff and scan for credentials/confidential material. Never stage ignored originals, private settings or helper credentials. GitHub Pages packages only active HTML as `index.html`; see `00_Documentations/GITHUB_PAGES.md`.

When delivering changes, report what changed and why, what was actually validated and what could not be, the exact HTML to run, baseline recovery procedure and expected pass/fail logs. Update the known-issues plan when hardware evidence accepts or rules out a hypothesis. Do not invent hardware evidence from static checks.
