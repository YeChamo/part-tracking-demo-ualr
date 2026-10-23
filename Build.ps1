param([string]$Python = 'python', [switch]$TensorRT)
$ErrorActionPreference = 'Stop'
$DemoRoot = $PSScriptRoot
Set-Location -LiteralPath $DemoRoot

function Assert-DemoStopped {
    $RunningDemoProcesses = @(Get-Process -Name 'PartTrackingUALR' -ErrorAction SilentlyContinue)
    if ($RunningDemoProcesses.Count -gt 0) {
        throw 'Close PartTrackingUALR before building or replacing its runtime, then run Build.ps1 again. No process was stopped.'
    }
}

Assert-DemoStopped
$env:PYTHONPATH = ''
# Do not let an unrelated document-conversion runtime shadow Windows DLLs.
$env:PATH = (($env:PATH -split ';') | Where-Object { $_ -notmatch 'codex-runtimes.*(poppler|libheif)' }) -join ';'
if (-not (Test-Path -LiteralPath (Join-Path $DemoRoot '.build-venv\Scripts\python.exe'))) {
    & $Python -m venv (Join-Path $DemoRoot '.build-venv')
    if ($LASTEXITCODE -ne 0) { throw 'Could not create the build environment.' }
}
$DemoPython = Join-Path $DemoRoot '.build-venv\Scripts\python.exe'
# Export is CPU work, even in the optional TensorRT build. Install the official
# CPU wheel first so the base requirement never pulls a CUDA PyTorch build.
& $DemoPython -m pip install --index-url https://download.pytorch.org/whl/cpu torch==2.12.0
if ($LASTEXITCODE -ne 0) { throw 'CPU PyTorch installation failed.' }
# ORT CPU and GPU distributions install the same module; never mix both.
& $DemoPython -m pip uninstall -y onnxruntime onnxruntime-gpu
if ($LASTEXITCODE -ne 0) { throw 'Could not reset the build environment ONNX Runtime distribution.' }
& $DemoPython -m pip install -r (Join-Path $DemoRoot 'requirements.txt') pyinstaller==6.21.0
if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed.' }
if ($TensorRT) {
    & $DemoPython -m pip uninstall -y onnxruntime
    if ($LASTEXITCODE -ne 0) { throw 'Could not remove CPU ONNX Runtime before the optional GPU install.' }
    & $DemoPython -m pip install -r (Join-Path $DemoRoot 'requirements-tensorrt.txt')
    if ($LASTEXITCODE -ne 0) { throw 'Optional TensorRT dependency installation failed.' }
    $env:UALR_TENSORRT_BUILD = '1'
} else {
    $env:UALR_TENSORRT_BUILD = '0'
}
& $DemoPython -m PyInstaller --noconfirm --distpath .package --workpath .build PartTrackingUALR.spec
if ($LASTEXITCODE -ne 0) { throw 'Application build failed.' }
# Recheck after the long build in case the operator opened the old application.
Assert-DemoStopped
$RuntimePath = [IO.Path]::GetFullPath((Join-Path $DemoRoot '_runtime'))
$BackupPath = [IO.Path]::GetFullPath((Join-Path $DemoRoot ('.build\runtime-backup-' + [Guid]::NewGuid().ToString('N'))))
$RootPrefix = [IO.Path]::GetFullPath($DemoRoot).TrimEnd('\') + '\'
if (-not $RuntimePath.StartsWith($RootPrefix, [StringComparison]::OrdinalIgnoreCase) -or
    -not $BackupPath.StartsWith($RootPrefix, [StringComparison]::OrdinalIgnoreCase)) {
    throw 'Runtime replacement paths must stay inside the demo folder.'
}
# Preserve the previous runtime and copy a fresh one, rather than mixing DLLs.
if (Test-Path -LiteralPath $RuntimePath) {
    Move-Item -LiteralPath $RuntimePath -Destination $BackupPath
}
Copy-Item -LiteralPath (Join-Path $DemoRoot '.package\PartTrackingUALR\_runtime') -Destination $DemoRoot -Recurse -Force
Copy-Item -LiteralPath (Join-Path $DemoRoot '.package\PartTrackingUALR\PartTrackingUALR.exe') -Destination $DemoRoot -Force
$CheckProcess = Start-Process -FilePath (Join-Path $DemoRoot 'PartTrackingUALR.exe') -ArgumentList '--self-test' -WindowStyle Hidden -Wait -PassThru
if ($CheckProcess.ExitCode -ne 0) { throw 'Runtime check failed; see data\runtime-check.json.' }
Write-Output 'Build complete. Run Start Demo.cmd.'
