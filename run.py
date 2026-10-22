from __future__ import annotations

import argparse
import logging
import os
import sys
from pathlib import Path

ROOT = Path(sys.executable).parent if getattr(sys, 'frozen', False) else Path(__file__).resolve().parent


def main():
    parser = argparse.ArgumentParser(description='UALR standalone bottle color sorting and barcode demo')
    parser.add_argument('--smoke-test', action='store_true', help='Run simulated inspection, save screenshot and exit; never hardware')
    parser.add_argument('--self-test', action='store_true', help='Verify bundled model, barcode decoder and sorting runtime without cameras or motion')
    parser.add_argument('--duration', type=float, default=14)
    args = parser.parse_args()
    (ROOT / 'data').mkdir(exist_ok=True)
    logging.basicConfig(filename=str(ROOT / 'data' / 'demo.log'), level=logging.INFO,
                        format='%(asctime)s %(levelname)s %(message)s')
    if args.self_test:
        from app.selftest import check_runtime
        return check_runtime(ROOT)
    from PySide6.QtCore import QTimer
    from PySide6.QtWidgets import QApplication, QMessageBox
    from PySide6.QtGui import QFontDatabase, QFont
    from PySide6.QtNetwork import QLocalServer, QLocalSocket
    from app.ui import MainWindow
    app = QApplication(sys.argv[:1])
    # Also supplies real fonts to the offscreen platform used for screenshot QA.
    font_folder = Path(os.environ.get('WINDIR', 'C:/Windows')) / 'Fonts'
    for font_name in ('segoeui.ttf', 'segoeuib.ttf', 'consola.ttf'):
        font_path = font_folder / font_name
        if font_path.is_file():
            QFontDatabase.addApplicationFont(str(font_path))
    app.setFont(QFont('Segoe UI', 10))
    app.setApplicationName('Part Tracking Demo UALR')
    app.setStyle('Fusion')
    server = QLocalServer()
    if not args.smoke_test:
        sock = QLocalSocket()
        sock.connectToServer('UALR-part-tracking-demo')
        if sock.waitForConnected(150):
            QMessageBox.information(None, 'Demo already running', 'The UALR demo is already open. Use its existing window.')
            return 0
        QLocalServer.removeServer('UALR-part-tracking-demo')
        server.listen('UALR-part-tracking-demo')
    window = MainWindow(ROOT, smoke_test=args.smoke_test)
    window.show()
    if args.smoke_test:
        QTimer.singleShot(int(args.duration * 1000), window.finish_smoke_test)
    result = app.exec()
    server.close()
    return result


if __name__ == '__main__':
    raise SystemExit(main())
