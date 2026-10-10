# MLX90614 temperature monitor via MCP2221A

A single-file desktop Chrome/Edge app that reads object and ambient temperature from a Melexis MLX90614 through a Microchip MCP2221A USB/I2C bridge. WebHID is the browser interface; **MCP2221A** is the bridge part number. The public repository name is `mlx90614-mcp2221a` because it identifies both pieces of hardware.

The dark interface includes Celsius readings, a live chart with mouse hover, 1/2/4/5/10 Hz requests, a custom rate dropdown, and bounded diagnostic logs. No browser runtime dependencies, CDN, backend, npm install, or build step are required.

- [Open the GitHub Pages app](https://robomaniac.github.io/mlx90614-mcp2221a/) — deployment status is recorded in [validation](05_Data/VALIDATION.md).
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

Quantities are for one sensor and one computer. A compatible substitute may work; confirm its voltage and pull-ups first. No purchase prices are assumed.

| Qty | Item / identification | Purpose and confirmed details | What remains to confirm |
| --- | --- | --- | --- |
| 1 | Melexis **MLX90614BAA**, marking supplied: `BAA7160B20` | Infrared thermometer; B = nominal 3 V supply, A = single zone, A = nominal 90° field of view. Chip operating VDD is **2.6–3.6 V**; factory SMBus address is normally `0x5A`. `7160B20` is traceability marking, not a breakout model. | Breakout supplier/model, regulator, module VIN tolerance and fitted pull-ups are unknown. Do not infer a module's 5 V compatibility from this marking. |
| 1 | Microchip **MCP2221A** USB/I2C bridge; project reference: **Adafruit #4471** | Carries I2C over HID. Adafruit #4471 has USB-C, a 3.3 V regulator and default 3.3 V I2C pull-ups of about 5.1 kΩ. Project device reports VID/PID `04D8:00DD`. | Physical board identity and jumper settings have not been independently inspected. Check silkscreen before relying on this reference board's pinout. |
| 1 | USB **data** cable, computer connector to bridge connector | Powers/enumerates the bridge; a charge-only cable will not carry HID. USB-C is the connector on the reference #4471 board. | Actual bridge connector and computer port. |
| 4 | Jumper connections: supply, ground, SDA, SCL | Connect a compatible **3.3 V supply** to confirmed sensor VDD, common GND, SDA to SDA and SCL to SCL. Keep wiring short. | Actual module pin labels and VIN versus VDD distinction. Follow the module's documentation; stop if unknown. |
| 0–1 | Breadboard / suitable connector | Optional mechanical connection for a breakout or correctly identified bare sensor pins. | Package pinout and assembly method. |
| 0–2 | I2C pull-up resistors | Conditional: needed only if compatible pull-ups are absent or inadequate. The reference #4471 already provides pull-ups. | Existing parallel pull-ups and bus voltage; do not add resistors blindly. |
| 0–1 | Local supply bypass capacitor | Conditional for a bare sensor: follow Melexis's application circuit. A breakout may already include it. | Actual board schematic and fitted capacitor; no value is assumed here. |
| 1 | Desktop computer, Chrome/Edge, USB port | Local WebHID host. No flashed firmware or serial terminal is required for this app. | Browser WebHID support and OS device permissions. |

Sources: [Melexis MLX90614 datasheet](https://www.melexis.com/-/media/files/documents/datasheets/mlx90614-datasheet-melexis.pdf), [Adafruit #4471](https://www.adafruit.com/product/4471), [reference board pinout and pull-ups](https://learn.adafruit.com/circuitpython-libraries-on-any-computer-with-mcp2221/pinout). The sensor marking identifies the chip variant, but does not establish the breakout's wiring or supply tolerance. This is a personal experiment, not an accuracy or medical validation.

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
