"""Windows bootstrap safety checks; no network, native build, or hardware."""
from __future__ import annotations

import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
import zipfile


ROOT = Path(__file__).resolve().parents[1]
POWERSHELL = shutil.which('powershell.exe')


def ps_quote(value):
    return "'" + str(value).replace("'", "''") + "'"


@unittest.skipUnless(POWERSHELL, 'Windows PowerShell required')
class RuntimeBootstrapTests(unittest.TestCase):
    def run_ps(self, source):
        with tempfile.TemporaryDirectory() as folder:
            script = Path(folder) / 'test.ps1'
            script.write_text(
                "$ErrorActionPreference = 'Stop'\n. "
                + ps_quote(ROOT / 'SetupRuntime.ps1') + '\n' + source,
                encoding='utf-8-sig',
            )
            return subprocess.run(
                [POWERSHELL, '-NoProfile', '-NonInteractive', '-ExecutionPolicy', 'Bypass', '-File', str(script)],
                text=True, capture_output=True, timeout=30,
            )

    def assert_ok(self, source):
        result = self.run_ps(source)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_scripts_parse(self):
        for filename in ('SetupRuntime.ps1', 'Build.ps1'):
            self.assert_ok(
                '$ParseErrors = $null; $Tokens = $null\n'
                '[void][System.Management.Automation.Language.Parser]::ParseFile('
                + ps_quote(ROOT / filename)
                + ', [ref]$Tokens, [ref]$ParseErrors)\n'
                'if ($ParseErrors.Count) { throw ($ParseErrors | Out-String) }'
            )

    def test_archive_only_extracts_runtime(self):
        with tempfile.TemporaryDirectory() as folder:
            base = Path(folder)
            archive = base / 'release.zip'
            destination = base / '_runtime'
            destination.mkdir()
            with zipfile.ZipFile(archive, 'w') as zipped:
                zipped.writestr('PartTrackingDemoUALR/_runtime/nested/runtime.dll', b'runtime')
                zipped.writestr('PartTrackingDemoUALR/PartTrackingUALR.exe', b'unwanted exe')
                zipped.writestr('PartTrackingDemoUALR/models/custom.onnx', b'unwanted model')
                zipped.writestr('PartTrackingDemoUALR/data/settings.json', b'unwanted settings')
            self.assert_ok(f'Expand-RuntimeArchive {ps_quote(archive)} {ps_quote(destination)}')
            self.assertEqual((destination / 'nested/runtime.dll').read_bytes(), b'runtime')
            self.assertEqual([p.relative_to(destination).as_posix() for p in destination.rglob('*') if p.is_file()], ['nested/runtime.dll'])

    def test_archive_rejects_traversal_and_windows_absolute_paths(self):
        for name in ('../escape', 'PartTrackingDemoUALR/_runtime/../../escape', 'C:/escape', '/escape', r'..\escape', 'PartTrackingDemoUALR/_runtime/x:stream'):
            with self.subTest(name=name):
                self.assert_ok('$Rejected = $false\ntry { Assert-SafeArchiveEntry ' + ps_quote(name) + ' | Out-Null } catch { $Rejected = $true }\nif (-not $Rejected) { throw "Unsafe path accepted" }')

    def test_download_hash_failure_preserves_executable_and_settings(self):
        with tempfile.TemporaryDirectory() as folder:
            base = Path(folder)
            (base / 'PartTrackingUALR.exe').write_bytes(b'tracked executable')
            (base / 'data').mkdir()
            (base / 'data/settings.json').write_text('keep settings')
            fixture = base / 'fixture.zip'
            fixture.write_bytes(b'corrupt or changed download')
            manifest = json.loads((ROOT / 'runtime-manifest.json').read_text())
            manifest.update(bytes=fixture.stat().st_size, sha256='0' * 64)
            (base / 'runtime-manifest.json').write_text(json.dumps(manifest))
            self.assert_ok(
                'function Assert-DemoStopped {}\n'
                'function Save-RuntimeArchive([string]$Url, [string]$Destination) { Copy-Item -LiteralPath '
                + ps_quote(fixture) + ' -Destination $Destination }\n'
                '$Rejected = $false\ntry { Initialize-DemoRuntime ' + ps_quote(base)
                + ' } catch { if ($_.Exception.Message -notmatch "SHA-256") { throw }; $Rejected = $true }\n'
                'if (-not $Rejected) { throw "Bad hash accepted" }'
            )
            self.assertEqual((base / 'PartTrackingUALR.exe').read_bytes(), b'tracked executable')
            self.assertEqual((base / 'data/settings.json').read_text(), 'keep settings')
            self.assertFalse((base / '_runtime').exists())

    def test_install_rolls_back_both_files_when_executable_swap_fails(self):
        with tempfile.TemporaryDirectory() as folder:
            base = Path(folder)
            old_runtime = base / '_runtime'
            old_runtime.mkdir()
            (old_runtime / 'identity').write_text('old runtime')
            (base / 'PartTrackingUALR.exe').write_text('old exe')
            new_runtime = base / 'candidate'
            new_runtime.mkdir()
            (new_runtime / 'identity').write_text('new runtime')
            new_exe = base / 'candidate.exe'
            new_exe.write_text('new exe')
            self.assert_ok(
                'function Assert-DemoStopped {}\n'
                'function Move-Item { param($LiteralPath, $Destination)\n'
                ' if ([IO.Path]::GetFileName($LiteralPath) -eq "new.exe") { throw "Injected swap failure" }\n'
                ' Microsoft.PowerShell.Management\\Move-Item -LiteralPath $LiteralPath -Destination $Destination\n}\n'
                '$Rejected = $false\ntry { Install-DemoRuntime ' + ps_quote(base) + ' '
                + ps_quote(new_runtime) + ' ' + ps_quote(new_exe)
                + ' } catch { if ($_.Exception.Message -notmatch "Injected swap failure") { throw }; $Rejected = $true }\n'
                'if (-not $Rejected) { throw "Failure not injected" }'
            )
            self.assertEqual((base / 'PartTrackingUALR.exe').read_text(), 'old exe')
            self.assertEqual((old_runtime / 'identity').read_text(), 'old runtime')

    def test_running_demo_prevents_runtime_replacement(self):
        self.assert_ok(
            'function Get-Process { [PSCustomObject]@{Id=123} }\n'
            '$Rejected = $false\ntry { Assert-DemoStopped } catch { $Rejected = $true }\n'
            'if (-not $Rejected) { throw "Running demo was ignored" }'
        )

    def test_pinned_manifest_matches_known_release(self):
        manifest = json.loads((ROOT / 'runtime-manifest.json').read_text())
        self.assertEqual(manifest['bytes'], 426673716)
        self.assertEqual(manifest['sha256'], '679edbb08d61f5779476dee2386158095652ce827203c48fd7153fac0061be04')
        self.assertIn('/v1.4.0-rc1/', manifest['url'])

    def test_failed_native_probes_return_false_in_windows_powershell(self):
        # PowerShell is deliberately not Python; stderr must not abort discovery.
        self.assert_ok(
            '$Ast = [System.Management.Automation.Language.Parser]::ParseFile('
            + ps_quote(ROOT / 'Build.ps1') + ', [ref]$null, [ref]$null)\n'
            '$Ast.FindAll({ param($Node) $Node -is [System.Management.Automation.Language.FunctionDefinitionAst] }, $false) | ForEach-Object { Invoke-Expression $_.Extent.Text }\n'
            '$ProbeExe = Join-Path $PSHOME "powershell.exe"\n'
            'if (Test-Python311 $ProbeExe) { throw "Non-Python accepted" }\n'
            'function Test-Python311 { return $true }\n'
            'if (Test-BuildDependencies $ProbeExe) { throw "Failed dependency probe accepted" }'
        )


if __name__ == '__main__':
    unittest.main()
