param([switch]$Diagnostics)
$ErrorActionPreference = 'Stop'
$checkerPath = Join-Path $PSScriptRoot 'check_html.mjs'
$nodeCommand = Get-Command node -ErrorAction SilentlyContinue
$previousElectronMode = $env:ELECTRON_RUN_AS_NODE
try {
    if ($nodeCommand) {
        $runtimePath = $nodeCommand.Source
    } else {
        $runtimePath = Join-Path $env:LOCALAPPDATA 'Programs\Microsoft VS Code\Code.exe'
        if (-not (Test-Path -LiteralPath $runtimePath)) {
            $runtimePath = Join-Path $env:ProgramFiles 'Microsoft VS Code\Code.exe'
        }
        if (-not (Test-Path -LiteralPath $runtimePath)) {
            throw 'Install Node.js, or use an installed desktop Visual Studio Code. No JavaScript runtime was found.'
        }
        $env:ELECTRON_RUN_AS_NODE = '1'
    }
    & $runtimePath $checkerPath | Out-Host
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    if ($Diagnostics) {
        & $runtimePath (Join-Path $PSScriptRoot 'test_diagnostics.mjs') | Out-Host
        if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    }
} finally {
    $env:ELECTRON_RUN_AS_NODE = $previousElectronMode
}
