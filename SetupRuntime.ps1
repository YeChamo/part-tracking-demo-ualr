param([switch]$ForceDownload)
$ErrorActionPreference = 'Stop'

function Assert-DemoStopped {
    if (@(Get-Process -Name 'PartTrackingUALR' -ErrorAction SilentlyContinue).Count) {
        throw 'Close PartTrackingUALR before replacing its runtime, then try again. No process was stopped.'
    }
}

function Assert-WorkspacePath([string]$Root, [string]$Path) {
    $Prefix = [IO.Path]::GetFullPath($Root).TrimEnd('\') + '\'
    $Resolved = [IO.Path]::GetFullPath($Path)
    if (-not $Resolved.StartsWith($Prefix, [StringComparison]::OrdinalIgnoreCase)) {
        throw "Path must stay inside the demo folder: $Resolved"
    }
    return $Resolved
}

function Test-RuntimeFiles([string]$Runtime) {
    foreach ($Name in @('python311.dll', 'PySide6\QtCore.pyd', 'torch\lib\torch_cpu.dll', 'onnxruntime\capi\onnxruntime_pybind11_state.pyd')) {
        if (-not (Test-Path -LiteralPath (Join-Path $Runtime $Name) -PathType Leaf)) { return $false }
    }
    return $true
}

function Get-RuntimeSha256([string]$Path) {
    $Stream = [IO.File]::OpenRead($Path)
    $Hasher = [Security.Cryptography.SHA256]::Create()
    try { return [BitConverter]::ToString($Hasher.ComputeHash($Stream)).Replace('-', '').ToLowerInvariant() }
    finally { $Hasher.Dispose(); $Stream.Dispose() }
}

function Test-DemoCandidate([string]$Root, [string]$Executable, [string]$Runtime, [string]$Validation) {
    $Validation = Assert-WorkspacePath $Root $Validation
    if (-not (Test-RuntimeFiles $Runtime)) { throw 'The candidate runtime is incomplete.' }
    New-Item -ItemType Directory -Path $Validation -Force | Out-Null
    Copy-Item -LiteralPath $Executable -Destination (Join-Path $Validation 'PartTrackingUALR.exe')
    $Links = @()
    try {
        foreach ($Pair in @(@('_runtime', $Runtime), @('models', (Join-Path $Root 'models')))) {
            $Link = Join-Path $Validation $Pair[0]
            New-Item -ItemType Junction -Path $Link -Target ([IO.Path]::GetFullPath($Pair[1])) | Out-Null
            $Links += $Link
        }
        # Diagnostics are written to this isolated folder, never the operator's data.
        $Process = Start-Process -FilePath (Join-Path $Validation 'PartTrackingUALR.exe') -ArgumentList '--self-test' -WorkingDirectory $Validation -WindowStyle Hidden -Wait -PassThru
        if ($Process.ExitCode -ne 0) { throw "Runtime check failed; diagnostics: $Validation\data\runtime-check.json" }
    } finally {
        # Delete the junction itself, without recursively touching its target.
        foreach ($Link in $Links) { [IO.Directory]::Delete($Link) }
    }
}

function Install-DemoRuntime([string]$Root, [string]$Runtime, [string]$Executable = '') {
    Assert-DemoStopped
    $Target = Assert-WorkspacePath $Root (Join-Path $Root '_runtime')
    $Work = Assert-WorkspacePath $Root (Join-Path $Root ('.runtime-setup\install-' + [Guid]::NewGuid().ToString('N')))
    New-Item -ItemType Directory -Path $Work -Force | Out-Null
    Copy-Item -LiteralPath $Runtime -Destination (Join-Path $Work 'new-runtime') -Recurse
    if ($Executable) { Copy-Item -LiteralPath $Executable -Destination (Join-Path $Work 'new.exe') }
    $OldRuntime = $false; $OldExe = $false; $NewRuntime = $false; $NewExe = $false
    $TargetExe = Join-Path $Root 'PartTrackingUALR.exe'
    try {
        Assert-DemoStopped
        if (Test-Path -LiteralPath $Target) { Move-Item -LiteralPath $Target -Destination (Join-Path $Work 'old-runtime'); $OldRuntime = $true }
        if ($Executable -and (Test-Path -LiteralPath $TargetExe)) { Move-Item -LiteralPath $TargetExe -Destination (Join-Path $Work 'old.exe'); $OldExe = $true }
        Move-Item -LiteralPath (Join-Path $Work 'new-runtime') -Destination $Target; $NewRuntime = $true
        if ($Executable) { Move-Item -LiteralPath (Join-Path $Work 'new.exe') -Destination $TargetExe; $NewExe = $true }
    } catch {
        if ($NewExe) { Move-Item -LiteralPath $TargetExe -Destination (Join-Path $Work 'failed.exe') }
        if ($NewRuntime) { Move-Item -LiteralPath $Target -Destination (Join-Path $Work 'failed-runtime') }
        if ($OldRuntime) { Move-Item -LiteralPath (Join-Path $Work 'old-runtime') -Destination $Target }
        if ($OldExe) { Move-Item -LiteralPath (Join-Path $Work 'old.exe') -Destination $TargetExe }
        throw
    }
}

function Assert-SafeArchiveEntry([string]$Name) {
    $Normalized = $Name.Replace('\', '/')
    if ($Normalized.StartsWith('/') -or $Normalized.Contains(':') -or (($Normalized -split '/') -contains '..')) {
        throw "Unsafe archive entry: $Name"
    }
    return $Normalized
}

function Expand-RuntimeArchive([string]$Archive, [string]$Destination) {
    Add-Type -AssemblyName System.IO.Compression.FileSystem
    $Zip = [IO.Compression.ZipFile]::OpenRead($Archive)
    try {
        foreach ($Entry in $Zip.Entries) {
            $Name = Assert-SafeArchiveEntry $Entry.FullName
            if (-not $Name.StartsWith('PartTrackingDemoUALR/_runtime/', [StringComparison]::Ordinal)) { continue }
            if ((($Entry.ExternalAttributes -shr 16) -band 61440) -eq 40960) { throw 'Archive symlinks are not supported.' }
            $Relative = $Name.Substring('PartTrackingDemoUALR/_runtime/'.Length)
            if (-not $Relative) { continue }
            $Target = Assert-WorkspacePath $Destination (Join-Path $Destination $Relative)
            if ($Name.EndsWith('/')) { New-Item -ItemType Directory -Path $Target -Force | Out-Null; continue }
            New-Item -ItemType Directory -Path ([IO.Path]::GetDirectoryName($Target)) -Force | Out-Null
            [IO.Compression.ZipFileExtensions]::ExtractToFile($Entry, $Target, $false)
        }
    } finally { $Zip.Dispose() }
}

function Save-RuntimeArchive([string]$Url, [string]$Destination) {
    $PreviousProgress = $ProgressPreference
    try {
        $ProgressPreference = 'SilentlyContinue'
        [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
        Invoke-WebRequest -Uri $Url -OutFile $Destination -UseBasicParsing
    } finally { $ProgressPreference = $PreviousProgress }
}

function Initialize-DemoRuntime([string]$Root, [bool]$Download = $false) {
    $Manifest = Get-Content -LiteralPath (Join-Path $Root 'runtime-manifest.json') -Raw | ConvertFrom-Json
    if ($Manifest.sha256 -notmatch '^[0-9a-f]{64}$' -or $Manifest.url -notmatch '^https://github\.com/YeChamo/part-tracking-demo-ualr/releases/download/[^/]+/[^/]+\.zip$') { throw 'Invalid runtime manifest.' }
    $Executable = Join-Path $Root 'PartTrackingUALR.exe'
    if (-not (Test-Path -LiteralPath $Executable -PathType Leaf)) { throw 'PartTrackingUALR.exe is missing. Pull the complete Git repository again.' }
    $Runtime = Join-Path $Root '_runtime'
    $ExeHash = Get-RuntimeSha256 $Executable
    $Stamp = Join-Path $Runtime '.ualr-runtime.json'
    if (-not $Download -and (Test-RuntimeFiles $Runtime)) {
        try {
            if (Test-Path -LiteralPath $Stamp) {
                $Saved = Get-Content -LiteralPath $Stamp -Raw | ConvertFrom-Json
                if ($Saved.exe_sha256 -eq $ExeHash -and $Saved.archive_sha256 -eq $Manifest.sha256) { return }
            }
            Test-DemoCandidate $Root $Executable $Runtime (Join-Path $Root ('.runtime-setup\check-' + [Guid]::NewGuid().ToString('N')))
            @{exe_sha256=$ExeHash; archive_sha256=$Manifest.sha256; validation='existing-runtime-self-test'} | ConvertTo-Json | Set-Content -LiteralPath $Stamp -Encoding UTF8
            Write-Output 'Existing runtime verified.'
            return
        } catch { Write-Output "Existing runtime needs repair: $($_.Exception.Message)" }
    }
    Assert-DemoStopped
    $Work = Assert-WorkspacePath $Root (Join-Path $Root ('.runtime-setup\download-' + [Guid]::NewGuid().ToString('N')))
    New-Item -ItemType Directory -Path $Work -Force | Out-Null
    $Archive = Join-Path $Work 'runtime.zip'
    Write-Output 'Downloading the pinned Windows runtime (407 MB, first run only)...'
    Save-RuntimeArchive $Manifest.url $Archive
    if ((Get-Item -LiteralPath $Archive).Length -ne [long]$Manifest.bytes -or (Get-RuntimeSha256 $Archive) -ne $Manifest.sha256) { throw 'Runtime download failed its size or SHA-256 check. Installed files were preserved.' }
    $Candidate = Join-Path $Work '_runtime'
    New-Item -ItemType Directory -Path $Candidate | Out-Null
    Expand-RuntimeArchive $Archive $Candidate
    Test-DemoCandidate $Root $Executable $Candidate (Join-Path $Work 'validation')
    Install-DemoRuntime $Root $Candidate
    @{exe_sha256=$ExeHash; archive_sha256=$Manifest.sha256; validation='verified-release-and-self-test'} | ConvertTo-Json | Set-Content -LiteralPath $Stamp -Encoding UTF8
    Write-Output 'Runtime ready. Your executable, models and settings were preserved.'
}

if ($MyInvocation.InvocationName -ne '.') { Initialize-DemoRuntime $PSScriptRoot ([bool]$ForceDownload) }
