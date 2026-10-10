# MLX90614 Cython + HIDAPI demo

A separate terminal experiment for measuring acquisition timing with the **same MLX90614 + MCP2221A**. The bridge transport and PEC decoder compile from `mcp2221_native.pyx`; USB calls use the native [Cython HIDAPI binding](https://github.com/trezor/cython-hidapi). The existing [single-file browser app](../mlx90614-webhid/README.md) remains available.

The demo prints temperatures once per second and saves every attempted object/ambient pair to CSV. It uses absolute monotonic deadlines, skips elapsed polling slots instead of issuing catch-up bursts, and reports successful throughput, latency and timing variation. **10 or 20 Hz is a requested polling rate, not a guaranteed sensor refresh rate or precise real-time timing.**

## Run on Windows

Prerequisites: the existing sensor wiring, **x64 CPython 3.10+** with development headers/import library (3.11 tested), and internet access for the first setup. No firmware flash or Microsoft C++ installation is needed: a portable C compiler installs inside this demo's virtual environment. The compiler package download is approximately 94 MB. No virtual-environment activation is required.

1. Open this repository in **VS Code → File → Open Folder**, then **Terminal → New Terminal**. Select **PowerShell**. All commands below start in the repository root and can run in this same terminal.
2. First run a **hardware-free, simulated test**:

   ```powershell
   powershell -NoProfile -ExecutionPolicy Bypass -File .\08_Software\mlx90614-hidapi-demo\Run-Demo.ps1 -Simulate -Hz 20 -Seconds 5
   ```

   The launcher creates an isolated `.venv`, installs pinned dependencies and builds the native extension on first use. Expect `Native extension import: PASS`, clearly labelled `SIMULATED` output, a timing summary, and a new file under `08_Software/mlx90614-hidapi-demo/output/`. Stop on installation, compilation or import errors. Artificial readings do not prove hardware throughput.
3. Enumerate the bridge without opening it:

   ```powershell
   powershell -NoProfile -ExecutionPolicy Bypass -File .\08_Software\mlx90614-hidapi-demo\Run-Demo.ps1 -List
   ```

   Expect `[0] MCP2221 USB-I2C/UART Combo VID=04D8 PID=00DD`. If none appears, connect the bridge and repeat. With multiple matches, supply the chosen index using `-DeviceIndex 0` in the following commands. The list omits serial numbers and device paths.
4. In the browser app, click **Disconnect**, then close sensor tabs. Stop other Python readers. Only one application may control the bridge during this test. Start with a **2 Hz hardware run**:

   ```powershell
   powershell -NoProfile -ExecutionPolicy Bypass -File .\08_Software\mlx90614-hidapi-demo\Run-Demo.ps1 -Hz 2 -Seconds 10
   ```

   Expect `HARDWARE: 100 kHz confirmed`, increasing valid-pair counts and temperatures in Celsius. A clean ten-second run should attempt 20 pairs. Inspect the final summary for failures and missed slots; retain the CSV if either occurs. Stop and use the recovery steps below if startup fails or no valid pairs arrive.
5. After the 2 Hz run succeeds, compare **10 Hz** with **experimental 20 Hz**, sequentially with identical wiring:

   ```powershell
   powershell -NoProfile -ExecutionPolicy Bypass -File .\08_Software\mlx90614-hidapi-demo\Run-Demo.ps1 -Hz 10 -Seconds 30
   powershell -NoProfile -ExecutionPolicy Bypass -File .\08_Software\mlx90614-hidapi-demo\Run-Demo.ps1 -Hz 20 -Seconds 30
   ```

   Compare successful pairs per second, failed pairs, missed slots and interval percentiles. The requested counts are 300 and 600; they are targets. More polls do not establish more independent sensor conversions. An unchanged raw word can also mean temperature stayed constant.

Press **Ctrl+C** to stop a run. Completed rows and a summary are retained; the HID handle closes before exit. A pair stopped during acquisition has CSV status `interrupted` and increments `interrupted_pairs`, separately from read failures. An interruption between pairs sets `interrupted` without adding an attempted pair. Exit code `0` means no failed pairs, `1` means a read/setup failure occurred, `2` means invalid arguments or incomplete setup, and `130` means interrupted. Missed slots remain visible even if every attempted read succeeded.

## Read the results

Each run creates a new CSV and a matching `.summary.json`. Existing files are never overwritten. These measurements and compiled products are ignored by Git.

| Field | Meaning |
| --- | --- |
| `successful_pairs_per_second` | Valid complete object/ambient pairs divided by actual run duration, including the full requested window on a normal finish |
| `attempts` | Every initiated pair; equals `valid_pairs + failed_pairs + interrupted_pairs`; no hidden temperature-read retry |
| `failed_pairs` | Pairs rejected because of a read error; remains counted if Ctrl+C interrupts subsequent error recovery |
| `interrupted_pairs` | Pairs stopped by Ctrl+C during acquisition, without a completed read-error result |
| `missed_slots` | Polling deadlines skipped when acquisition/recovery/output takes too long; these are separate from attempted reads that failed |
| `start_lateness_ms` | Host acquisition start minus its scheduled deadline; p50/p95/p99/max quantify scheduling variation |
| `acquisition_ms` | Host time spent acquiring the pair, excluding subsequent error recovery and terminal output |
| `successful_interval_ms` | Time between completion of successive valid pairs, including gaps caused by failures |
| `object_raw`, `ambient_raw` | Validated sensor words; both are blank when the pair is rejected |
| `repeated_raw_pairs` | Consecutive valid pairs with identical words; this alone cannot distinguish steady temperature from rereading sensor data |
| `error_code`, `error`, `recovery_error` | Each failure and any failed cancellation, retained in CSV and printed to the terminal |

Timing percentiles cover the latest **10,000 attempts/intervals**; counts and CSV cover the entire run. Timestamps use the host monotonic clock. Ambient and object registers are read sequentially; these are not simultaneous acquisition times or sensor conversion timestamps. CSV writes and once-per-second display updates share the acquisition thread and can contribute to missed slots.

## What differs from WebHID

| Change | Purpose and limit |
| --- | --- |
| Native Cython transport + HIDAPI | Avoid browser lifecycle/timer restrictions; desktop OS and USB delays still apply |
| Absolute deadlines | Avoid accumulated drift from sleeping a full interval after each read; overdue slots are counted and skipped |
| Direct `0x40` data retrieval after repeated-start | Shorter acquisition path: **six** HID exchanges per valid pair in the recorded hardware runs, versus at least eight in the current browser code path; pending/partial data adds exchanges. A matched browser timing comparison is still needed. |
| No fixed pause between registers | Reduce host-added delay; no promise of faster fresh sensor data |
| One attempt per scheduled pair | Expose errors and latency rather than hiding them behind retries; nonfatal failure triggers one I2C cancellation before the next slot |
| Stop on a missing/malformed HID reply | Avoid allowing a late matching-command reply to contaminate later readings |

The bus stays at **100 kHz**, using divider `118` and verifying it. No `0x70` USB reset, sensor EEPROM change, GPIO change or UART configuration is issued. SMBus PEC and the sensor's error bit are checked before accepting a pair. The [MLX90614 specification](https://www.melexis.com/-/media/files/documents/datasheets/mlx90614-datasheet-melexis.pdf) limits the bus to 100 kHz; filtering determines refresh/settling. Cython does not change those limits. HID read waits use the per-register budget, but OS-level writes/scheduling do not provide a hard real-time deadline.

## Reuse, diagnostics and recovery

1. Reuse the launcher commands above for later runs. Dependencies are reused unless `requirements.txt` changes. The extension rebuilds only when its source/build script changes or the compiled file is missing. No flash, repeated Python install or activation is needed.
2. For a startup failure, keep the printed error. For a short protocol trace, with other readers still stopped, run:

   ```powershell
   powershell -NoProfile -ExecutionPolicy Bypass -File .\08_Software\mlx90614-hidapi-demo\Run-Demo.ps1 -Hz 2 -Seconds 5 -Trace
   ```

   Expect hexadecimal `TX`/`RX` command evidence. Tracing changes timing; use ordinary runs for rate comparisons. A rejected speed setting prints status bytes and stops instead of silently using a different bus speed.
3. If a HID timeout occurs, the demo stops and closes its handle. Retry the ordinary 2 Hz command after checking other clients are stopped. If the bridge still fails, unplug/replug **only this bridge**, then repeat 2 Hz. Replugging also interrupts its UART users. The demo never resets USB automatically.
4. To return to the browser, finish the demo or press Ctrl+C, then open the [browser app](https://robomaniac.github.io/mlx90614-mcp2221a/) and click **Connect**. Use the same requested rate and duration when comparing results.

## Test and manual build

From **PowerShell at the repository root**, after first setup:

```powershell
& .\08_Software\mlx90614-hidapi-demo\.venv\Scripts\python.exe -m unittest discover -s .\08_Software\mlx90614-hidapi-demo -p test_demo.py -v
```

Expect all 19 tests `OK`. Fake HID reports and a fake clock test PEC rejection, complete-pair accounting, packet layout, reset prevention, missed slots, retained failures and interruption during acquisition/recovery. These tests do not contact the sensor.

For manual setup/build, in the same PowerShell window starting at the repository root:

```powershell
Set-Location .\08_Software\mlx90614-hidapi-demo
python -m venv .venv
& .\.venv\Scripts\python.exe -m pip install --only-binary=:all: -r requirements.txt
& .\.venv\Scripts\python.exe build_native.py
& .\.venv\Scripts\python.exe demo.py --simulate --hz 20 --seconds 5
Set-Location ..\..
```

Run each command separately and stop on an error. The build generates a local Windows `.pyd`; it is specific to the Python version and architecture. Changing Python requires rebuilding the virtual environment. The build helper also has Linux/macOS compiler paths, which are not validated here; this guide targets Windows x64.

## Optional cleanup

Close the demo first. From **PowerShell at the repository root**, delete only generated build/environment files with this checked-path command; source and recorded measurements remain:

```powershell
$demoFolder = (Resolve-Path -LiteralPath .\08_Software\mlx90614-hidapi-demo).Path
foreach ($demoGenerated in @('.venv', '.native-build', '__pycache__')) {
    $demoTarget = [IO.Path]::GetFullPath((Join-Path $demoFolder $demoGenerated))
    if (-not $demoTarget.StartsWith($demoFolder + [IO.Path]::DirectorySeparatorChar)) { throw 'Unexpected cleanup path' }
    if (Test-Path -LiteralPath $demoTarget) { Remove-Item -LiteralPath $demoTarget -Recurse -Force }
}
Get-ChildItem -LiteralPath $demoFolder -Filter 'mcp2221_native*.pyd' -File | Remove-Item -Force
```

The next launcher invocation performs setup/build again because those generated files were removed. Delete measurement files through **VS Code Explorer → `08_Software/mlx90614-hidapi-demo/output`** only when you no longer need them.

## Validation

Native Windows x64 build/import, 19 fake-device protocol/scheduler tests, a simulated timing run and real sensor runs passed. On 2026-10-10, completed hardware trials returned **20/20 pairs at 2 Hz**, **300/300 at 10 Hz**, and **600/600 at 20 Hz**, with zero read errors or missed slots at 100 kHz. The 20 Hz trial lasted 30 seconds; acquisition p95 was **12.27 ms** and start lateness p95 **0.73 ms**. See the [hardware results, startup evidence and limits](../../05_Data/NATIVE_HARDWARE_TESTS.md).

These short trials demonstrate complete validated reads on the tested setup. Long-run reliability, independent sensor-conversion rate, temperature accuracy and a matched WebHID comparison remain untested. This Python/Cython demo runs locally and cannot execute on GitHub Pages. The interruption-counter correction changes Python reporting only; the existing environment and native extension can be reused.
