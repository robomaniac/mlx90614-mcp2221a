# MLX90614 temperature monitor via MCP2221A

A single-file desktop Chrome/Edge app that reads object and ambient temperature from a Melexis MLX90614 through a Microchip MCP2221A USB/I2C bridge. WebHID is the browser interface; **MCP2221A** is the bridge part number. The public repository name is `mlx90614-mcp2221a` because it identifies both pieces of hardware.

The dark interface includes Celsius readings, a live chart with mouse hover, 1/2/4/5/10 Hz requests, a custom rate dropdown, and bounded diagnostic logs. No browser runtime dependencies, CDN, backend, npm install, or build step are required.

- [Open the live GitHub Pages app](https://robomaniac.github.io/mlx90614-mcp2221a/) — deployed HTML verified identical to the active file; checks recorded in [validation](05_Data/VALIDATION.md).
- [Complete local setup, operation, recovery and testing](08_Software/mlx90614-webhid/README.md).
- [GitHub publication and Pages maintenance](00_Documentations/GITHUB_PAGES.md).
- [Review findings](00_Documentations/PROJECT_REVIEW.md), [protocol notes](00_Documentations/HARDWARE_AND_PROTOCOL.md), [test plan](00_Documentations/KNOWN_ISSUES_AND_TEST_PLAN.md).

## Current status

The user reports the existing [hosted app](https://jeromedemers.com/mlx.html) works. Its fetched HTML exactly matched historical revision 07 before this migration. The active revision preserves the interface and protocol but disables automatic USB reset, retains failed-read evidence, and distinguishes successful object/ambient pairs from attempted pairs. The edited revision requires hardware validation; static and simulated tests cannot establish sensor operation or a sustained 10 Hz success rate. See [selected historical logs](05_Data/SELECTED_LOGS.md).

## Quick local start

Prerequisites: desktop Chrome or Edge, Python 3 for the local server, and Node.js **or installed desktop VS Code** for the checks. The Python server only serves the HTML; it does not communicate with the sensor.

1. In **VS Code > File > Open Folder**, open this repository. Choose **Terminal > New Terminal**, using **PowerShell**. For the current local checkout, enter:

   ```powershell
   Set-Location -LiteralPath 'C:\Nextcloud\01_Projects\2026-013_MLX90614-WebHID'
   powershell -NoProfile -ExecutionPolicy Bypass -File .\08_Software\mlx90614-webhid\tools\Check-Html.ps1 -Diagnostics
   ```

   All checks should print `PASS`. Stop and correct any failure before connecting hardware. In a different checkout, change the first path to that checkout.

2. In the **same PowerShell terminal**, start the server:

   ```powershell
   python -m http.server 8000 --bind 127.0.0.1 --directory .\08_Software\mlx90614-webhid
   ```

   Leave this terminal running. If Python is missing, install Python 3 or use the optional direct-file method in the [app guide](08_Software/mlx90614-webhid/README.md). If the port is occupied, reuse only a server you know serves this app, or stop that server before retrying.

3. Open **Chrome or Edge** at `http://127.0.0.1:8000/mlx.html`. Close other clients using the bridge, select **2 Hz**, then click **Connect** and select MCP2221A if prompted. Expect changing object/ambient readings and chart points. Inspect the debug log for errors; successful connection alone does not prove readings.

4. Click **Disconnect** before closing the tab. Return to the server terminal and press **Ctrl+C** to stop it. Reuse an existing correct server for subsequent tests; there is no build or flash step. After saving HTML changes, disconnect and reload the browser before reconnecting.

On GitHub Pages, open the app link directly in Chrome/Edge and follow step 3. GitHub serves the HTML over HTTPS; the sensor remains connected to your own computer. GitHub's repository file preview does not run the app.

## Detailed bill of materials

| Qty | Component | Manufacturer / part | Relevant specifications |
| --- | --- | --- | --- |
| 1 | Infrared temperature sensor | **Melexis MLX90614BAA**; supplied marking `BAA7160B20` | TO-39 package; single zone; **90° FOV**; **2.6–3.6 V VDD**; SMBus address **`0x5A`**; **0.02 °C digital resolution** |
| 1 | USB-to-I2C bridge board | **Microchip MCP2221A**; reference breakout: [**Adafruit #4471**](https://www.adafruit.com/product/4471) | I2C commands over HID; project bus **100 kHz**. Reference board includes a **3.3 V regulator** and **5.1 kΩ SDA/SCL pull-ups**, with logic set to 3.3 V by default. |

`BAA` identifies the sensor variant; `7160B20` is the lot marking. The exact sensor breakout model and full ordering code are not established. Adafruit #4471 is the reference bridge board from the project history; the physical board model has not been confirmed. Sensor specifications and marking are documented in the [Melexis datasheet](https://www.melexis.com/-/media/files/documents/datasheets/mlx90614-datasheet-melexis.pdf).

### Wiring

For the Adafruit #4471 reference board with **3.3 V logic**:

| Bridge board pin | Sensor signal | Bare MLX90614 TO-39 pin |
| --- | --- | --- |
| **3V** (regulated 3.3 V) | VDD | **3** |
| **GND** | VSS / ground | **4** |
| **SDA** | SDA / PWM | **2** |
| **SCL** | SCL / Vz | **1** |

The reference board's pull-ups are already fitted. Keep its logic jumper at **3.3 V**; the BAA sensor uses the 3 V supply variant. TO-39 pin numbers refer to the manufacturer's package drawing, not a breakout's header order. For a sensor module, confirm its supply input and header labels before using this mapping. See the [bridge pinout](https://learn.adafruit.com/circuitpython-libraries-on-any-computer-with-mcp2221/pinout) and [sensor pin description, page 6](https://www.melexis.com/-/media/files/documents/datasheets/mlx90614-datasheet-melexis.pdf#page=6).

## Folder map

| Path | Contents |
| --- | --- |
| `00_Documentations/` | Review, protocol, history, issue/test plan and publication guide |
| `04_Media/` | Cropped sample-rate control reference image |
| `05_Data/` | Selected diagnostic logs, validation record and current SHA-256 manifest |
| `08_Software/mlx90614-webhid/` | Active `mlx.html`, operating guide and development checks |
| `99_Archive/webhid-history/` | Seven unchanged historical HTML snapshots, public provenance |
| `99_Archive/original-handoff/` | Full verified original backup, local only and ignored |
| `99_Archive/original-releases/` | Original ZIPs, local only and ignored |
| `99_Archive/python-webapp/`, `99_Archive/early-webhid-prototype/` | Older alternatives, local only and ignored; not app dependencies |
| `.github/workflows/pages.yml` | Checks source and deploys only the active HTML as site `index.html` |
| `.vscode/tasks.json` | VS Code check and local-server tasks |

The numbered folders follow the user's existing Nextcloud convention. Unused categories are omitted. `.local/` is reserved for ignored helper binaries and temporary validation artifacts.

## Provenance, privacy and license

Historical snapshots are immutable. The complete original handoff remains local; public Git includes only the curated app, guides, selected logs, cropped reference image and seven HTML snapshots. [Validation](05_Data/VALIDATION.md) records the publication review and its limits. Do not add credentials, private paths or confidential logs; review staged files before every push. The app uses browser-granted USB access and includes no analytics or network upload code.

Released under [MIT](LICENSE). Manufacturer documentation and product names remain their owners' materials. The original source checksum and evidence are recorded in the [project review](00_Documentations/PROJECT_REVIEW.md).
