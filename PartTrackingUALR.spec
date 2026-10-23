# Run with Python 3.11 + PyInstaller. Runtime stays beside the executable.
from pathlib import Path
import importlib.util
import os

from PyInstaller.utils.hooks import collect_all, collect_submodules, copy_metadata

root = Path(SPECPATH)
gpu_build = os.environ.get('UALR_TENSORRT_BUILD') == '1'
extra_datas = [(str(root / 'app' / 'vendor' / 'yolox_models' / name), 'app/vendor/yolox_models')
               for name in ('LICENSE', 'NOTICE')]
for package in ('torch', 'onnx', 'onnxscript', 'onnx_ir', 'sympy'):
    extra_datas += copy_metadata(package)
extra_binaries = []
extra_imports = collect_submodules('app.vendor.yolox_models')
extra_imports += ['torch.onnx', 'torch.export', 'onnxscript', 'onnx_ir', 'sympy', 'app.color_classifier']
tensor_packages = ('tensorrt', 'tensorrt_libs', 'tensorrt_bindings',
                   'tensorrt_cu12', 'tensorrt_cu12_libs', 'tensorrt_cu12_bindings')
if gpu_build:
    for package in tensor_packages:
        if importlib.util.find_spec(package) is not None:
            data, binaries, imports = collect_all(package)
            extra_datas += data
            extra_binaries += binaries
            extra_imports += imports
a = Analysis(
    [str(root / 'run.py')],
    pathex=[str(root)],
    binaries=extra_binaries, datas=extra_datas,
    hiddenimports=['zxingcpp', 'pypylon.pylon', 'pypylon.genicam', 'PySide6.QtNetwork'] + extra_imports,
    hookspath=[], runtime_hooks=[],
    excludes=['torchvision', 'torchaudio', 'transformers', 'tensorflow', 'scipy',
              'matplotlib', 'pandas', 'sklearn', 'IPython', 'notebook',
              'pytest', 'PyQt5', 'PyQt6', 'PySide2', 'tkinter', 'PIL', 'tensorboard']
             + ([] if gpu_build else list(tensor_packages)),
    # ONNX Script's @script decorator calls inspect.getsource at runtime.
    # Its imported modules therefore need source files beside the PYZ code.
    module_collection_mode={'onnxscript': 'pyz+py'},
    noarchive=False,
)
# Keep PyTorch CPU export DLLs. GPU libraries belong only to an opt-in build;
# the target station still needs a compatible NVIDIA GPU and driver.
if not gpu_build:
    a.binaries = [entry for entry in a.binaries if not any(name in entry[0].lower() for name in
        ('onnxruntime_providers_cuda', 'onnxruntime_providers_tensorrt', 'cudnn', 'cublas',
         'cufft', 'nvrtc', 'nvinfer', 'nvonnxparser'))]
# Qt on Windows uses Windows' unsuffixed ICU API. An unrelated Poppler on
# PATH can otherwise supply ICU 78 with incompatible suffixed exports.
a.binaries = [entry for entry in a.binaries
              if entry[0].lower() not in ('icuuc.dll', 'icudt78.dll')]
pyz = PYZ(list(a.pure))
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name='PartTrackingUALR',
          debug=False, bootloader_ignore_signals=False, strip=False, upx=False,
          console=False, disable_windowed_traceback=False, contents_directory='_runtime',
          icon=str(root / 'assets' / 'demo.ico'))
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name='PartTrackingUALR')
