param(
    [ValidatePattern('^COM[0-9]+$')] [string]$Port = 'COM20',
    [switch]$WiredForLoopback
)
$ErrorActionPreference = 'Stop'
if (-not $WiredForLoopback) {
    throw 'Disconnect FTDI from OpenLog, join only FTDI TX to RX, reconnect FTDI USB, then run with -WiredForLoopback. No serial port opened.'
}
$ftdiDevice = @(Get-PnpDevice -Class Ports -PresentOnly | Where-Object {
    $_.FriendlyName -eq "USB Serial Port ($Port)" -and $_.InstanceId -match 'FTDIBUS.*VID_0403\+PID_6001'
})
if ($ftdiDevice.Count -ne 1) { throw 'Expected FTDI 0403:6001 port not found; no serial port opened.' }
$projectRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$outputRoot = Join-Path $projectRoot '.local\openlog-update'
New-Item -ItemType Directory -Force -Path $outputRoot | Out-Null
$resultPath = Join-Path $outputRoot ('ftdi-loopback-' + [DateTime]::UtcNow.ToString('yyyyMMddTHHmmssfffffffZ') + '.json')
$result = [ordered]@{mode='ACTUAL_FTDI_LOOPBACK';port=$Port;baud=115200;passed=$false;openlog_disconnected_confirmed=$true}
$serial = New-Object System.IO.Ports.SerialPort $Port,115200,([System.IO.Ports.Parity]::None),8,([System.IO.Ports.StopBits]::One)
$serial.Handshake = [System.IO.Ports.Handshake]::None
$serial.DtrEnable = $false
$serial.RtsEnable = $false
$serial.ReadTimeout = 100
$serial.WriteTimeout = 1000
[byte[]]$transmitted = 0x55,0xAA,0x00,0xFF,0x4F,0x50,0x45,0x4E,0x4C,0x4F,0x47,0x2D,0x46,0x54,0x44,0x49
[byte[]]$received = New-Object byte[] $transmitted.Length
$count = 0
try {
    $serial.Open()
    $serial.DiscardInBuffer()
    $serial.Write($transmitted, 0, $transmitted.Length)
    $timer = [System.Diagnostics.Stopwatch]::StartNew()
    while ($count -lt $received.Length -and $timer.ElapsedMilliseconds -lt 2000) {
        try { $count += $serial.Read($received, $count, $received.Length - $count) }
        catch [System.TimeoutException] { }
    }
    $result.sent_hex = [BitConverter]::ToString($transmitted)
    $result.received_bytes = $count
    $result.received_hex = if ($count -gt 0) { [BitConverter]::ToString($received,0,$count) } else { '' }
    $result.passed = $count -eq $transmitted.Length -and $result.sent_hex -eq $result.received_hex
    if (-not $result.passed) { throw "FTDI loopback mismatch: received $count of $($transmitted.Length) bytes." }
    "PASS: FTDI $Port at 115200; all $count test bytes echoed exactly."
} catch {
    $result.error = $_.Exception.Message
    throw
} finally {
    try { if ($serial.IsOpen) { $serial.Close() } }
    finally {
        $serial.Dispose()
        $result | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath $resultPath -Encoding UTF8
        "Evidence: $resultPath"
    }
}
