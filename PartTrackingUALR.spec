# Run with Python 3.11 + PyInstaller. Runtime stays beside the executable.
from pathlib import Path

root = Path(SPECPATH)
a = Analysis(
    [str(root / 'run.py')],
    pathex=[str(root)],
    binaries=[], datas=[],
    hiddenimports=['zxingcpp', 'pypylon.pylon', 'pypylon.genicam', 'PySide6.QtNetwork'],
    hookspath=[], runtime_hooks=[],
    excludes=['torch', 'torchvision', 'torchaudio', 'transformers', 'tensorflow', 'scipy',
              'matplotlib', 'pandas', 'sklearn', 'sympy', 'IPython', 'notebook', 'onnx',
              'pytest', 'PyQt5', 'PyQt6', 'PySide2', 'tkinter', 'PIL', 'tensorboard'],
    noarchive=False,
)
# CPU inspection is deliberately portable; GPU runtimes need station-specific drivers.
a.binaries = [entry for entry in a.binaries if not any(name in entry[0].lower() for name in
    ('onnxruntime_providers_cuda', 'onnxruntime_providers_tensorrt', 'cudnn', 'cublas', 'cufft', 'nvrtc'))]
# Qt on Windows uses Windows' unsuffixed ICU API. An unrelated Poppler on
# PATH can otherwise supply ICU 78 with incompatible suffixed exports.
a.binaries = [entry for entry in a.binaries
              if entry[0].lower() not in ('icuuc.dll', 'icudt78.dll')]
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name='PartTrackingUALR',
          debug=False, bootloader_ignore_signals=False, strip=False, upx=False,
          console=False, disable_windowed_traceback=False, contents_directory='_runtime',
          icon=str(root / 'assets' / 'demo.ico'))
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name='PartTrackingUALR')
