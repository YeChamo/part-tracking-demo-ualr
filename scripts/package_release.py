"""Package the Git source and fresh native build, excluding workstation data."""
from __future__ import annotations

import hashlib
from pathlib import Path
import subprocess
import zipfile


def main():
    root = Path(__file__).resolve().parents[1]
    build = root / '.package' / 'PartTrackingUALR'
    executable = build / 'PartTrackingUALR.exe'
    runtime = build / '_runtime'
    if not executable.is_file() or not runtime.is_dir():
        raise SystemExit('Build the application before packaging a release.')
    output = root / '.releases'
    output.mkdir(exist_ok=True)
    archive = output / 'PartTrackingDemoUALR-v1.2.0-Windows-x64.zip'
    files = subprocess.check_output(['git','ls-files','-z'],cwd=root).decode('utf-8').split('\0')
    prefix = 'PartTrackingDemoUALR/'
    entries = []
    for name in files:
        if not name:
            continue
        relative = Path(name)
        if relative.is_absolute() or '..' in relative.parts:
            raise RuntimeError('Source path must remain inside the project.')
        if name.startswith('data/') and name != 'data/.gitkeep':
            raise RuntimeError('Saved workstation data must not be tracked or packaged.')
        if name.endswith(('.exe','.pyd','.zip')) or name.startswith(('_runtime/','.build','.package/','.releases/')):
            raise RuntimeError('Generated binaries must not be tracked as source.')
        entries.append((root / relative,prefix+relative.as_posix()))
    entries.append((executable,prefix+'PartTrackingUALR.exe'))
    for file in runtime.rglob('*'):
        if file.is_file():
            entries.append((file,prefix+'_runtime/'+file.relative_to(runtime).as_posix()))
    with zipfile.ZipFile(archive,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=5) as zf:
        zf.writestr(prefix+'data/','')
        for path,name in entries:
            zf.write(path,name)
    with zipfile.ZipFile(archive) as zf:
        names=zf.namelist()
        assert prefix+'PartTrackingUALR.exe' in names
        assert prefix+'models/yolox_nano.onnx.data' in names
        assert prefix+'Start Demo.cmd' in names
        assert all(not name.startswith(prefix+'data/') or name in (prefix+'data/',prefix+'data/.gitkeep') for name in names)
        assert prefix+'EtherMotion/EtherMotion.exe' not in names
    digest=hashlib.file_digest(archive.open('rb'),'sha256').hexdigest()
    (output/'SHA256SUMS.txt').write_text(f'{digest}  {archive.name}\n',encoding='utf-8')
    print(f'Packaged {len(entries)} files, {archive.stat().st_size/1024**2:.1f} MiB: {archive}')


if __name__=='__main__':
    main()
