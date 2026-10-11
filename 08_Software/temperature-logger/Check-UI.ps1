$ErrorActionPreference = 'Stop'
$nodeCommand = Get-Command node -ErrorAction SilentlyContinue
$previousElectronMode = $env:ELECTRON_RUN_AS_NODE
$checkOutput = $null
$checkError = $null
try {
    if ($nodeCommand) { $runtimePath = $nodeCommand.Source }
    else {
        $runtimePath = Join-Path $env:LOCALAPPDATA 'Programs/Microsoft VS Code/Code.exe'
        if (-not (Test-Path -LiteralPath $runtimePath)) { $runtimePath = Join-Path $env:ProgramFiles 'Microsoft VS Code/Code.exe' }
        if (-not (Test-Path -LiteralPath $runtimePath)) { throw 'Use Node.js or an installed desktop Visual Studio Code for the UI checks.' }
        $env:ELECTRON_RUN_AS_NODE = '1'
    }
    if ($nodeCommand) {
        & $runtimePath (Join-Path $PSScriptRoot 'check_ui.mjs')
        exit $LASTEXITCODE
    }
    # Code.exe is a GUI executable: explicitly wait and capture its Node-mode
    # output so a detached process cannot make a failed check look successful.
    $checkOutput = [System.IO.Path]::GetTempFileName()
    $checkError = [System.IO.Path]::GetTempFileName()
    $checkProcess = Start-Process -FilePath $runtimePath -ArgumentList ('"' + (Join-Path $PSScriptRoot 'check_ui.mjs') + '"') -WindowStyle Hidden -Wait -PassThru -RedirectStandardOutput $checkOutput -RedirectStandardError $checkError
    Get-Content -LiteralPath $checkOutput
    $errorText = Get-Content -LiteralPath $checkError -Raw
    if ($errorText) { Write-Host $errorText }
    exit $checkProcess.ExitCode
} finally {
    $env:ELECTRON_RUN_AS_NODE = $previousElectronMode
    if ($checkOutput) { Remove-Item -LiteralPath $checkOutput }
    if ($checkError) { Remove-Item -LiteralPath $checkError }
}
