param(
    [string]$Archive = '',
    [string]$Output = '',
    [string]$Version = '1.5.1'
)
$ErrorActionPreference = 'Stop'
$OfflineRoot = $PSScriptRoot
if ($Version -notmatch '^\d+\.\d+\.\d+[a-zA-Z0-9.-]*$') { throw 'Use a valid release version.' }
if (-not $Archive) { $Archive = Join-Path $OfflineRoot ".releases\PartTrackingDemoUALR-v$Version-Windows-x64.zip" }
if (-not $Output) { $Output = Join-Path $OfflineRoot ".releases\PartTrackingDemoUALR-v$Version-Offline.exe" }
$Archive = (Resolve-Path -LiteralPath $Archive).Path
$Output = [IO.Path]::GetFullPath($Output)
if (Test-Path -LiteralPath $Output) { throw "Output already exists; choose a new file so the existing package is preserved: $Output" }
$Framework = Join-Path $env:WINDIR 'Microsoft.NET\Framework64\v4.0.30319'
$Compiler = Join-Path $Framework 'csc.exe'
if (-not (Test-Path -LiteralPath $Compiler -PathType Leaf)) { throw '.NET Framework 4.x x64 compiler was not found.' }
$Work = Join-Path $OfflineRoot ('.build\offline-' + [Guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $Work -Force | Out-Null
New-Item -ItemType Directory -Path ([IO.Path]::GetDirectoryName($Output)) -Force | Out-Null
Add-Type -AssemblyName System.IO.Compression.FileSystem
$Package = [IO.Compression.ZipFile]::OpenRead($Archive)
function Get-EmbeddedEntryHash([string]$EntryName) {
    $Entry = $Package.GetEntry('PartTrackingDemoUALR/' + $EntryName)
    if (-not $Entry) { throw "The portable package is missing $EntryName" }
    $EntryStream = $Entry.Open()
    $EntryHasher = [Security.Cryptography.SHA256]::Create()
    try { return [BitConverter]::ToString($EntryHasher.ComputeHash($EntryStream)).Replace('-','').ToLowerInvariant() }
    finally { $EntryHasher.Dispose(); $EntryStream.Dispose() }
}
try {
    $PythonHash = Get-EmbeddedEntryHash '_runtime/python311.dll'
    $ExecutableHash = Get-EmbeddedEntryHash 'PartTrackingUALR.exe'
} finally { $Package.Dispose() }
function Get-OfflineSha256([string]$Path) {
    $InputStream = [IO.File]::Open($Path,[IO.FileMode]::Open,[IO.FileAccess]::Read,([IO.FileShare]::ReadWrite -bor [IO.FileShare]::Delete))
    $InputHasher = [Security.Cryptography.SHA256]::Create()
    try { return [BitConverter]::ToString($InputHasher.ComputeHash($InputStream)).Replace('-','').ToLowerInvariant() }
    finally { $InputHasher.Dispose(); $InputStream.Dispose() }
}
$ArchiveHash = Get-OfflineSha256 $Archive
$ManifestPath = Join-Path $Work 'payload-manifest.txt'
$Manifest = @(
    "version=$Version",
    "archive_sha256=$ArchiveHash",
    "archive_bytes=$((Get-Item -LiteralPath $Archive).Length)",
    "python_sha256=$PythonHash",
    "exe_sha256=$ExecutableHash"
) -join "`n"
[IO.File]::WriteAllText($ManifestPath,$Manifest,[Text.UTF8Encoding]::new($false))
$StagedOutput = Join-Path $Work 'Offline.exe'
$Arguments = @('/nologo','/target:winexe','/platform:x64','/optimize+',
    "/out:$StagedOutput", "/resource:$Archive,UALR.PortableZip",
    "/resource:$ManifestPath,UALR.Manifest", "/win32icon:$(Join-Path $OfflineRoot 'assets\demo.ico')",
    "/reference:$(Join-Path $Framework 'System.IO.Compression.dll')",
    "/reference:$(Join-Path $Framework 'System.Windows.Forms.dll')",
    "/reference:$(Join-Path $Framework 'System.Drawing.dll')",
    (Join-Path $OfflineRoot 'scripts\OfflineLauncher.cs'))
& $Compiler @Arguments
if ($LASTEXITCODE -ne 0 -or -not (Test-Path -LiteralPath $StagedOutput)) { throw 'Offline launcher compilation failed.' }
Move-Item -LiteralPath $StagedOutput -Destination $Output
$OutputHash = Get-OfflineSha256 $Output
[IO.File]::WriteAllText($Output + '.sha256',"$OutputHash  $([IO.Path]::GetFileName($Output))`n",[Text.Encoding]::ASCII)
Write-Output "Offline package ready: $Output"
Write-Output "Embedded ZIP SHA-256: $ArchiveHash"
Write-Output "Offline EXE SHA-256: $OutputHash"
