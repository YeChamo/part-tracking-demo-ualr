param([string]$Python = 'python')
$ErrorActionPreference = 'Stop'
$DemoRoot = $PSScriptRoot
Set-Location -LiteralPath $DemoRoot
$env:PYTHONPATH = ''
# Do not let an unrelated document-conversion runtime shadow Windows DLLs.
$env:PATH = (($env:PATH -split ';') | Where-Object { $_ -notmatch 'codex-runtimes.*(poppler|libheif)' }) -join ';'
$InstalledVersion = & $Python -c "import PyInstaller, cv2, numpy, onnxruntime, PySide6, zxingcpp; print(PyInstaller.__version__)" 2>$null
if ($LASTEXITCODE -eq 0 -and $InstalledVersion -eq '6.21.0') {
    $DemoPython = $Python
} else {
    if (-not (Test-Path -LiteralPath (Join-Path $DemoRoot '.build-venv\Scripts\python.exe'))) {
        & $Python -m venv (Join-Path $DemoRoot '.build-venv')
        if ($LASTEXITCODE -ne 0) { throw 'Could not create the build environment.' }
    }
    $DemoPython = Join-Path $DemoRoot '.build-venv\Scripts\python.exe'
    & $DemoPython -m pip install -r (Join-Path $DemoRoot 'requirements.txt') pyinstaller==6.21.0
    if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed.' }
}
& $DemoPython -m PyInstaller --noconfirm --distpath .package --workpath .build PartTrackingUALR.spec
if ($LASTEXITCODE -ne 0) { throw 'Application build failed.' }
Copy-Item -LiteralPath (Join-Path $DemoRoot '.package\PartTrackingUALR\PartTrackingUALR.exe') -Destination $DemoRoot -Force
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
$CheckProcess = Start-Process -FilePath (Join-Path $DemoRoot 'PartTrackingUALR.exe') -ArgumentList '--self-test' -WindowStyle Hidden -Wait -PassThru
if ($CheckProcess.ExitCode -ne 0) { throw 'Runtime check failed; see data\runtime-check.json.' }
Write-Output 'Build complete. Run Start Demo.cmd.'
