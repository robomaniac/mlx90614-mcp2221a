$ErrorActionPreference = 'Stop'
$nodeCommand = Get-Command node -ErrorAction SilentlyContinue
$previousElectronMode = $env:ELECTRON_RUN_AS_NODE
try {
    if ($nodeCommand) { $runtimePath = $nodeCommand.Source }
    else {
        $runtimePath = Join-Path $env:LOCALAPPDATA 'Programs/Microsoft VS Code/Code.exe'
        if (-not (Test-Path -LiteralPath $runtimePath)) { $runtimePath = Join-Path $env:ProgramFiles 'Microsoft VS Code/Code.exe' }
        if (-not (Test-Path -LiteralPath $runtimePath)) { throw 'Use Node.js or an installed desktop Visual Studio Code for the UI checks.' }
        $env:ELECTRON_RUN_AS_NODE = '1'
    }
    & $runtimePath (Join-Path $PSScriptRoot 'check_ui.mjs')
    exit $LASTEXITCODE
} finally { $env:ELECTRON_RUN_AS_NODE = $previousElectronMode }
