# Run and test the single-file app

The active file is **`mlx.html` in this directory**. CSS and JavaScript are embedded. Python serves static files for local development; the browser communicates directly with the USB bridge. There is no compilation, firmware flash, npm installation or backend service.

## Prerequisites and voltage check

Use desktop Chrome or Edge with WebHID, a USB data cable, an MCP2221A bridge and a correctly wired MLX90614. See the [detailed BOM](../../README.md#detailed-bill-of-materials). The supplied `BAA7160B20` marking identifies a 3 V chip. Its breakout's VIN/regulator and pin labels are unknown; establish these before connecting power. On a confirmed compatible circuit, use a 3.3 V supply and 3.3 V I2C pull-ups with common ground, SDA and SCL. Do not guess a bare sensor's pinout.

Local serving requires Python 3. Checks require Node.js or installed desktop Visual Studio Code; the wrapper reuses VS Code's bundled JavaScript runtime if Node is absent. Neither Python nor Node is required by the deployed browser app.

## Local setup and operation

1. Open **Visual Studio Code > File > Open Folder** and select the repository root (the folder containing the main `README.md` and `08_Software`). Open **Terminal > New Terminal** and select **PowerShell**. The new terminal starts in that folder. Confirm the location and prerequisites:

   ```powershell
   Get-Location
   Test-Path .\08_Software\mlx90614-webhid\mlx.html
   python --version
   ```

   The path must be the repository root, `Test-Path` must return `True`, and Python must report version 3. Stop if the path is wrong. If Python is unavailable, use the optional direct-file method below or install Python 3 with PATH enabled and reopen the terminal.

2. In the **same terminal**, check source syntax and simulated diagnostic behavior:

   ```powershell
   powershell -NoProfile -ExecutionPolicy Bypass -File .\08_Software\mlx90614-webhid\tools\Check-Html.ps1 -Diagnostics
   ```

   Expect `PASS` for active HTML and baseline syntax, then six diagnostic checks. Stop on any error. These tests use simulated failures and do not open USB hardware. On macOS/Linux or with Node already installed, run from the repository root:

   ```sh
   node 08_Software/mlx90614-webhid/tools/check_html.mjs
   node 08_Software/mlx90614-webhid/tools/test_diagnostics.mjs
   ```

3. In the **same PowerShell terminal**, start a loopback server:

   ```powershell
   python -m http.server 8000 --bind 127.0.0.1 --directory .\08_Software\mlx90614-webhid
   ```

   Expect `Serving HTTP` on port 8000. Leave this terminal running. If the port is occupied, reuse an existing server only when you know it serves this directory; otherwise stop that server and rerun the command. Do not terminate an unidentified process.

4. Open **Chrome or Edge** at `http://127.0.0.1:8000/mlx.html`. The dark monitor and five rate options should appear. The debug log should report a secure context and WebHID availability. If WebHID is unavailable, switch to desktop Chrome/Edge and check browser policy. On public hosting use HTTPS; on local hosting use the loopback URL above.

5. Close other tabs, Python bridge apps and serial/HID tools using this bridge. Connect the USB data cable. Select **2 Hz** in the rate dropdown, then click **Connect**. The app tries previously permitted devices using `navigator.hid.getDevices()`; otherwise select the MCP2221A in Chrome's chooser and approve device access. Canceling the chooser leaves the app disconnected.

6. A pass includes an I2C speed confirmation for **100000 Hz**, valid object and ambient readings in °C, and growing chart points. The debug log reports startup and successful reads. The points pill shows successful pairs separately from attempted pairs; a failed partial pair must not become a plotted point. Hover over the chart to inspect samples. Requested 10 Hz is a target, not a guaranteed successful rate.

7. If a read fails, retain the debug log. An example failed-attempt entry is `Ambient register 0x06 read failed (attempt 1/2): ...`; the real message explains the failure. A transient failure displays **Retrying** while waiting for a valid pair. A startup error such as `I2C speed set failed ... 0x21` is a failure, even if SCL/SDA were high at one instant. Do not call the connection recovered until readings resume.

8. Click **Disconnect** before closing the tab. Return to the server terminal and press **Ctrl+C**; the PowerShell prompt returning confirms the server stopped. Unplug the bridge only after its clients are closed if needed. The app keeps data in memory; reloading clears the displayed chart/log.

Optional direct-file method: in **File Explorer**, locate `08_Software\mlx90614-webhid\mlx.html`, right-click **Open with > Google Chrome** or **Microsoft Edge**, then follow steps 5–8. If device access is blocked under `file://`, use the loopback server above. The loopback method is the documented reference.

Optional VS Code tasks: choose **Terminal > Run Task > Check HTML and simulated diagnostics**, or **Serve MLX90614 app on localhost:8000**. Stop the server with Ctrl+C in its dedicated task terminal. The server task requires Python on PATH.

## Reuse, editing and restart

1. Keep an existing server running if it serves the correct directory. Edit and save `mlx.html`; no build or firmware flash is needed.
2. Click **Disconnect**, then reload the browser with **Ctrl+R**, and click **Connect** again. Reloading is necessary to execute the saved JavaScript; restarting the static server is unnecessary for HTML edits.
3. If the server was stopped, open PowerShell at the repository root and repeat local setup step 3. If hardware is busy, close every client before retrying.
4. Automatic MCP2221A USB soft reset is disabled. If the log says recovery requires USB reset, click **Disconnect**, close all bridge clients, manually unplug/replug **only this bridge**, reload the page and click **Connect**. This disconnects any other HID/UART client sharing the bridge; coordinate before unplugging. No `0x70` reset command is sent by the active app.

## Compare with the unchanged baseline

Revision 03 is a comparison candidate preceding the user's high-rate logs. Revision 07 exactly matched the user's hosted HTML when fetched before migration; neither establishes the edited revision's hardware reliability. Run only one connected client at a time.

1. Keep the loopback server from local setup running. Open a **second VS Code PowerShell terminal** at the repository root and copy the immutable baseline to an ignored experiment folder:

   ```powershell
   if (-not (Test-Path -LiteralPath .\99_Archive\webhid-history\03-dropdown-last-reading-baseline.html)) { throw 'Open a terminal at the repository root before continuing.' }
   New-Item -ItemType Directory -Force -Path .\08_Software\mlx90614-webhid\.local-test | Out-Null
   Copy-Item -LiteralPath .\99_Archive\webhid-history\03-dropdown-last-reading-baseline.html -Destination .\08_Software\mlx90614-webhid\.local-test\baseline.html
   Get-FileHash -Algorithm SHA256 -LiteralPath .\08_Software\mlx90614-webhid\.local-test\baseline.html
   ```

   Expect SHA-256 `463e33449d486cde680637a82cac7b535fd9ccadccbbca20f82e700ad1e1728e` (case is immaterial). Stop if it differs. Never edit the historical source in place.

2. Disconnect and close the active tab. Open `http://127.0.0.1:8000/.local-test/baseline.html`, choose **2 Hz**, connect and retain two minutes of readings and error evidence. Disconnect and close it. Open `http://127.0.0.1:8000/mlx.html` and repeat with the same wiring and rate. This is an A/B test, not a replacement of the active source.

3. Optional original-source inspection: in the second terminal, copy revision 07:

   ```powershell
   Copy-Item -LiteralPath .\99_Archive\webhid-history\07-latest-soft-reset-recovery.html -Destination .\08_Software\mlx90614-webhid\.local-test\original.html
   Get-FileHash -Algorithm SHA256 -LiteralPath .\08_Software\mlx90614-webhid\.local-test\original.html
   ```

   The expected original source hash is `2b252a1eb651d16f144040758d6844ecb7548aabc9196ea3ce6319c24d6c2787`. Inspect the copied source in VS Code. Revision 07 can automatically reset USB during recovery: obtain explicit approval for that behavior before clicking Connect in the old app. The current revision prevents it.

4. Cleanup after closing comparison tabs: in the second terminal, remove only these experiment files if present:

   ```powershell
   Remove-Item -LiteralPath .\08_Software\mlx90614-webhid\.local-test\baseline.html -ErrorAction SilentlyContinue
   Remove-Item -LiteralPath .\08_Software\mlx90614-webhid\.local-test\original.html -ErrorAction SilentlyContinue
   ```

   The original history and full handoff backup remain intact.

## Hardware validation still required

1. Follow local setup at **2 Hz** for two minutes; record successful pairs, attempted pairs, read errors, elapsed time and any timeout. Save only a reviewed, sanitized log into `05_Data/` if you intend to publish it.
2. Disconnect/reconnect ten times with one tab and unchanged wiring. Record startup failures and the exact outgoing/response evidence provided by the debug panel. One successful reconnect does not establish recovery reliability.
3. Run each of **1, 2, 5 and 10 Hz** for five minutes with the same wiring. Record successful pair rate as successful pairs / elapsed seconds, missed/failed pairs and time to first timeout. A recovered register retry still counts as read-error evidence.
4. Compare revision 03 and the active revision using the procedure above when a regression appears. Update the [known issues/test plan](../../00_Documentations/KNOWN_ISSUES_AND_TEST_PLAN.md) with observations separately from hypotheses. See [validation](../../05_Data/VALIDATION.md) for checks actually completed.
