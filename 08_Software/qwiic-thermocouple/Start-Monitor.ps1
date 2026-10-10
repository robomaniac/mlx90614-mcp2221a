param(
    [ValidateRange(1024, 65535)] [int]$Port = 8766,
    [ValidateRange(96, 103)] [int]$Address = 96,
    [int]$DeviceIndex = -1,
    [switch]$Connect,
    [switch]$NoBrowser
)
$ErrorActionPreference = 'Stop'
$nativeFolder = Join-Path (Split-Path -Parent $PSScriptRoot) 'mlx90614-hidapi-demo'
$monitorPython = Join-Path $nativeFolder '.venv/Scripts/python.exe'
& powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $nativeFolder 'Run-Demo.ps1') -List
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
& $monitorPython (Join-Path $nativeFolder 'build_native.py')
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
$monitorArguments = @((Join-Path $PSScriptRoot 'monitor.py'), '--port', "$Port", '--address', "$Address")
if ($DeviceIndex -ge 0) { $monitorArguments += @('--device-index', "$DeviceIndex") }
if ($Connect) { $monitorArguments += '--connect' }
if ($NoBrowser) { $monitorArguments += '--no-browser' }
& $monitorPython @monitorArguments
exit $LASTEXITCODE
