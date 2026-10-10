param(
    [ValidateRange(0.1, 200)] [double]$Hz = 10,
    [ValidateRange(0.01, 86400)] [double]$Seconds = 30,
    [switch]$Simulate,
    [switch]$Unpaced,
    [switch]$List,
    [switch]$Trace,
    [int]$DeviceIndex = -1,
    [string]$Csv = ''
)
$ErrorActionPreference = 'Stop'
if ($Unpaced -and $PSBoundParameters.ContainsKey('Hz')) { throw 'Choose -Unpaced or -Hz, not both.' }
Push-Location -LiteralPath $PSScriptRoot
try {
    $demoPython = Join-Path $PSScriptRoot '.venv/Scripts/python.exe'
    if (-not (Test-Path -LiteralPath $demoPython)) {
        python -c "import sys,struct; assert sys.version_info >= (3,10) and struct.calcsize('P') == 8, 'Use x64 CPython 3.10+ (3.11 tested).'"
        if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
        python -m venv .venv
        if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    }
    $dependencyHash = (Get-FileHash -LiteralPath requirements.txt -Algorithm SHA256).Hash
    $dependencyMarker = Join-Path $PSScriptRoot '.venv/demo-requirements.sha256'
    if (-not (Test-Path -LiteralPath $dependencyMarker) -or
        (Get-Content -LiteralPath $dependencyMarker -Raw).Trim() -ne $dependencyHash) {
        & $demoPython -m pip install --disable-pip-version-check --only-binary=:all: -r requirements.txt
        if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
        Set-Content -LiteralPath $dependencyMarker -Value $dependencyHash -Encoding ASCII
    }
    if (-not $List) {
        & $demoPython build_native.py
        if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    }
    $demoArguments = @('demo.py', '--seconds', $Seconds.ToString([Globalization.CultureInfo]::InvariantCulture))
    if ($Unpaced) { $demoArguments += '--unpaced' }
    else { $demoArguments += @('--hz', $Hz.ToString([Globalization.CultureInfo]::InvariantCulture)) }
    if ($Simulate) { $demoArguments += '--simulate' }
    if ($List) { $demoArguments += '--list' }
    if ($Trace) { $demoArguments += '--trace' }
    if ($DeviceIndex -ge 0) { $demoArguments += @('--device-index', "$DeviceIndex") }
    if ($Csv) { $demoArguments += @('--csv', $Csv) }
    & $demoPython @demoArguments
    exit $LASTEXITCODE
}
finally {
    Pop-Location
}
