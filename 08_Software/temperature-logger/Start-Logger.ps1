param(
    [ValidateRange(1024,65535)] [int]$Port = 8768,
    [ValidateRange(96,103)] [int]$Address = 96,
    [int]$DeviceIndex = -1,
    [switch]$Connect,
    [switch]$NoBrowser
)
$ErrorActionPreference = 'Stop'
$nativeFolder = Join-Path (Split-Path -Parent $PSScriptRoot) 'mlx90614-hidapi-demo'
$loggerPython = Join-Path $nativeFolder '.venv/Scripts/python.exe'
& powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $nativeFolder 'Run-Demo.ps1') -List
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
& $loggerPython (Join-Path $nativeFolder 'build_native.py')
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
$loggerArguments = @((Join-Path $PSScriptRoot 'logger.py'),'--port',"$Port",'--address',"$Address")
if ($DeviceIndex -ge 0) { $loggerArguments += @('--device-index',"$DeviceIndex") }
if ($Connect) { $loggerArguments += '--connect' }
if ($NoBrowser) { $loggerArguments += '--no-browser' }
& $loggerPython @loggerArguments
exit $LASTEXITCODE
