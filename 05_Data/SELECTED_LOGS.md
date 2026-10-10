# Representative raw logs from the original discussion

These are **selected verbatim diagnostic lines** from the user's chat, not an exhaustive dump of thousands of near-identical successes. The surrounding user message included much longer continuous logging. Time-of-day is from the browser local clock; dates of these events are not independently verified from the log lines.

## 1. Original host/HID setup problem in Python

```text
source : The term 'source' is not recognized as the name of a cmdlet, function, script file, or operable program.
Defaulting to user installation because normal site-packages is not writeable
c:\program files (x86)\python39-32\lib\site-packages
ImportError: Unable to load any of the following libraries:libhidapi-hidraw.so libhidapi-hidraw.so.0 libhidapi-libusb.so libhidapi-libusb.so.0 libhidapi-iohidmanager.so libhidapi-iohidmanager.so.0 libhidapi.dylib hidapi.dll libhidapi-0.dll
```

**Outcome:** User later said the 64-bit Python / new venv instructions worked and the Python project ran successfully.

## 2. Live data really worked at 10 Hz

```text
[9:35:30 PM] Page loaded. isSecureContext=true. navigator.hid=true.
[9:35:32 PM] Sample rate changed to 10 Hz.
[9:35:34 PM] Using previously authorized HID device list from navigator.hid.getDevices().
[9:35:34 PM] Trying HID device: MCP2221 USB-I2C/UART Combo (0x04D8:0x00DD)
[9:35:34 PM] HID candidates: unnumbered HID reports (report ID 0)
[9:35:34 PM] Transport selected: unnumbered HID reports (report ID 0)
[9:35:34 PM] I2C cancel result: byte2=0x10
[9:35:34 PM] I2C speed set to 100000 Hz using divider 118 (0x76).
[9:35:34 PM] Initial sample - object 34.99 C - ambient 28.25 C
[9:35:34 PM] Read OK - object 34.99 C - ambient 28.23 C
[9:35:35 PM] Read OK - object 35.01 C - ambient 28.21 C
[9:35:35 PM] Read OK - object 35.05 C - ambient 28.23 C
```

Original display was a single long text span containing literal `\n` instead of actual newlines; shown here as separate lines for readability. Subsequent version fixed logger.

## 3. Intermittent sensor-word errors and recovery attempts

```text
[9:35:35 PM] Read error: Object temperature word reports the MLX90614 error flag.
[9:35:35 PM] I2C cancel result: byte2=0x10
[9:35:36 PM] Read OK - object 35.39 C - ambient 28.23 C
[9:35:36 PM] Read error: Ambient temperature word reports the MLX90614 error flag.
[9:35:36 PM] I2C cancel result: byte2=0x10
```

## 4. Cluster of HID timeouts, followed by sporadic recovery

```text
[9:48:13 PM] Read error: Timed out waiting for HID input report.
[9:48:14 PM] I2C cancel result: byte2=0x10
[9:48:17 PM] Read error: Timed out waiting for HID input report.
[9:48:18 PM] I2C cancel result: byte2=0x10
[9:49:09 PM] Read error: Timed out waiting for HID input report.
[9:49:10 PM] I2C cancel result: byte2=0x10
[9:49:10 PM] Read OK - object 34.99 C - ambient 27.79 C
```

## 5. Change to 1 Hz after high-rate problems

```text
[9:50:45 PM] Sample rate changed to 1 Hz.
[9:50:46 PM] Read error: Object temperature word reports the MLX90614 error flag.
[9:50:46 PM] I2C cancel result: byte2=0x10
[9:50:46 PM] Read OK - object 34.75 C - ambient 27.87 C
[9:50:47 PM] Read OK - object 34.93 C - ambient 27.87 C
```

## 6. Startup regression: first 0x21 log

```text
[10:10:56 PM] Page loaded. isSecureContext=true. navigator.hid=true.
[10:11:05 PM] Trying HID device: MCP2221 USB-I2C/UART Combo (0x04D8:0x00DD)
[10:11:05 PM] HID candidates: unnumbered HID reports (report ID 0)
[10:11:05 PM] Transport selected: unnumbered HID reports (report ID 0)
[10:11:05 PM] I2C cancel result: byte2=0x10
[10:11:05 PM] Connect failed: MCP2221A did not accept the new I2C speed. Status byte3=0x21.
```

## 7. 0x21 after retry/cancel change

```text
[10:53:00 PM] Page loaded. isSecureContext=true. navigator.hid=true.
[10:53:02 PM] Using previously authorized HID device list from navigator.hid.getDevices().
[10:53:02 PM] Trying HID device: MCP2221 USB-I2C/UART Combo (0x04D8:0x00DD)
[10:53:02 PM] HID candidates: unnumbered HID reports (report ID 0)
[10:53:02 PM] Transport selected: unnumbered HID reports (report ID 0)
[10:53:02 PM] I2C cancel result: byte2=0x10
[10:53:02 PM] Set speed got busy status 0x21. Retrying after another cancel. SCL=1 SDA=1 pending=0 currentDivider=0x00.
[10:53:03 PM] Connect failed: MCP2221A kept reporting busy while setting I2C speed (status byte3=0x21). SCL=1 SDA=1 pending=0 currentDivider=0x00. Another tab/app may still own the device, or SDA/SCL may be held low.
```

**Caution:** The error message speculated about SDA/SCL being held low even though both were reported as 1; do not treat that sentence as a measured diagnosis.

## 8. Skip-initial-cancel attempt did not solve it

```text
[11:12:39 PM] Page loaded. isSecureContext=true. navigator.hid=true.
[11:12:42 PM] Using previously authorized HID device list from navigator.hid.getDevices().
[11:12:42 PM] Trying HID device: MCP2221 USB-I2C/UART Combo (0x04D8:0x00DD)
[11:12:42 PM] HID candidates: unnumbered HID reports (report ID 0)
[11:12:42 PM] Transport selected: unnumbered HID reports (report ID 0)
[11:12:42 PM] Fresh MCP2221A I2C engine detected; skipping initial cancel before first speed set. SCL=1 SDA=1 pending=0 requested=0 transferred=0 buffered=0 currentDivider=0x00.
[11:12:42 PM] Set speed got busy status 0x21. Retrying after a short wait. SCL=1 SDA=1 pending=0 requested=0 transferred=0 buffered=0 currentDivider=0x00.
[11:12:44 PM] Speed-set command stayed busy even though the I2C engine now looks idle. SCL=1 SDA=1 pending=0 requested=0 transferred=0 buffered=0 currentDivider=0x00. Continuing with the MCP2221A current I2C speed and probing the MLX90614 anyway.
[11:12:45 PM] Connect failed: I2C engine stayed busy for command 0x94. Last response: 0x01
```

Subsequent revisions attempted to remove the incorrect fallback and add reset/reconnect. No subsequent user logs confirming or refuting that latest revision were provided.
