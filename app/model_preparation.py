"""Prepare and inspect models without opening cameras or motion connections."""
from __future__ import annotations

import threading
from pathlib import Path

from PySide6.QtCore import QThread, Signal


class ModelPreparationWorker(QThread):
    progress=Signal(str)
    prepared=Signal(object)
    fault=Signal(str)

    def __init__(self,settings,root:Path,parent=None):
        super().__init__(parent)
        self.settings=dict(settings,_inspect_models=True)
        self.root=Path(root)
        self._cancelled=threading.Event()

    def stop(self):
        self._cancelled.set()

    def run(self):
        from .yolox_pipeline import YoloXPipeline
        pipeline=YoloXPipeline(self.settings,self.root)
        pipeline.progress=self.progress.emit
        pipeline.cancelled=self._cancelled.is_set
        try:
            pipeline.open()
            if not self._cancelled.is_set(): self.prepared.emit(pipeline.information())
        except Exception as exc:
            if not self._cancelled.is_set(): self.fault.emit(str(exc))
        finally:
            pipeline.close()
