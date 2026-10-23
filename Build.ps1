param([string]$Python = '', [switch]$TensorRT)
$ErrorActionPreference = 'Stop'
$DemoRoot = $PSScriptRoot
Set-Location -LiteralPath $DemoRoot
. (Join-Path $DemoRoot 'SetupRuntime.ps1')
Assert-DemoStopped
$env:PYTHONPATH = ''
# A workstation may already have the pinned barcode wheel in this repository's
# private dependency directory. Never inherit another application's module path.
$LocalDependencies = Join-Path $DemoRoot '.builddeps'
if (Test-Path -LiteralPath $LocalDependencies -PathType Container) { $env:PYTHONPATH = $LocalDependencies }
# Document-conversion DLLs must not shadow the application's ICU/Qt dependencies.
$env:PATH = (($env:PATH -split ';') | Where-Object { $_ -notmatch 'codex-runtimes.*(poppler|libheif)' }) -join ';'

function Test-Python311([string]$Executable) {
    if (-not $Executable -or -not (Test-Path -LiteralPath $Executable -PathType Leaf)) { return $false }
    # Windows PowerShell 5 treats redirected native stderr as an error record.
    # An unsuitable candidate must return false rather than abort discovery.
    $ErrorActionPreference = 'Continue'
    & $Executable -c 'import sys; sys.exit(0 if sys.version_info[:2] == (3,11) and sys.maxsize > 2**32 else 1)' *> $null
    return $LASTEXITCODE -eq 0
}

function Test-BuildDependencies([string]$Executable) {
    if (-not (Test-Python311 $Executable)) { return $false }
    $ErrorActionPreference = 'Continue'
    $Check = @'
import importlib.metadata as md
from pathlib import Path
from packaging.requirements import Requirement
import PySide6.QtCore, cv2, numpy, pypylon.pylon, zxingcpp, torch, onnx, onnxscript, onnx_ir, sympy, PyInstaller
for line in Path('requirements.txt').read_text().splitlines():
    line=line.strip()
    if not line or line.startswith('#'): continue
    req=Requirement(line)
    if req.marker and not req.marker.evaluate(): continue
    try: version=md.version(req.name)
    except md.PackageNotFoundError:
        if req.name.lower() != 'onnxruntime': raise
        version=md.version('onnxruntime-gpu')
    assert version in req.specifier, (req.name, version)
assert md.version('pyinstaller') == '6.21.0'
'@
    & $Executable -c $Check *> $null
    return $LASTEXITCODE -eq 0
}

$Candidates = @()
if ($Python) {
    $ResolvedPython = Get-Command $Python -ErrorAction SilentlyContinue
    if ($ResolvedPython) { $Candidates += $ResolvedPython.Source } else { $Candidates += $Python }
}
$Candidates += (Join-Path $DemoRoot '.build-venv\Scripts\python.exe')
$Candidates += (Join-Path $DemoRoot '.venv\Scripts\python.exe')
if ($env:VIRTUAL_ENV) { $Candidates += (Join-Path $env:VIRTUAL_ENV 'Scripts\python.exe') }
$Launcher = Get-Command py -ErrorAction SilentlyContinue
if ($Launcher) {
    $LaunchedPython = & $Launcher.Source -3.11 -c 'import sys; print(sys.executable)' 2>$null
    if ($LASTEXITCODE -eq 0) { $Candidates += $LaunchedPython }
}
if ($env:LOCALAPPDATA) { $Candidates += (Join-Path $env:LOCALAPPDATA 'Programs\Python\Python311\python.exe') }
$OnPathPython = Get-Command python -ErrorAction SilentlyContinue
if ($OnPathPython) { $Candidates += $OnPathPython.Source }
$Candidates = @($Candidates | Where-Object { $_ } | Select-Object -Unique)
$DemoPython = ''
foreach ($Candidate in $Candidates) {
    if (Test-BuildDependencies $Candidate) { $DemoPython = $Candidate; break }
}
if ($DemoPython) {
    Write-Output "Reusing verified Python 3.11 build environment: $DemoPython"
} else {
    $BootstrapPython = ''
    foreach ($Candidate in $Candidates) { if (Test-Python311 $Candidate) { $BootstrapPython = $Candidate; break } }
    if (-not $BootstrapPython) { throw 'Install Python 3.11 (64-bit), or run Build.ps1 -Python "C:\path\to\python.exe". Python 3.12 is not used for this build.' }
    $DemoPython = Join-Path $DemoRoot '.build-venv\Scripts\python.exe'
    if (-not (Test-Path -LiteralPath $DemoPython)) {
        & $BootstrapPython -m venv (Join-Path $DemoRoot '.build-venv')
        if ($LASTEXITCODE -ne 0) { throw 'Could not create the private build environment.' }
    }
    if (-not (Test-Python311 $DemoPython)) { throw 'The existing .build-venv is not Python 3.11 x64. Rename that folder, then build again.' }
    & $DemoPython -m pip install --index-url https://download.pytorch.org/whl/cpu torch==2.12.0
    if ($LASTEXITCODE -ne 0) { throw 'CPU PyTorch installation failed.' }
    & $DemoPython -m pip install -r (Join-Path $DemoRoot 'requirements.txt') pyinstaller==6.21.0
    if ($LASTEXITCODE -ne 0 -or -not (Test-BuildDependencies $DemoPython)) { throw 'Build dependency validation failed.' }
}
if ($TensorRT) {
    $OptionalCheck = 'import importlib.metadata as m; assert m.version("onnxruntime-gpu") == "1.23.2"; assert m.version("tensorrt-cu12") == "10.9.0.34"'
    & $DemoPython -c $OptionalCheck *> $null
    if ($LASTEXITCODE -ne 0) {
        # Optional GPU dependencies belong to a private build environment.
        if ($DemoPython -ne (Join-Path $DemoRoot '.build-venv\Scripts\python.exe')) { throw 'For -TensorRT, first use a private .build-venv with requirements-tensorrt.txt installed. The shared environment was preserved.' }
        & $DemoPython -m pip uninstall -y onnxruntime
        if ($LASTEXITCODE -ne 0) { throw 'Could not remove CPU ONNX Runtime before the optional GPU install.' }
        & $DemoPython -m pip install -r (Join-Path $DemoRoot 'requirements-tensorrt.txt')
        if ($LASTEXITCODE -ne 0) { throw 'Optional TensorRT dependency installation failed.' }
    }
    $env:UALR_TENSORRT_BUILD = '1'
} else { $env:UALR_TENSORRT_BUILD = '0' }

& $DemoPython -m PyInstaller --noconfirm --distpath .package --workpath .build PartTrackingUALR.spec
if ($LASTEXITCODE -ne 0) { throw 'Application build failed. The installed demo was preserved.' }
$Build = Join-Path $DemoRoot '.package\PartTrackingUALR'
$Validation = Join-Path $DemoRoot ('.build\validate-' + [Guid]::NewGuid().ToString('N'))
# Test the staged pair before touching either installed file. Failure preserves both.
Test-DemoCandidate $DemoRoot (Join-Path $Build 'PartTrackingUALR.exe') (Join-Path $Build '_runtime') $Validation
Install-DemoRuntime $DemoRoot (Join-Path $Build '_runtime') (Join-Path $Build 'PartTrackingUALR.exe')
Write-Output 'Build complete and self-test passed. Run Start Demo.cmd.'
