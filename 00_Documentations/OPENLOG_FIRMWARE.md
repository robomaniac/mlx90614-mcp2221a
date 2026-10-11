# Qwiic OpenLog firmware update and SD verification

The **SparkFun Qwiic OpenLog DEV-15164** initially reported firmware **2.0**. A physical test stored only `ki` from a 14-byte CSV header and rejected the sync command. SparkFun's 3.1 source corrects the write length and provides sync; the Temperature Logger rejects older firmware before creating a recording file.

**Current result: local 3.101 is flashed, confirmed over I2C and verified with a native SD recording.** It keeps SPI powered during sleep; only that behavior and the version tag differ from pinned official 3.1. Flash verification passed for **21,688 bytes**. New **61-byte** and **91-byte** CSVs read back exactly, including one-second idle gaps. A short native thermocouple trial produced **19 valid reads / zero read errors / 9 saved rows**; all **1,263 SD bytes matched the PC CSV**. MCP9600 is at **0x60**, OpenLog at **0x2A**. The native service is available at **http://127.0.0.1:8768/** with the reader disconnected. Reuse it through [the logger instructions](../08_Software/temperature-logger/README.md#use-the-existing-native-environment); no rebuild/reflash/rewiring is needed for normal use. Standalone WebHID SD and long-duration/cold-start reliability remain unverified.

**Retained earlier result:** original 2.0 truncated writes; official 3.1 was backed up/flashed/verified through **COM21**, but its CSV write and SparkFun write/sync comparison timed out. The separate SPI change supports the sleep/peripheral hypothesis, without instrumentation proving the failing callback's state. Both official 3.1 and the original full-flash backup are preserved. See [actual before/after evidence](../05_Data/TEMPERATURE_LOGGER_TESTS.md#verified-3101-hardware-recording). The programming steps below document the completed process and optional reproduction/rollback; normal recording does not require repeating them.

## Wiring and prerequisites

1. Disconnect every WebHID/native reader using **Disconnect** in its dashboard. The local servers may remain open while disconnected. Close Arduino Serial Monitor and any other program using the FTDI port. Programming resets **OpenLog**, so it must not be receiving SD writes.
2. Use a **3.3 V TTL FTDI adapter**, with firm contacts. Match signal labels, not wire colors. The FTDI programs the OpenLog ATmega328P; the MCP2221A's separate UART port does not program this board. Use one suitable 3.3 V supply and common ground; avoid joining two competing regulator outputs.

   | FTDI signal | OpenLog signal |
   | --- | --- |
   | TX / TXD | RXI |
   | RX / RXD | TXO |
   | GND | GND |
   | DTR | DTR / GRN |
   | 3.3 V, if this adapter supplies the board | 3.3 V |

   OpenLog's DTR capacitor supplies the programming reset pulse. A pin crossover board can swap RX/TX for a wiring test; an electrical logic inverter or RS-232-level adapter is different hardware and should not be substituted. If a retry still reports `not in sync`, stop and inspect reset/serial wiring rather than repeatedly flashing.
3. Open **VS Code → this repository → Terminal → New Terminal → PowerShell**. Keep the commands below in this same terminal at the repository root. The existing **Arduino IDE 2 / AVR core 1.8.8** installation and native Python environment can be reused. The correct target is **Arduino Uno / ATmega328P, 16 MHz, Optiboot**, as documented in the [SparkFun Qwiic OpenLog guide](https://learn.sparkfun.com/tutorials/qwiic-openlog-hookup-guide/all?print=1).

## Reuse the prepared official build for comparison or rollback

The official **3.1** image is `.local/openlog-update/build/Qwiic_OpenLog.ino.hex`. It occupies **21,698 bytes flash**, **1,368 bytes SRAM**, leaving **680 bytes SRAM**. Its SHA-256 is `61479e702b30a5718ecf46b0f3579c2f25032aaadd12883ab0a23ffe5900c2ac`. Its SD test failed on this setup; the currently verified native setup uses **3.101** from [the separate SPI section](#separate-spi-experiment). Use the official-image commands only for an intentional comparison or rollback. Firmware source and build products stay local and ignored.

1. Define and check the tools/image in the repository-root **PowerShell** terminal:

   ```powershell
   $ErrorActionPreference = 'Stop'
   $projectRoot = (Get-Location).Path
   $avrdudeRoot = Join-Path $env:LOCALAPPDATA 'Arduino15\packages\arduino\tools\avrdude\8.0.0-arduino1'
   $avrdudePath = Join-Path $avrdudeRoot 'bin\avrdude.exe'
   $avrdudeConfig = Join-Path $avrdudeRoot 'etc\avrdude.conf'
   $hexPath = Join-Path $projectRoot '.local\openlog-update\build\Qwiic_OpenLog.ino.hex'
   $ftdiPort = 'COM21'
   foreach ($requiredPath in @($avrdudePath, $avrdudeConfig, $hexPath)) {
       if (-not (Test-Path -LiteralPath $requiredPath)) { throw "Missing: $requiredPath. Stop; use the build section below." }
   }
   $ftdiDevice = @(Get-PnpDevice -Class Ports -PresentOnly | Where-Object {
       $_.FriendlyName -eq "USB Serial Port ($ftdiPort)" -and $_.InstanceId -match 'FTDIBUS.*VID_0403\+PID_6001'
   })
   if ($ftdiDevice.Count -ne 1) { throw 'Expected FTDI port not found. Check Device Manager; do not select the MCP2221A UART.' }
   (Get-FileHash -LiteralPath $hexPath -Algorithm SHA256).Hash
   ```

   Expect the FTDI check to pass and the prepared image hash above. A Windows reconnection can change COM numbering: check **Device Manager → Ports (COM & LPT) → USB Serial Port**, and change `$ftdiPort` before continuing. Stop on missing tools, ambiguous hardware or an unexpected prepared-image hash.
2. Read the existing flash into a unique backup. This also tests serial wiring and the bootloader without writing firmware:

   ```powershell
   $backupPath = Join-Path $projectRoot ('.local\openlog-update\before-' + (Get-Date -Format 'yyyyMMdd-HHmmss') + '.hex')
   if (Test-Path -LiteralPath $backupPath) { throw 'Backup already exists; wait one second and repeat this step.' }
   $ErrorActionPreference = 'Continue'
   & $avrdudePath -C $avrdudeConfig -p atmega328p -c arduino -P $ftdiPort -b 115200 -D -n -x attempts=2 -U "flash:r:${backupPath}:i"
   $probeExit = $LASTEXITCODE
   $ErrorActionPreference = 'Stop'
   if ($probeExit -ne 0) { throw 'No verified bootloader connection. Stop here; do not run the flash command.' }
   if (-not (Test-Path -LiteralPath $backupPath) -or (Get-Item -LiteralPath $backupPath).Length -eq 0) { throw 'Backup missing/empty; stop.' }
   ```

   Success includes device signature **`0x1e950f`**, flash read and exit code 0. `resp=0x00` is no valid bootloader reply; it does not alone prove whether RX/TX or DTR is responsible. The OpenLog reset is expected during the handshake. MCP2221A USB reset is not used.
3. **Only after step 2 succeeds**, write and verify the prepared application:

   ```powershell
   $ErrorActionPreference = 'Continue'
   & $avrdudePath -C $avrdudeConfig -p atmega328p -c arduino -P $ftdiPort -b 115200 -D -x attempts=2 -U "flash:w:${hexPath}:i"
   $flashExit = $LASTEXITCODE
   $ErrorActionPreference = 'Stop'
   if ($flashExit -ne 0) { throw 'Flash/verification failed. Stop and retain the output; do not start recording.' }
   ```

   Expect **flash verified** and exit code 0. Normal signature and verification checks remain enabled. This application HEX does not include the bootloader; there are no EEPROM, fuse or erase commands. On normal startup, OpenLog firmware may create its usual numbered log and update its log-number setting. This procedure does not format or deliberately delete card files.

**Completed backup:** `.local/openlog-update/before-new-ftdi-COM21.hex`, all **32,768 flash bytes**, SHA-256 `0a93c04feef4d813bf78ffbff05e1d1532cc0b396b74af1f2d66b52d97e6017d`. The backup includes the original bootloader area and stays local/ignored. Do not write that complete image through the serial bootloader as a routine application update. The official build and backup are preserved for comparison/rollback. Repeating the official flash cannot by itself resolve the subsequently observed SD failure.

The first COM21 flash command failed during bootloader initialization (`cannot obtain SW version`, unexpected sync byte `0x00`), before programming was reported. A subsequent read-only signature/parameter exchange passed. The successful flash retry retained a verbose trace and ended with **`21698 bytes of flash verified`**, exit 0. The intermittent initialization cause remains unproven. AVRDUDE's generic `-B`/`-F` suggestions were not used; normal part-signature checks remained enabled.

## If no bootloader reply: test FTDI loopback

This section retains the **original COM20 adapter** diagnosis. It was replaced; the new **COM21 adapter successfully backed up/programmed OpenLog**. A new loopback is unnecessary on this working connection unless a new failure warrants it.

The initial COM20 serial backup and bounded retry after wiring confirmation received no reply. A separate two-attempt check after physically crossing RX/TX also received `resp=0x00`. The swap did not establish a working orientation. AVRDUDE's [Arduino reset implementation](https://github.com/avrdudes/avrdude/blob/v8.0/src/arduino.c) toggles DTR/RTS and waits 100 ms before synchronization; a correctly wired DTR capacitor should provide reset, but its physical pulse has not been measured here. A loopback isolates serial transmit/receive before investigating that reset path.

**Actual loopback outcome:** COM20 opened and the 16-byte write returned without an error; no bytes arrived within two seconds. OpenLog was disconnected for this test. The observed sequence was `55 AA 00 FF 4F 50 45 4E 4C 4F 47 2D 46 54 44 49`, with an empty received sequence. This implicates the serial loop setup, adapter or driver path; it does not identify a broken adapter or OpenLog bootloader. Windows enumeration and driver status alone do not verify electrical transmission. No further serial attempt is warranted until the adapter pinout/contact is checked.

1. Unplug **FTDI and MCP2221A USB power**. Disconnect the FTDI wiring from OpenLog entirely. Join **FTDI TX directly to FTDI RX** with a jumper, with no OpenLog connected. Reconnect **only FTDI USB**. Keep its existing 3.3 V setting. This test needs the adapter's TX/RX labels, not the OpenLog labels.
2. Open **VS Code → Terminal → PowerShell at the repository root**, close any serial monitor, and run:

   ```powershell
   powershell -NoProfile -ExecutionPolicy Bypass -File .\08_Software\temperature-logger\Test-FtdiLoopback.ps1 -Port COM20 -WiredForLoopback
   if ($LASTEXITCODE -ne 0) { throw 'FTDI loopback failed. Stop and retain its JSON evidence.' }
   ```

   Expect **PASS**, 16 bytes echoed exactly at **115200**. The two-second test opens only the identified FTDI port, with DTR/RTS disabled. Results stay in `.local/openlog-update/ftdi-loopback-*.json`. If Windows assigns a different port, check **Device Manager → Ports → USB Serial Port** and replace `COM20`; the helper checks FTDI VID/PID before opening it. It refuses to run without the explicit loopback flag.
3. If no bytes or corrupted bytes return, stop and inspect the adapter model/pinout, jumper contact and driver. Connect directly to the adapter's labeled TX/RX pins for the next test; bypass any crossover/inverter board so it is excluded from the loop. Record what changed before repeating the command. A successful echo verifies this serial loop, including any jumper wiring used; it does **not** verify OpenLog's DTR, RX/TX connections or bootloader.
4. Unplug FTDI USB, remove the TX/RX loopback jumper, then reconnect OpenLog with **FTDI TX → RXI**, **FTDI RX → TXO**, **GND → GND**, and **DTR → DTR/GRN**, using the supply arrangement in the wiring table. Do not leave the jumper across the connected board's RX/TX. Reconnect power. If serial loopback passed but the normal backup still cannot synchronize, inspect the DTR/reset connection or use a separately planned manual-reset/ISP test; do not force the device signature or keep repeating unchanged attempts.

## Check the firmware and one new SD file

1. **Restore the I2C connection after programming:** unplug FTDI USB and disconnect its wiring from OpenLog. Keep OpenLog/MCP9600 connected through the shared Qwiic bus, then reconnect **only MCP2221A USB power**, using its existing 3.3 V supply. This avoids joining the FTDI and bridge regulator outputs. Keep other readers disconnected. In the same repository-root **PowerShell** terminal, reuse the already built Cython/HIDAPI environment:

   ```powershell
   $nativePython = Join-Path (Get-Location).Path '08_Software\mlx90614-hidapi-demo\.venv\Scripts\python.exe'
   & $nativePython .\08_Software\temperature-logger\check_openlog.py
   if ($LASTEXITCODE -ne 0) { throw 'OpenLog identity check failed; stop and retain the evidence file.' }
   ```

   Expect identity **120 (0x78)**, address **42 (0x2A)**, initialized-card status and firmware **3.1** for the official image, or **3.101** for the local experiment. The helper refuses a busy/error bridge without cancellation or USB reset. It cannot detect every competing browser tab; disconnect those yourself. Stop on a failed check; do not automatically change addresses or repeat recovery.
2. Create one exclusive new file and verify every stored byte:

   ```powershell
   & $nativePython .\08_Software\temperature-logger\check_openlog.py --write-test
   if ($LASTEXITCODE -ne 0) { throw 'SD verification failed; keep the new test file and JSON evidence.' }
   ```

   Expect **PASS**, a generated `Txxxxxxx.CSV`, and matching complete readback. Existing recordings are preserved. A failure can leave a new partial test file; the helper does not delete it. JSON evidence and the successful readback copy are in `08_Software/temperature-logger/output/`, ignored by Git. This is a short storage check, not sustained logger validation.
3. Optional, if the MCP9600 is still connected at **0x60**, check its identity and two temperatures without another SD write:

   ```powershell
   & $nativePython .\08_Software\temperature-logger\check_openlog.py --check-sensor
   if ($LASTEXITCODE -ne 0) { throw 'Sensor check failed; stop before a recording trial.' }
   ```

   Expect MCP9600 identity and plausible `hot_c`/`cold_c`. An address NACK remains a sensor/bus failure even if the SD test passed.
4. Start/reuse **http://127.0.0.1:8768/** using the [logger setup](../08_Software/temperature-logger/README.md#use-the-existing-native-environment). Click **Connect sensor**, select **1 second** recording, check **OpenLog**, then **Start recording**. After a short trial click **Stop & sync**, wait for **file closed**, download **Recorded CSV**, then **Disconnect**. To check card contents externally, remove power before moving the card. Compare the new card CSV with the downloaded CSV; retain results and errors.

## Separate SPI experiment

**Flashed and native SD recording verified.** Official 3.1 puts SPI into a disabled state after 500 ms idle, then restores it after a wake interrupt returns. Its I2C callbacks perform SD operations inside interrupts. Keeping SPI powered passed the new write/readback tests, including idle gaps. These before/after results support that suspected interaction, but do not prove sleep was active at the original failing command. This change does not address SD timeout handling inside an interrupt, card free space or supply integrity. It may increase idle consumption. Source: [pinned SparkFun firmware](https://github.com/sparkfun/Qwiic_OpenLog/blob/f3f6a3ec3f70fe4c14612b38fac360f26ee79a4c/Firmware/Qwiic_OpenLog/Qwiic_OpenLog.ino).

The separate source is `.local/openlog-update/spi-awake/Qwiic_OpenLog/`; its patch is `.local/openlog-update/spi-awake.patch`. Only two lines change: remove `power_spi_disable()` and use minor version **101**, giving **3.101**. This is a local version tag, not an upstream release. The original source and official 3.1 image are unchanged.

| Prepared image | Flash / SRAM | SHA-256 |
| --- | --- | --- |
| Official `build/Qwiic_OpenLog.ino.hex`, version 3.1 | 21,698 / 1,368 bytes | `61479e702b30a5718ecf46b0f3579c2f25032aaadd12883ab0a23ffe5900c2ac` |
| Experiment `spi-awake-build/Qwiic_OpenLog.ino.hex`, local version 3.101 | 21,688 / 1,368 bytes | `ca930c7fd55c4fd5b75c2ef84dd1d6557b99f143fe2a4ed49101fce9453ae1ef` |

Both paths are relative to `.local/openlog-update/`. Both leave **680 bytes SRAM**. The experiment's Intel HEX checksums passed; its highest application address is **0x54B7**, below the **0x7E00** bootloader boundary.

**Already completed:** a fresh 32,768-byte pre-experiment backup, 21,688-byte flash verification, Qwiic restoration, I2C version check, two CSV readback checks and a short actual native recording. The pre-experiment backup's SHA-256 is `fa95537cb9123a2217a117597ca2fbf5a4ea17485a5b1ff92b86f5ad0b19f808`; its application matched official 3.1 and its bootloader matched the factory backup. The first later MCP9600 check NACKed; one cancellation restored idle/high lines, and a subsequent probe/read at the unchanged 0x60 address passed. Its intermittent cause remains unknown. Final bridge status is idle/high with no pending read. The following steps are for reproducing the completed experiment, not required startup steps.

1. **Repeat only for another intentional flash.** Stop readers and close serial monitors. Unplug MCP2221A and FTDI USB before moving wires. Disconnect OpenLog's Qwiic cable while programming. Connect the working **3.3 V FTDI** using the wiring table above, including **DTR**, and one 3.3 V supply. Reconnect **only FTDI USB**. Board power was removed before the completed comparison; no MCP USB soft-reset command was used.
2. Open **VS Code → Terminal → New Terminal → PowerShell at the repository root**. Reuse the prepared experiment; no rebuild is needed. Run the following in this same terminal. Set `$ftdiPort` to the FTDI port shown in **Device Manager → Ports (COM & LPT) → USB Serial Port** if it has changed:

   ```powershell
   $ErrorActionPreference = 'Stop'
   $projectRoot = (Get-Location).Path
   $ftdiPort = 'COM21'
   $avrdudeRoot = Join-Path $env:LOCALAPPDATA 'Arduino15\packages\arduino\tools\avrdude\8.0.0-arduino1'
   $avrdudePath = Join-Path $avrdudeRoot 'bin\avrdude.exe'
   $avrdudeConfig = Join-Path $avrdudeRoot 'etc\avrdude.conf'
   $hexPath = Join-Path $projectRoot '.local\openlog-update\spi-awake-build\Qwiic_OpenLog.ino.hex'
   $officialHex = Join-Path $projectRoot '.local\openlog-update\build\Qwiic_OpenLog.ino.hex'
   foreach ($requiredPath in @($avrdudePath, $avrdudeConfig, $hexPath, $officialHex)) {
       if (-not (Test-Path -LiteralPath $requiredPath)) { throw "Missing: $requiredPath. Stop before programming." }
   }
   if ((Get-FileHash -LiteralPath $hexPath -Algorithm SHA256).Hash -ne 'ca930c7fd55c4fd5b75c2ef84dd1d6557b99f143fe2a4ed49101fce9453ae1ef') { throw 'Unexpected experiment image; stop.' }
   if ((Get-FileHash -LiteralPath $officialHex -Algorithm SHA256).Hash -ne '61479e702b30a5718ecf46b0f3579c2f25032aaadd12883ab0a23ffe5900c2ac') { throw 'Official rollback image changed; stop.' }
   $ftdiDevice = @(Get-PnpDevice -Class Ports -PresentOnly | Where-Object {
       $_.FriendlyName -eq "USB Serial Port ($ftdiPort)" -and $_.InstanceId -match 'FTDIBUS.*VID_0403\+PID_6001'
   })
   if ($ftdiDevice.Count -ne 1) { throw 'Expected FTDI not found; stop and check Device Manager.' }
   $comparisonBackup = Join-Path $projectRoot ('.local\openlog-update\before-experiment-' + (Get-Date -Format 'yyyyMMdd-HHmmss') + '.hex')
   if (Test-Path -LiteralPath $comparisonBackup) { throw 'Backup already exists; wait one second and repeat this step.' }
   $ErrorActionPreference = 'Continue'
   & $avrdudePath -C $avrdudeConfig -p atmega328p -c arduino -P $ftdiPort -b 115200 -D -n -x attempts=2 -vvvv -U "flash:r:${comparisonBackup}:i"
   $probeExit = $LASTEXITCODE
   $ErrorActionPreference = 'Stop'
   if ($probeExit -ne 0) { throw 'Backup/handshake failed; stop before flashing.' }
   ```

   Expect signature **`1e950f`**, a full flash backup and exit **0**. This fresh backup records the board immediately before the experiment; the earlier factory backup remains untouched. Stop on initialization failure and retain its output; do not use forced-signature flags.
3. Only after the preceding check succeeds, flash and verify the experiment in the **same PowerShell terminal**:

   ```powershell
   $ErrorActionPreference = 'Continue'
   & $avrdudePath -C $avrdudeConfig -p atmega328p -c arduino -P $ftdiPort -b 115200 -D -x attempts=2 -vvvv -U "flash:w:${hexPath}:i"
   $flashExit = $LASTEXITCODE
   $ErrorActionPreference = 'Stop'
   if ($flashExit -ne 0) { throw 'Experiment flash/verification failed; stop and retain the output.' }
   ```

   Expect **`21688 bytes of flash verified`**, exit **0**. This verifies programmed bytes; it does not verify SD operation.
4. Unplug FTDI USB and remove its wiring. Restore the shared Qwiic connection, then reconnect only MCP2221A USB, with other readers disconnected. Run **steps 1–3 of [the I2C/SD check](#check-the-firmware-and-one-new-sd-file)**; identity must show **3.101**, then a new CSV must match its complete readback. Stop at the first failure and preserve the new file/JSON. Do not loop cancellation/reset or start the dashboard on a stuck bus. Only after SD and thermocouple checks pass, run the short recording trial in step 4 of that section.
5. **Optional rollback:** reconnect FTDI with power removed as in experiment step 1. Repeat step 2 to define/check the tools, verify the official image hash and obtain a fresh backup/handshake. Then run in that same terminal:

   ```powershell
   $ErrorActionPreference = 'Continue'
   & $avrdudePath -C $avrdudeConfig -p atmega328p -c arduino -P $ftdiPort -b 115200 -D -x attempts=2 -vvvv -U "flash:w:${officialHex}:i"
   $rollbackExit = $LASTEXITCODE
   $ErrorActionPreference = 'Stop'
   if ($rollbackExit -ne 0) { throw 'Official-image rollback verification failed; stop.' }
   ```

   Expect **21,698 bytes verified**. Remove FTDI power/wiring, restore Qwiic/MCP2221A and run the read-only identity check; expect **3.1**. Rollback restores the official application, whose SD failure remains documented. Do not restore the complete factory backup through this application-flash command.

### Reproduce the experiment if its prepared build is missing

This is **optional**; the compiled experiment above is reusable. Prerequisites are the pinned official source, local libraries and toolchain from the next section. It copies source into a separate sketch and changes only the version tag and SPI gating line. In a repository-root **PowerShell** terminal:

```powershell
$ErrorActionPreference = 'Stop'
$projectRoot = (Get-Location).Path
$updateRoot = Join-Path $projectRoot '.local\openlog-update'
$sourcePath = Join-Path $updateRoot 'source\Qwiic_OpenLog-f3f6a3ec3f70fe4c14612b38fac360f26ee79a4c\Firmware\Qwiic_OpenLog'
$experimentPath = Join-Path $updateRoot 'spi-awake\Qwiic_OpenLog'
$cliPath = Join-Path $env:LOCALAPPDATA 'Programs\Arduino IDE\resources\app\lib\backend\resources\arduino-cli.exe'
foreach ($requiredPath in @($sourcePath, $cliPath, (Join-Path $updateRoot 'libraries\SerialPort'), (Join-Path $updateRoot 'libraries\SdFat'))) {
    if (-not (Test-Path -LiteralPath $requiredPath)) { throw "Missing: $requiredPath. Stop; prepare the pinned source/tools below first." }
}
New-Item -ItemType Directory -Force -Path $experimentPath | Out-Null
Get-ChildItem -LiteralPath $sourcePath -Filter '*.ino' | ForEach-Object {
    Copy-Item -LiteralPath $_.FullName -Destination (Join-Path $experimentPath $_.Name) -Force
}
$mainPath = Join-Path $experimentPath 'Qwiic_OpenLog.ino'
$sourceText = [System.IO.File]::ReadAllText($mainPath)
$oldVersion = '  .firmwareMinor = 0x01,'
$oldGate = '    power_spi_disable();'
foreach ($expectedText in @($oldVersion, $oldGate)) {
    if ([regex]::Matches($sourceText, [regex]::Escape($expectedText)).Count -ne 1) { throw 'Source differs from the pinned experiment; stop.' }
}
$sourceText = $sourceText.Replace($oldVersion, '  .firmwareMinor = 0x65, // Local 3.101 SPI-awake experiment; not an upstream release.')
$sourceText = $sourceText.Replace($oldGate, '    // Keep SPI powered: Wire callbacks perform SD I/O before loop() resumes.')
[System.IO.File]::WriteAllText($mainPath, $sourceText, [System.Text.UTF8Encoding]::new($false))
& $cliPath compile --fqbn arduino:avr:uno --libraries (Join-Path $updateRoot 'libraries') --build-path (Join-Path $updateRoot 'spi-awake-build') $experimentPath
if ($LASTEXITCODE -ne 0) { throw 'Experiment build failed; do not flash.' }
Get-FileHash -LiteralPath (Join-Path $updateRoot 'spi-awake-build\Qwiic_OpenLog.ino.hex') -Algorithm SHA256
```

Expect **21,688 flash bytes**, **1,368 SRAM bytes** and the experiment hash in the table, using the same pinned toolchain. Stop on different output; inspect the difference before programming. No build result alone establishes hardware success.

## Rebuild only if the prepared image is missing or intentionally changed

The completed build can be reused; rebuilding cannot fix a silent bootloader connection. A fresh checkout needs these sources. Run this block in a repository-root **PowerShell** terminal with network access and the installed Arduino IDE 2 / AVR core 1.8.8:

```powershell
$ErrorActionPreference = 'Stop'
$projectRoot = (Get-Location).Path
$updateRoot = Join-Path $projectRoot '.local\openlog-update'
$firmwareRevision = 'f3f6a3ec3f70fe4c14612b38fac360f26ee79a4c'
$serialPortRevision = '0a751d912af85b4a00ac4c4b8595e97df7b02166'
$cliPath = Join-Path $env:LOCALAPPDATA 'Programs\Arduino IDE\resources\app\lib\backend\resources\arduino-cli.exe'
if (-not (Test-Path -LiteralPath $cliPath)) { throw 'Arduino IDE 2 CLI is missing; install/open Arduino IDE 2 first.' }
New-Item -ItemType Directory -Force -Path $updateRoot, (Join-Path $updateRoot 'libraries') | Out-Null
Invoke-WebRequest -Uri "https://codeload.github.com/sparkfun/Qwiic_OpenLog/zip/$firmwareRevision" -OutFile (Join-Path $updateRoot 'sparkfun-source.zip')
Invoke-WebRequest -Uri "https://codeload.github.com/greiman/SerialPort/zip/$serialPortRevision" -OutFile (Join-Path $updateRoot 'serialport-source.zip')
Invoke-WebRequest -Uri 'https://codeload.github.com/greiman/SdFat/zip/refs/tags/1.1.4' -OutFile (Join-Path $updateRoot 'sdfat-1.1.4.zip')
Expand-Archive -LiteralPath (Join-Path $updateRoot 'sparkfun-source.zip') -DestinationPath (Join-Path $updateRoot 'source') -Force
Expand-Archive -LiteralPath (Join-Path $updateRoot 'serialport-source.zip') -DestinationPath (Join-Path $updateRoot 'serialport-source') -Force
Expand-Archive -LiteralPath (Join-Path $updateRoot 'sdfat-1.1.4.zip') -DestinationPath (Join-Path $updateRoot 'sdfat-source') -Force
if (-not (Test-Path -LiteralPath (Join-Path $updateRoot 'libraries\SerialPort'))) {
    Copy-Item -LiteralPath (Join-Path $updateRoot "serialport-source\SerialPort-$serialPortRevision\SerialPort") -Destination (Join-Path $updateRoot 'libraries\SerialPort') -Recurse
}
if (-not (Test-Path -LiteralPath (Join-Path $updateRoot 'libraries\SdFat'))) {
    Copy-Item -LiteralPath (Join-Path $updateRoot 'sdfat-source\SdFat-1.1.4') -Destination (Join-Path $updateRoot 'libraries\SdFat') -Recurse
}
$sketchPath = Join-Path $updateRoot "source\Qwiic_OpenLog-$firmwareRevision\Firmware\Qwiic_OpenLog"
& $cliPath compile --fqbn arduino:avr:uno --libraries (Join-Path $updateRoot 'libraries') --build-path (Join-Path $updateRoot 'build') $sketchPath
if ($LASTEXITCODE -ne 0) { throw 'Firmware build failed; do not flash.' }
```

If the AVR platform is missing, open **Arduino IDE 2 → Tools → Board → Boards Manager**, search **Arduino AVR Boards**, select **1.8.8**, and click **Install**, then repeat just the compile command. Dependencies are workspace-local **SerialPort** and **SdFat 1.1.4**; modern SdFat 2.x is incompatible with this sketch. Stop on dependency/compiler errors. See [SparkFun firmware requirements](https://github.com/sparkfun/Qwiic_OpenLog/blob/master/Firmware/README.md).

The application must remain below **32,256 bytes** to preserve the Uno Optiboot area. Retain the backup, HEX, source revisions and verification logs. Close the FTDI serial connection when finished; normal dashboard operation uses MCP2221A HID. No new logger changes are committed, pushed or deployed.
