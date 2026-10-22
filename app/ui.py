from __future__ import annotations

import csv
import heapq
import json
import logging
import os
import subprocess
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path

import cv2
from PySide6.QtCore import QObject, QRectF, Qt, QTimer, QUrl, Signal
from PySide6.QtGui import QColor, QDesktopServices, QFont, QIcon, QImage, QPainter, QPen
from PySide6.QtWidgets import (
    QAbstractItemView, QApplication, QCheckBox, QComboBox, QDoubleSpinBox,
    QFileDialog, QFormLayout, QFrame, QHBoxLayout, QHeaderView, QLabel,
    QLineEdit, QMainWindow, QMessageBox, QPushButton, QScrollArea, QSpinBox,
    QSplitter, QTableWidget, QTableWidgetItem, QTabWidget, QVBoxLayout, QWidget, QSizePolicy,
)

from . import settings as store
from .cameras import CameraChoice, discover_cameras
from .confidence_control import ConfidenceControl
from . import diverter
from .ethermotion import EtherMotionClient
from .fullscreen_view import FullscreenCameraWindow
from .simulation import HEIGHT, WIDTH, Simulation
from .tracking import BottleTracker, TrackingConfig
from .vision import VideoWorker

STYLE = '''
QMainWindow, QWidget { background: #1e1e1e; color: #f2f4f7; font-family: "Segoe UI"; font-size: 12px; }
QFrame#card { background: #2c2f36; border: 1px solid #3a3e46; border-radius: 10px; }
QFrame#liveInspection { background: #202a38; border: 1px solid #385778; border-radius: 10px; }
QLabel { background: transparent; }
QLabel#muted { color: #a8adb7; }
QLabel#title { font-size: 23px; font-weight: 700; }
QLabel#stat { font-size: 24px; font-weight: 700; }
QLabel#badge { background: #243b61; color: #c8dcff; padding: 7px 12px; border-radius: 12px; }
QPushButton { background: #353941; border: 1px solid #4a4f59; border-radius: 6px; padding: 9px 13px; font-weight: 600; }
QPushButton:hover { background: #424752; border-color: #6e7889; }
QPushButton:disabled { color: #777d88; background: #282b30; border-color: #343840; }
QPushButton#primary { background: #2e76f3; border-color: #5a93f7; color: white; }
QPushButton#stop { background: #4b3038; border-color: #80505b; color: #ffced2; }
QComboBox, QLineEdit, QSpinBox, QDoubleSpinBox { background: #22252a; border: 1px solid #505660; padding: 7px; border-radius: 5px; min-height: 18px; }
QComboBox QAbstractItemView { background: #2c2f36; selection-background-color: #2e76f3; }
QTabWidget::pane { border: 1px solid #3a3e46; border-radius: 8px; }
QTabBar::tab { background: #282b31; padding: 10px 11px; color: #a8adb7; }
QTabBar::tab:selected { color: #dce9ff; background: #2d3c55; border-bottom: 2px solid #2e76f3; }
QTableWidget { background: #25282e; alternate-background-color: #2c2f36; gridline-color: #3a3e46; border: none; }
QHeaderView::section { background: #333741; color: #c0c6d0; border: none; padding: 7px; text-align: left; }
QScrollArea { border: none; }
QCheckBox { spacing: 8px; padding: 5px 0; }
QCheckBox::indicator { width: 17px; height: 17px; }
QSlider::groove:horizontal { height: 5px; background: #4a5361; border-radius: 2px; }
QSlider::sub-page:horizontal { background: #2e76f3; border-radius: 2px; }
QSlider::handle:horizontal { background: #a9c8ff; width: 15px; margin: -5px 0; border-radius: 7px; }
QSlider::handle:horizontal:disabled { background: #656d79; }
QToolTip { color: #f2f4f7; background: #363a42; border: 1px solid #6b737f; }
QSplitter::handle { background: #1e1e1e; }
'''


class Jobs(QObject):
    done = Signal(int, object, object)

    def __init__(self, parent):
        super().__init__(parent)
        self.pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix='ethermotion')
        self.callbacks, self.counter = {}, 0
        self.closed = False
        self.done.connect(self._finish)

    def submit(self, function, callback):
        self.counter += 1
        ident = self.counter
        self.callbacks[ident] = callback
        future = self.pool.submit(function)

        def finished(value):
            try:
                result, error = value.result(), None
            except Exception as exc:
                result, error = None, exc
            if not self.closed:
                self.done.emit(ident, result, error)
        future.add_done_callback(finished)

    def _finish(self, ident, result, error):
        callback = self.callbacks.pop(ident, None)
        if callback:
            callback(result, error)


class VisionView(QWidget):
    def __init__(self, main):
        super().__init__()
        self.main = main
        self.setMinimumSize(620, 330)

    def mouseDoubleClickEvent(self, event):
        self.main.toggle_fullscreen()
        event.accept()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.fillRect(self.rect(), QColor('#20242b'))
        m = self.main
        frame = m.last_packet.get('frame') if m.last_packet else None
        if m.settings['source'] == 'simulation':
            w, h = WIDTH, HEIGHT
        elif frame is not None:
            h, w = frame.shape[:2]
        else:
            w, h = WIDTH, HEIGHT
        scale = min(self.width()/w, self.height()/h)
        p.translate((self.width()-w*scale)/2, (self.height()-h*scale)/2)
        p.scale(scale, scale)
        if m.settings['source'] == 'simulation':
            m.sim.draw(p, m.settings)
        elif frame is not None:
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            image = QImage(rgb.data, w, h, rgb.strides[0], QImage.Format.Format_RGB888)
            p.drawImage(QRectF(0, 0, w, h), image)
        else:
            p.setPen(QColor('#8ba1bc'))
            p.setFont(QFont('Segoe UI', 23))
            p.drawText(QRectF(0, 0, w, h), Qt.AlignmentFlag.AlignCenter, 'Choose a source, then start inspection')
        # Geometry and tracking boxes use source-image coordinates.
        rtl = m.settings['direction'] == 'rtl'
        entry = w*(1-m.settings['entry'] if rtl else m.settings['entry'])
        line = w*(1-m.settings['line'] if rtl else m.settings['line'])
        p.setPen(QPen(QColor('#418fc7'), 2/scale, Qt.PenStyle.DashLine))
        p.drawLine(int(entry), 100 if h == HEIGHT else 0, int(entry), h)
        p.setPen(QPen(QColor('#f3b252'), 2.5/scale, Qt.PenStyle.DashLine))
        p.drawLine(int(line), 94 if h == HEIGHT else 0, int(line), h)
        p.setFont(QFont('Segoe UI', max(10, round(11/scale)), QFont.Weight.DemiBold))
        p.setPen(QColor('#f6c671'))
        p.drawText(QRectF(max(0, line-160), h-37/scale, 315, 28/scale), Qt.AlignmentFlag.AlignCenter, 'DECISION / REJECT LINE')
        if m.running and m.last_packet and m.settings['source'] != 'simulation':
            for index, box in enumerate(m.last_packet.get('boxes', [])):
                x1,y1,x2,y2 = box
                center_x, center_y = (x1+x2)/2, (y1+y2)/2
                if any(not track.missed and track.bbox[0]<=center_x<=track.bbox[2]
                       and track.bbox[1]<=center_y<=track.bbox[3] for track in m.tracker.tracks):
                    continue
                p.setPen(QPen(QColor('#a9c8ff'), 2/scale, Qt.PenStyle.DashLine))
                p.setBrush(Qt.BrushStyle.NoBrush)
                p.drawRoundedRect(QRectF(x1,y1,x2-x1,y2-y1), 5/scale, 5/scale)
                colors = m.last_packet.get('colors', [])
                color = str(colors[index] if index<len(colors) else 'unknown').upper()
                p.setFont(QFont('Segoe UI', max(10, round(10/scale)), QFont.Weight.DemiBold))
                p.drawText(QRectF(max(0,x1),max(18,y1-7/scale),max(130,x2-x1),25/scale),
                           Qt.AlignmentFlag.AlignLeft, f'BOTTLE · {color}  /  MOVE TO ENTRY')
        for track in m.tracker.tracks:
            if track.missed:
                continue
            x1,y1,x2,y2 = track.bbox
            color = QColor('#fb8b94' if track.bad else '#54dfbb')
            p.setPen(QPen(color, 2/scale))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawRoundedRect(QRectF(x1-5,y1-5,x2-x1+10,y2-y1+10), 5/scale, 5/scale)
            meta = m.track_meta.get(track.id, {})
            brand = ' GATORADE' if meta.get('gatorade_label_match') else ''
            title = f"#{track.id:03d}  {meta.get('color', '').upper()}{brand}  {'1 DIVERT' if track.bad else '0 PASS'}"
            p.setFont(QFont('Segoe UI', max(10, round(10/scale)), QFont.Weight.Bold))
            text_w = p.fontMetrics().horizontalAdvance(title) + 14/scale
            tag_y = max(0, y1-30/scale)
            p.fillRect(QRectF(max(0,x1), tag_y, text_w, 24/scale), QColor('#122234'))
            p.drawText(QRectF(max(0,x1)+5/scale,tag_y,text_w,24/scale), Qt.AlignmentFlag.AlignVCenter, title)
        p.end()


class MainWindow(QMainWindow):
    def __init__(self, root: Path, smoke_test=False):
        super().__init__()
        self.root, self.smoke_test = root, smoke_test
        self.settings = store.load(root)
        # Normal launches are live camera inspections. The synthetic source is
        # only exposed by the explicit --smoke-test diagnostic.
        self.settings['source'] = ('simulation' if smoke_test else
                                   self.settings['source'] if self.settings['source'] in ('usb', 'basler') else 'usb')
        self.settings['rule'] = 'color'
        self.sim = Simulation()
        self.tracker = self.make_tracker()
        self.worker = None
        self.last_packet = None
        self.track_meta = {}
        self.session = uuid.uuid4().hex[:12]
        self.events, self.pending = [], []
        self.running = self.armed = self.arming = self.owns_motion = self.output_busy = False
        self.active_run, self.active_event = None, None
        self.active_program = None
        self.sequence_plan = None
        self.sequence_stage = 'primary'
        self.sequence_cycle = 1
        self.sequence_wait_until = None
        self.sequence_next = None
        self.phase_generation = 0
        self.pass_clearance_until = 0.0
        self.generation = 0
        self.arm_generation = 0
        self.send_gate = threading.Event()
        self.stopping_motion = False
        self.stop_acknowledged = False
        self.client = None
        self.camera_devices = []
        self.camera_scanning = False
        self.auto_start_saved_camera = not smoke_test
        self.fullscreen = None
        self.expected_confidence_revision = 0
        self.confidence_timer = QTimer(self)
        self.confidence_timer.setSingleShot(True)
        self.confidence_timer.timeout.connect(self.flush_confidence)
        self.network_poll = False
        self.last_poll = 0.0
        self.pass_count = self.divert_count = self.complete_count = 0
        self.jobs = Jobs(self)
        self.setWindowTitle('RemingtonVision • Gatorade Sorting Demo')
        self.setWindowIcon(QIcon(str(root/'assets'/'demo.ico')))
        self.resize(1450, 960)
        self.setMinimumSize(1100, 720)
        self.setStyleSheet(STYLE)
        self.build_ui()
        self.last_tick = time.monotonic()
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.tick)
        self.timer.start(30)
        if smoke_test:
            self.set_status('Ready • Simulation diagnostic', '#a9c8ff')
            QTimer.singleShot(200, self.start)
        else:
            self.set_status('Finding live cameras…', '#a9c8ff')
            QTimer.singleShot(0, self.refresh_cameras)
        self.log('Demo ready. Pass color = '+self.settings['pass_color']+'. Source = '+self.settings['source'])

    def make_tracker(self):
        return BottleTracker(TrackingConfig(direction=self.settings['direction'], line=self.settings['line'],
                                           entry=self.settings['entry'], confirm_frames=self.settings['confirm_frames'],
                                           max_miss=self.settings['max_miss']))

    def build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(22,18,22,16)
        layout.setSpacing(14)
        header = QHBoxLayout()
        brand = QLabel('RV')
        brand.setStyleSheet('background:#2e76f3;color:white;font-weight:800;font-size:18px;border-radius:9px;padding:15px;')
        header.addWidget(brand)
        title = QVBoxLayout()
        title.addWidget(self.label('Gatorade color sorting', 'title'))
        title.addWidget(self.label('RemingtonVision  /  UALR live demo', 'muted'))
        header.addLayout(title)
        header.addStretch()
        self.badge = self.label('SIMULATION • NO HARDWARE' if self.smoke_test else 'LIVE CAMERA • OUTPUT DISARMED', 'badge')
        header.addWidget(self.badge)
        self.export_button = QPushButton('Export CSV')
        self.export_button.clicked.connect(self.export)
        header.addWidget(self.export_button)
        layout.addLayout(header)
        stats = QHBoxLayout()
        self.stats = {}
        for key, title, color in [('total','BOTTLES SORTED','#f2f4f7'),('pass','PASS  /  0','#54dfbb'),('divert','DIVERT  /  1','#fb8b94'),('output','MOTION COMPLETED','#a9c8ff')]:
            card = QFrame(); card.setObjectName('card')
            box = QVBoxLayout(card); box.setContentsMargins(16,8,16,8)
            box.addWidget(self.label(title,'muted'))
            value = self.label('0','stat'); value.setStyleSheet('color:'+color)
            box.addWidget(value); self.stats[key] = value
            stats.addWidget(card)
        layout.addLayout(stats)
        controls = QHBoxLayout()
        controls.addWidget(self.label('SOURCE','muted'))
        self.source = QComboBox()
        sources = ([('Simulation','simulation'),('USB camera','usb'),('Basler / GigE','basler'),
                    ('Video file (dry run)','video')] if self.smoke_test else
                   [('USB camera','usb'),('Basler / GigE','basler')])
        for name, value in sources:
            self.source.addItem(name, value)
        self.source.setCurrentIndex(max(0, self.source.findData(self.settings['source'])))
        self.source.currentIndexChanged.connect(self.source_changed)
        self.source.setMaximumWidth(185)
        controls.addWidget(self.source)
        self.camera_picker = QComboBox()
        self.camera_picker.setMinimumWidth(155)
        self.camera_picker.setSizePolicy(QSizePolicy.Policy.Expanding,QSizePolicy.Policy.Fixed)
        self.camera_picker.addItem('Choose a camera source first',None)
        self.camera_picker.setEnabled(False)
        self.camera_picker.currentIndexChanged.connect(self.camera_choice_changed)
        controls.addWidget(self.camera_picker,1)
        self.refresh_cameras_button = QPushButton('Refresh cameras')
        self.refresh_cameras_button.setEnabled(False)
        self.refresh_cameras_button.clicked.connect(self.refresh_cameras)
        controls.addWidget(self.refresh_cameras_button)
        self.start_button = QPushButton('Start inspection'); self.start_button.setObjectName('primary')
        self.start_button.clicked.connect(self.start)
        controls.addWidget(self.start_button)
        self.stop_button = QPushButton('Stop + disarm'); self.stop_button.setObjectName('stop')
        self.stop_button.clicked.connect(self.stop)
        controls.addWidget(self.stop_button)
        self.inject_button = QPushButton('Next bottle: divert color')
        self.inject_button.clicked.connect(lambda: setattr(self.sim,'next_bad',True))
        self.reset_button = QPushButton('Reset counts'); self.reset_button.clicked.connect(self.reset_counts)
        self.fullscreen_button = QPushButton('Full screen')
        self.fullscreen_button.setToolTip('Full-screen camera view • F11 or double-click the image')
        self.fullscreen_button.clicked.connect(self.toggle_fullscreen)
        controls.addWidget(self.fullscreen_button)
        layout.addLayout(controls)
        splitter = QSplitter(Qt.Orientation.Horizontal)
        left = QWidget(); ll = QVBoxLayout(left); ll.setContentsMargins(0,0,0,0); ll.setSpacing(8)
        self.view = VisionView(self)
        ll.addWidget(self.view,1)
        self.diagnostics = self.label('Waiting for live camera inspection', 'muted')
        ll.addWidget(self.diagnostics)
        inspection = QFrame(); inspection.setObjectName('liveInspection')
        readout = QHBoxLayout(inspection); readout.setContentsMargins(16,10,16,10); readout.setSpacing(16)
        self.live_swatch = QLabel('—')
        self.live_swatch.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.live_swatch.setFixedSize(58,58)
        readout.addWidget(self.live_swatch)
        inspection_text = QVBoxLayout(); inspection_text.setSpacing(2)
        self.live_title = self.label('WAITING FOR BOTTLE', 'muted')
        self.live_title.setStyleSheet('font-weight:700;letter-spacing:1px;color:#a9c8ff;')
        self.live_detail = self.label('Live camera inspection will appear here')
        self.live_detail.setStyleSheet('font-size:17px;font-weight:700;')
        self.live_evidence = self.label('YOLOX-S bottle detection + exposed drink color', 'muted')
        inspection_text.addWidget(self.live_title)
        inspection_text.addWidget(self.live_detail)
        inspection_text.addWidget(self.live_evidence)
        readout.addLayout(inspection_text,1)
        self.live_route = self.label('AWAITING', 'badge')
        readout.addWidget(self.live_route)
        ll.addWidget(inspection)
        self.update_live_inspection()
        barcode_card = QFrame(); barcode_card.setObjectName('card')
        self.barcode_card = barcode_card
        bc = QVBoxLayout(barcode_card); bc.setContentsMargins(16,10,16,10)
        self.barcode_title = self.label('LAST BARCODE  •  SYNTHETIC DEMO DATA' if self.smoke_test else 'LAST BARCODE  •  LIVE DECODE','muted'); bc.addWidget(self.barcode_title)
        self.barcode_text = QLabel('Waiting for a bottle…')
        self.barcode_text.setTextFormat(Qt.TextFormat.PlainText)
        self.barcode_text.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.barcode_text.setSizePolicy(QSizePolicy.Policy.Ignored,QSizePolicy.Policy.Preferred)
        self.barcode_text.setStyleSheet('font-size:24px;font-family:Consolas;font-weight:600;color:#c8dcff;')
        bc.addWidget(self.barcode_text)
        self.barcode_info = self.label('Color and barcode follow the tracked bottle ID.','muted'); bc.addWidget(self.barcode_info)
        self.scanner_input = QLineEdit()
        self.scanner_input.setMaxLength(512)
        self.scanner_input.setPlaceholderText('USB barcode scanner: click here, scan, then Enter')
        self.scanner_input.returnPressed.connect(self.scanner_read)
        bc.addWidget(self.scanner_input)
        splitter.addWidget(left)
        self.tabs = QTabWidget(); self.tabs.setMinimumWidth(365); self.tabs.setMaximumWidth(470)
        self.fields = {}
        self.path_buttons = {}
        self.build_models_tab()
        self.build_sort_tab()
        self.build_conveyor_tab()
        self.build_reject_tab()
        splitter.addWidget(self.tabs)
        splitter.setSizes([970,430])
        layout.addWidget(splitter,1)
        self.table = QTableWidget(0,6)
        self.table.setHorizontalHeaderLabels(['TIME / BOTTLE','COLOR','ROUTING','BARCODE','OUTPUT','DETAIL'])
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().hide()
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(3,QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(5,QHeaderView.ResizeMode.Stretch)
        self.table.setMaximumHeight(125)
        layout.addWidget(self.table)
        footer = QHBoxLayout()
        self.status = QLabel(); footer.addWidget(self.status,1)
        open_folder = QPushButton('Open demo folder'); open_folder.clicked.connect(lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.root))))
        footer.addWidget(open_folder)
        help_button = QPushButton('Quick start'); help_button.clicked.connect(lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.root/'README.txt'))))
        footer.addWidget(help_button)
        layout.addLayout(footer)
        self.fields['yolox_mode'].currentIndexChanged.connect(self.update_enabled)
        self.fields['rule'].currentIndexChanged.connect(self.update_enabled)

    @staticmethod
    def label(text, name=None):
        label = QLabel(text)
        label.setTextFormat(Qt.TextFormat.PlainText)
        if name: label.setObjectName(name)
        return label

    def new_tab(self,name):
        inner = QWidget(); box = QVBoxLayout(inner); box.setContentsMargins(14,16,14,16); box.setSpacing(12)
        scroll = QScrollArea(); scroll.setWidgetResizable(True); scroll.setWidget(inner)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.tabs.addTab(scroll,name)
        return box

    def note(self, box, text):
        label = self.label(text,'muted'); label.setWordWrap(True); box.addWidget(label)
        return label

    def field(self, form, key, title, kind='float', minimum=0, maximum=10000, decimals=0):
        form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapLongRows)
        if kind == 'text':
            widget = QLineEdit(str(self.settings[key]))
        elif kind == 'int':
            widget = QSpinBox(); widget.setRange(int(minimum),int(maximum)); widget.setValue(int(self.settings[key]))
        else:
            widget = QDoubleSpinBox(); widget.setDecimals(decimals); widget.setRange(minimum,maximum); widget.setValue(float(self.settings[key]))
        self.fields[key] = widget
        form.addRow(title,widget)
        return widget

    def combo(self,form,key,title,choices):
        widget = QComboBox()
        for name,value in choices: widget.addItem(name,value)
        widget.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        widget.setMinimumContentsLength(10)
        widget.setSizePolicy(QSizePolicy.Policy.Expanding,QSizePolicy.Policy.Fixed)
        index = widget.findData(self.settings[key]); widget.setCurrentIndex(max(0,index))
        self.fields[key] = widget; form.addRow(title,widget)
        return widget

    def path_field(self, form, key, title, filter):
        row = QWidget(); rl = QHBoxLayout(row); rl.setContentsMargins(0,0,0,0)
        edit = QLineEdit(self.settings[key]); self.fields[key] = edit
        browse = QPushButton('…'); browse.setMaximumWidth(34)
        self.path_buttons[key] = browse
        def choose():
            path,_ = QFileDialog.getOpenFileName(self,title,str(self.root),filter)
            if path: edit.setText(path)
        browse.clicked.connect(choose)
        rl.addWidget(edit); rl.addWidget(browse); form.addRow(title,row)

    def build_sort_tab(self):
        box = self.new_tab('Color + code')
        self.note(box,'Choose the color that stays on the belt. Other colors produce decision 1 and the selected divert motion.')
        form = QFormLayout(); form.setSpacing(10)
        self.sort_form = form
        self.combo(form,'pass_color','Pass color',[(c.title(),c) for c in ['blue','yellow','white','orange','green','red','purple','clear']])
        rule_choices = ([('Drink color → pass / divert','color'),('Every Nth (simulation)','every_n'),
                         ('Divert all (simulation)','all'),('Pass all (simulation)','none')]
                        if self.smoke_test else [('Drink color → pass / divert','color')])
        self.combo(form,'rule','Sort rule',rule_choices)
        self.field(form,'every_n','Every Nth','int',2,100)
        box.addLayout(form)
        box.addWidget(self.barcode_card)
        self.note(box,'Live barcode reader: UPC / EAN / Code 128 / QR and more. Unread codes remain UNREAD. Codes are displayed and logged; color determines routing.')
        form = QFormLayout(); form.setSpacing(10)
        self.field(form,'camera_index','Manual USB index','int',0,63)
        self.path_field(form,'video_path','Video file','Videos (*.mp4 *.avi *.mov *.mkv);;All files (*)')
        if not self.smoke_test:
            form.setRowVisible(self.fields['video_path'].parentWidget(), False)
        box.addLayout(form)
        self.note(box,'Pick the camera by name in the toolbar. Manual index is an advanced fallback. The default Gatorade mode uses YOLOX-S bottle boxes and exposed drink color; trained color models remain available on the Models tab.')
        tools=QHBoxLayout()
        if self.smoke_test:
            tools.addWidget(self.inject_button)
        tools.addWidget(self.reset_button)
        box.addLayout(tools)
        box.addStretch()

    def build_models_tab(self):
        box = self.new_tab('Models')
        self.note(box,'YOLOX-S finds each bottle. The demo reads exposed drink color and sorts by the selected pass color.')
        form = QFormLayout(); form.setSpacing(10)
        form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapAllRows)
        self.model_form = form
        self.combo(form,'yolox_mode','Vision mode',[('Gatorade demo','gatorade'),('Two trained models','two_models'),('Combined trained model','combined')])
        self.path_field(form,'model_path','Bottle model (.onnx)','YOLOX ONNX models (*.onnx)')
        self.fields['model_path'].setPlaceholderText('Bundled YOLOX-S')
        self.path_field(form,'color_model_path','Color model (.onnx)','YOLOX ONNX models (*.onnx)')
        self.path_buttons['model_path'].setText('Choose'); self.path_buttons['model_path'].setMaximumWidth(70)
        self.path_buttons['color_model_path'].setText('Choose'); self.path_buttons['color_model_path'].setMaximumWidth(70)
        self.combo(form,'gatorade_label_check','Label evidence',[('Check visible label',True),('Off for speed',False)])
        box.addLayout(form)
        thresholds=QFormLayout(); thresholds.setSpacing(12)
        thresholds.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapAllRows)
        for key,title in (('confidence','Bottle confidence'),('color_confidence','Color confidence')):
            control=ConfidenceControl(float(self.settings[key]))
            control.setToolTip('Adjust during live preview while reject output is disarmed.')
            self.fields[key]=control
            thresholds.addRow(title,control)
            control.valueChanged.connect(self.confidence_changed)
        box.addLayout(thresholds)
        self.note(box,'Adjust confidence during a disarmed live preview. Color confidence is the minimum agreement among sampled pixels.')
        advanced_button=QPushButton('Advanced model settings')
        advanced_button.setCheckable(True)
        box.addWidget(advanced_button)
        advanced=QWidget(); advanced.setVisible(False)
        advanced_button.toggled.connect(advanced.setVisible)
        form=QFormLayout(advanced); form.setContentsMargins(0,0,0,0); form.setSpacing(10)
        self.field(form,'model_class_id','Bottle class ID (-1 = all)','int',-1,999)
        self.field(form,'image_size','Bottle input size','int',160,1920)
        names=self.field(form,'model_class_names','Bottle class order','text')
        names.setPlaceholderText('Read from ONNX; or enter class order')
        self.field(form,'color_image_size','Color input size','int',160,1920)
        names=self.field(form,'color_class_names','Color class order','text')
        names.setPlaceholderText('Read from ONNX; e.g. orange,blue,green')
        mapping=self.field(form,'color_class_map','Class → color map','text')
        mapping.setPlaceholderText('Optional: 0:orange,1:blue,2:green')
        box.addWidget(advanced)
        self.note(box,'A blank model path uses the bundled YOLOX-S. Label evidence is visual context; routing follows drink color. Trained model modes are available for future inspections.')
        box.addStretch()

    def confidence_changed(self, _value=None):
        if self.armed or self.arming or self.owns_motion:
            return
        self.settings['confidence']=self.fields['confidence'].value()
        self.settings['color_confidence']=self.fields['color_confidence'].value()
        self.confidence_timer.start(150)
        self.update_enabled()

    def flush_confidence(self):
        self.confidence_timer.stop()
        store.save(self.root,self.settings)
        if self.running and self.worker is not None and self.settings['source']!='simulation':
            self.expected_confidence_revision=self.worker.update_confidence(self.settings['confidence'],self.settings['color_confidence'])
            self.tracker.reset(); self.track_meta.clear()
            self.set_status('Applying YOLOX confidence thresholds…','#8dcaff')
        self.update_enabled()

    def toggle_fullscreen(self):
        if self.fullscreen is not None:
            self.fullscreen.close()
            return
        window=FullscreenCameraWindow(VisionView(self),self)
        self.fullscreen=window
        window.closed.connect(lambda: setattr(self,'fullscreen',None))
        window.open_fullscreen()

    def keyPressEvent(self,event):
        if event.key()==Qt.Key.Key_F11:
            self.toggle_fullscreen(); event.accept(); return
        super().keyPressEvent(event)

    def build_conveyor_tab(self):
        box = self.new_tab('Tracking')
        self.note(box,'The conveyor runs from its hardware controls. These measurements only predict bottle arrival; the app controls the diverter through EtherMotion.')
        form = QFormLayout(); form.setSpacing(11)
        self.combo(form,'direction','Travel direction',[('Left → right','ltr'),('Right → left','rtl')])
        self.field(form,'entry','Entry zone fraction',minimum=.05,maximum=.60,decimals=2)
        self.field(form,'line','Decision line fraction',minimum=.40,maximum=.95,decimals=2)
        self.field(form,'confirm_frames','Confirm color frames','int',1,20)
        self.field(form,'max_miss','Track timeout (s)',minimum=.05,maximum=3,decimals=2)
        self.field(form,'field_width','Visible belt width (mm)',minimum=50,maximum=10000)
        self.field(form,'belt_speed','Measured belt speed (mm/s)',minimum=5,maximum=2500)
        box.addLayout(form)
        self.note(box,'Track IDs follow bottles from the entry zone to the decision line. Each bottle makes one 0 / 1 decision. A missed or stale camera frame cannot trigger a motion.')
        form = QFormLayout(); form.setSpacing(11)
        self.field(form,'distance_mm','Line → diverter (mm)',minimum=0,maximum=10000)
        self.field(form,'delay_ms','Extra delay (ms)','int',0,10000)
        self.field(form,'lead_ms','Trigger lead (ms)','int',0,10000)
        self.field(form,'move_ms','Measured gate move (ms)','int',0,10000)
        self.field(form,'bottle_length_mm','Bottle length along belt (mm)',minimum=1,maximum=1000)
        self.field(form,'clearance_ms','Clearance margin (ms)','int',0,10000)
        box.addLayout(form)
        self.timing_note=self.note(box,'')
        for key in ('belt_speed','distance_mm','delay_ms','lead_ms','move_ms','bottle_length_mm','clearance_ms'):
            self.fields[key].valueChanged.connect(self.refresh_timing)
        self.refresh_timing()
        self.note(box,'Allow network/PC margin in Trigger lead. Live output requires enough upstream travel time and lead at least as long as the measured gate move. Stop + disarm when the hardware-controlled belt stops; there is no encoder or belt-run input.')
        box.addStretch()

    def refresh_timing(self, _value=None):
        values=self.settings.copy()
        for key in ('belt_speed','distance_mm','delay_ms','lead_ms','move_ms','bottle_length_mm','clearance_ms'):
            values[key]=self.fields[key].value()
        try: self.timing_note.setText(diverter.preview(values))
        except ValueError as exc: self.timing_note.setText(str(exc))

    def build_reject_tab(self):
        box = self.new_tab('Diverter')
        self.note(box,'Set a separate action for PASS (0) and REJECT (1). Choose one complete Once cycle, or a position program followed by a timed hold and a return program.')
        form = QFormLayout(); form.setSpacing(10)
        self.field(form,'base_url','Service URL','text')
        self.program = QComboBox(); self.program.addItem('Discover Once programs…','')
        form.addRow('REJECT (1) program',self.program)
        self.pass_program=QComboBox(); self.pass_program.addItem('Let pass / no movement','')
        form.addRow('PASS (0) program',self.pass_program)
        self.return_program=QComboBox(); self.return_program.addItem('Return included in main cycle','')
        form.addRow('Return program',self.return_program)
        for widget in (self.program,self.pass_program,self.return_program):
            widget.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
            widget.setMinimumContentsLength(10)
            widget.setSizePolicy(QSizePolicy.Policy.Expanding,QSizePolicy.Policy.Fixed)
        self.field(form,'reject_cycles','REJECT cycles per bottle','int',1,10)
        self.field(form,'pass_cycles','PASS cycles per bottle','int',1,10)
        self.field(form,'hold_ms','Hold / repeat gap (ms)','int',0,30000)
        box.addLayout(form)
        self.connect_button = QPushButton('Discover / check connection'); self.connect_button.clicked.connect(self.discover)
        box.addWidget(self.connect_button)
        self.connection_note = self.note(box,'Not connected. Only programs saved as Once are offered.')
        self.arm = QCheckBox('Enable live diverter actions')
        self.arm.setEnabled(False); self.arm.toggled.connect(self.toggle_arm); box.addWidget(self.arm)
        self.output_note = self.note(box,'DISARMED • Simulation and video files never move hardware.')
        self.motion_label = self.note(box,'No motion requested.')
        self.open_motion = QPushButton('Open EtherMotion'); self.open_motion.clicked.connect(self.launch_ethermotion); box.addWidget(self.open_motion)
        self.note(box,'With a return program, the gate waits for both the configured hold and calculated bottle clearance before returning. Without one, the main EtherMotion cycle must include its own hold and return. Repeats run only after confirmed completion, never as simultaneous triggers.')
        self.note(box,'A busy diverter or overlapping pass/reject window stops inspection and disarms output. This cannot stop the hardware-controlled conveyor; use its hardware controls. Connect and commission the diverter in EtherMotion first.')
        self.note(box,'Accepted ≠ completed. Motion completion is checked separately. Software reports controller commands; it does not prove physical gate position.')
        box.addStretch()

    def collect_settings(self):
        for key,widget in self.fields.items():
            if isinstance(widget,QComboBox): value = widget.currentData()
            elif isinstance(widget,QLineEdit): value = widget.text().strip()
            else: value = widget.value()
            self.settings[key] = value
        self.settings['source'] = self.source.currentData()
        self.settings['program_id'] = self.program.currentData() or self.settings.get('program_id','')
        self.settings['pass_program_id'] = self.pass_program.currentData() or ''
        self.settings['return_program_id'] = self.return_program.currentData() or ''
        if not 0 < self.settings['entry'] < self.settings['line'] < 1:
            raise ValueError('Entry zone must be smaller than the decision line fraction.')
        if self.settings['source'] != 'simulation' and self.settings['rule'] != 'color':
            raise ValueError('Choose YOLOX color → 0 / 1 for a camera or video.')
        if self.settings['source'] in ('usb','basler'):
            selection=self.camera_picker.currentData()
            if selection == 'manual' and self.settings['source']=='usb':
                self.settings.update(camera_manual=True,camera_id='',camera_name=f"Manual USB camera {self.settings['camera_index']}")
            elif isinstance(selection,CameraChoice) and selection.kind==self.settings['source']:
                if selection.kind=='usb':
                    self.settings.update(camera_manual=False,camera_id=selection.id,camera_name=selection.name,camera_index=selection.index)
                else:
                    self.settings['basler_serial']=selection.serial
            else:
                raise ValueError('Choose your camera by name from the top camera list, then start inspection.')
        store.save(self.root,self.settings)

    def source_changed(self):
        if self.running: self.stop()
        self.last_packet = None
        self.settings['source'] = self.source.currentData()
        self.badge.setText('SIMULATION • NO HARDWARE' if self.settings['source']=='simulation' else ('VIDEO • NO HARDWARE' if self.settings['source']=='video' else 'LIVE CAMERA • OUTPUT DISARMED'))
        self.inject_button.setEnabled(self.settings['source']=='simulation')
        self.barcode_title.setText('LAST BARCODE  •  SYNTHETIC DEMO DATA' if self.settings['source']=='simulation' else 'LAST BARCODE  •  LIVE DECODE')
        self.barcode_text.setText('Waiting for a bottle…')
        self.arm.setEnabled(False)
        if self.settings['source'] in ('usb','basler'):
            self.refresh_cameras()
        else:
            self.camera_picker.blockSignals(True)
            self.camera_picker.clear(); self.camera_picker.addItem('No camera needed for this source',None)
            self.camera_picker.blockSignals(False)
        self.update_enabled()
        self.view.update()

    def camera_choice_changed(self):
        if not hasattr(self,'fields'): return
        self.update_enabled()
        selection=self.camera_picker.currentData()
        if isinstance(selection,CameraChoice):
            self.camera_picker.setToolTip(f"{selection.name}\n{selection.serial if selection.kind=='basler' else selection.device_path}")
            self.set_status('Selected '+selection.name+' • Start inspection to connect.','#8dcaff')

    def refresh_cameras(self):
        if self.running or self.owns_motion or self.camera_scanning: return
        self.camera_scanning=True
        source=self.source.currentData()
        self.update_enabled()
        self.set_status('Looking for connected cameras…','#8dcaff')
        def done(devices,error):
            self.camera_scanning=False
            if self.source.currentData()!=source:
                self.update_enabled()
                if self.source.currentData() in ('usb','basler'):
                    self.refresh_cameras()
                return
            self.camera_devices=devices or []
            self.camera_picker.blockSignals(True)
            self.camera_picker.clear()
            self.camera_picker.addItem('Select your camera…',None)
            for device in self.camera_devices:
                if device.kind!=source: continue
                suffix=f'USB {device.index}' if device.kind=='usb' else f'Basler {device.serial}'
                self.camera_picker.addItem(f'{device.name}  ·  {suffix}',device)
            if source=='usb':
                self.camera_picker.addItem('Manual camera index (advanced)','manual')
            restored=0
            for index in range(1,self.camera_picker.count()):
                device=self.camera_picker.itemData(index)
                if isinstance(device,CameraChoice) and ((source=='usb' and device.id==self.settings.get('camera_id')) or
                    (source=='basler' and device.serial==self.settings.get('basler_serial'))):
                    restored=index; break
                if source=='usb' and device=='manual' and self.settings.get('camera_manual'):
                    restored=index
            self.camera_picker.setCurrentIndex(restored)
            self.camera_picker.blockSignals(False)
            count=sum(device.kind==source for device in self.camera_devices)
            if error:
                self.set_status('Camera discovery failed: '+str(error),'#f3b252')
            elif restored:
                self.set_status('Saved camera selected • Start inspection to connect.','#8dcaff')
            elif self.settings.get('camera_id') and source=='usb':
                self.set_status('Saved camera is unavailable. Choose a connected camera; no fallback was opened.','#f3b252')
            else:
                self.set_status(f'{count} camera(s) found • choose the conveyor camera by name.','#8dcaff')
            self.update_enabled()
            auto_start = self.auto_start_saved_camera
            self.auto_start_saved_camera = False
            if restored and auto_start and not self.running:
                QTimer.singleShot(0, self.start)
        self.jobs.submit(discover_cameras,done)

    def start(self):
        if self.running or self.owns_motion:
            return
        if self.worker and self.worker.isRunning():
            self.set_status('Camera is still releasing. Wait, then start again.','#f3b252'); return
        try:
            self.collect_settings()
            self.confidence_timer.stop()
            self.expected_confidence_revision=0
            self.tracker = self.make_tracker()
            self.track_meta.clear(); self.pending.clear(); self.last_packet = None
            self.pass_clearance_until=0.0
            self.generation += 1
            self.running = True
            self.started_at = time.monotonic()
            self.last_tick = time.monotonic()
            if self.settings['source']=='simulation':
                self.sim = Simulation()
                self.set_status('Running • Color sort simulation','#54dfbb')
            else:
                self.worker = VideoWorker(self.settings.copy(),self.root)
                worker = self.worker
                worker.fault.connect(lambda message: self.camera_fault(worker,message))
                worker.ready.connect(lambda message: self.set_status('Running • '+message,'#54dfbb') if self.worker is worker and self.running else None)
                self.worker.start()
                self.set_status('Opening source and loading bottle detector…','#8dcaff')
            self.update_enabled()
            self.log('Inspection started • '+self.settings['source']+' • pass='+self.settings['pass_color'])
        except Exception as exc:
            self.running = False
            self.set_status(str(exc),'#fb8b94')
            self.update_enabled()

    def stop(self):
        self.running = False
        if self.confidence_timer.isActive(): self.flush_confidence()
        self.generation += 1
        for _,_,event in self.pending:
            event['output']='CANCELLED'; self.refresh_event(event)
        self.pending.clear()
        self.tracker.reset()
        self.update_live_inspection()
        if self.worker: self.worker.stop()
        self.set_disarmed()
        self.request_motion_stop()
        self.set_status('Stopped • pending decisions cleared • output disarmed','#f3b252')
        self.update_enabled(); self.view.update()

    def camera_fault(self,worker,message):
        if worker is self.worker and self.running:
            self.fail('Camera / vision: '+message)

    def fail(self,message):
        logging.error(message)
        self.stop()
        self.set_status(message,'#fb8b94')
        self.motion_label.setText(message)

    def set_disarmed(self):
        self.send_gate.clear()
        self.arm_generation += 1
        self.armed = self.arming = False
        self.arm.blockSignals(True); self.arm.setChecked(False); self.arm.blockSignals(False)
        self.output_note.setText('DISARMED • no new divert commands')
        if self.settings['source'] in ('usb','basler'):
            self.badge.setText('LIVE CAMERA • OUTPUT DISARMED')

    def update_enabled(self):
        self.start_button.setEnabled(not self.running and not self.owns_motion and not self.camera_scanning)
        for widget in self.fields.values(): widget.setEnabled(not self.running)
        for button in self.path_buttons.values(): button.setEnabled(not self.running)
        mode=self.fields['yolox_mode'].currentData()
        self.sort_form.setRowVisible(self.fields['rule'], self.smoke_test)
        self.sort_form.setRowVisible(self.fields['every_n'], self.smoke_test and self.fields['rule'].currentData()=='every_n')
        two_models=mode=='two_models'
        self.model_form.setRowVisible(self.fields['color_model_path'].parentWidget(), two_models)
        self.model_form.setRowVisible(self.fields['gatorade_label_check'], mode=='gatorade')
        for key in ('color_model_path','color_class_names','color_image_size'):
            self.fields[key].setEnabled(not self.running and two_models)
        self.path_buttons['color_model_path'].setEnabled(not self.running and two_models)
        self.fields['model_class_id'].setEnabled(not self.running and mode!='combined')
        self.fields['gatorade_label_check'].setEnabled(not self.running and mode=='gatorade')
        for key in ('confidence','color_confidence'):
            self.fields[key].setEnabled(not self.armed and not self.arming and not self.owns_motion)
        camera_source=self.source.currentData() in ('usb','basler')
        self.camera_picker.setEnabled(not self.running and not self.owns_motion and not self.camera_scanning and camera_source)
        self.refresh_cameras_button.setEnabled(not self.running and not self.owns_motion and not self.camera_scanning and camera_source)
        self.fields['camera_index'].setEnabled(not self.running and self.source.currentData()=='usb' and self.camera_picker.currentData()=='manual')
        for widget in (self.program,self.pass_program,self.return_program):
            widget.setEnabled(not self.running and not self.armed and not self.arming and not self.owns_motion)
        self.connect_button.setEnabled(not self.armed and not self.arming and not self.owns_motion)
        self.reset_button.setEnabled(not self.running)
        thresholds_ready=not self.confidence_timer.isActive() and (self.last_packet or {}).get('confidence_revision',0)>=self.expected_confidence_revision
        self.arm.setEnabled(self.running and not self.owns_motion and not self.arming and self.settings['source'] in ('usb','basler') and self.client is not None and bool(self.program.currentData()) and thresholds_ready)

    def tick(self):
        now = time.monotonic(); dt = min(.12,max(.001,now-self.last_tick)); self.last_tick = now
        if self.running:
            try:
                if self.settings['source']=='simulation':
                    boxes,reasons = self.sim.update(dt,self.settings)
                    tracks,decisions = self.tracker.update(boxes,reasons,now,WIDTH,HEIGHT)
                    from .barcode_fixture import demo_barcode
                    for track in tracks:
                        if not self.sim.bottles: continue
                        bottle = min(self.sim.bottles,key=lambda b: abs(b['x']-(track.bbox[0]+track.bbox[2])/2))
                        code = demo_barcode(bottle['seq'])
                        self.track_meta[track.id] = {'color':bottle['kind'],'barcode':code,'format':'EAN-13 (synthetic)'}
                    self.diagnostics.setText(f"SIMULATION  •  YOLOX inference is not running  •  {len(tracks)} tracked  •  Pass {self.settings['pass_color']}  •  Synthetic EAN-13 barcodes")
                    for decision in decisions: self.decision(decision)
                elif self.worker:
                    packet = self.worker.take_latest()
                    if packet:
                        self.last_packet = packet
                        age = now-packet['captured']
                        if age > .85:
                            self.fail(f'Inspection frame is stale ({age:.2f}s); output disarmed.'); return
                        if packet.get('inspection_ready',True):
                            h,w = packet['frame'].shape[:2]
                            tracks,decisions = self.tracker.update(packet['boxes'],packet['reasons'],packet['captured'],w,h)
                            self.update_meta(packet,tracks)
                            self.update_live_inspection(tracks,packet)
                            for decision in decisions: self.decision(decision)
                        self.diagnostics.setText(f"{packet.get('vision_pipeline','YOLOX')}  •  {packet.get('fps',0):.1f} FPS  •  {packet.get('inference_ms',0):.0f} ms model  •  {packet.get('inspection_ms',0):.0f} ms color/label  •  frame age {age*1000:.0f} ms  •  {packet.get('barcode_decoder','barcode reader')}")
                        if not packet.get('inspection_ready',True):
                            self.fail(packet.get('inspection_error','Inspection unavailable')); return
                    elif self.last_packet and now-self.last_packet['captured'] > 1.0:
                        self.fail('No fresh camera image for 1 second. Inspection stopped.'); return
                    elif self.last_packet is None and now-self.started_at>15:
                        self.fail('Source did not deliver its first inspection within 15 seconds.'); return
                    self.update_enabled()
                if self.running: self.dispatch_due(now)
            except Exception as exc:
                self.fail('Inspection error: '+str(exc))
        if self.output_busy and self.owns_motion:
            if self.sequence_wait_until is not None and not self.stopping_motion:
                self.resume_sequence(now)
            elif not self.network_poll and now-self.last_poll>.18:
                self.poll_motion()
        self.view.update()

    def update_meta(self,packet,tracks):
        boxes = packet['boxes']; colors = packet.get('colors',[]); codes = packet.get('barcodes',[])
        color_confidences = packet.get('color_confidences',[])
        brand_matches = packet.get('brand_matches',[])
        fresh = [t for t in tracks if not t.missed]
        for track in fresh:
            meta = self.track_meta.setdefault(track.id,{'color':'unknown','barcode':'UNREAD','format':'',
                                                        'gatorade_label_match':False})
            cx=(track.bbox[0]+track.bbox[2])/2; cy=(track.bbox[1]+track.bbox[3])/2
            if boxes:
                i=min(range(len(boxes)),key=lambda j: abs((boxes[j][0]+boxes[j][2])/2-cx)+abs((boxes[j][1]+boxes[j][3])/2-cy))
                if i<len(colors): meta['color']=colors[i]
                if i<len(color_confidences): meta['color_confidence']=color_confidences[i]
                if i<len(brand_matches) and brand_matches[i]: meta['gatorade_label_match']=True
            for code in codes:
                box=code.get('bbox')
                if box:
                    code_x=(box[0]+box[2])/2; code_y=(box[1]+box[3])/2
                    if not(track.bbox[0]<=code_x<=track.bbox[2] and track.bbox[1]<=code_y<=track.bbox[3]): continue
                    owners=[t for t in fresh if t.bbox[0]<=code_x<=t.bbox[2] and t.bbox[1]<=code_y<=t.bbox[3]]
                    if len(owners)!=1: continue
                else:
                    # Unlocalized codes cannot be assigned to a specific physical bottle.
                    continue
                meta.update(barcode=code['text'],format=code.get('format',''))
                self.show_barcode(track.id,meta)
        active={t.id for t in tracks}
        if len(self.track_meta)>500:
            self.track_meta={k:v for k,v in self.track_meta.items() if k in active}
        if codes and not fresh:
            self.barcode_text.setText(str(codes[-1]['text']))
            self.barcode_info.setText('Read in frame • not associated with a tracked bottle')

    def update_live_inspection(self, tracks=None, packet=None):
        fresh = [track for track in (tracks or []) if not track.missed]
        if not fresh and packet and packet.get('boxes'):
            boxes = packet['boxes']
            index = max(range(len(boxes)), key=lambda i: (boxes[i][2]-boxes[i][0])*(boxes[i][3]-boxes[i][1]))
            color = str(packet.get('colors',[])[index] if index<len(packet.get('colors',[])) else 'unknown').lower()
            values = packet.get('color_confidences',[])
            support = max(0.0,min(1.0,float(values[index]))) if index<len(values) else 0.0
            matches = packet.get('brand_matches',[])
            label = 'label visible' if index<len(matches) and matches[index] else 'label not confirmed'
            self.show_live_color(color,support)
            self.live_title.setText('BOTTLE DETECTED · NOT TRACKED')
            self.live_evidence.setText(f'{label}  •  move across blue entry line to start sorting')
            self.live_route.setText('MOVE TO ENTRY')
            self.live_route.setStyleSheet('background:#35445a;color:#c8dcff;padding:9px 12px;border-radius:8px;font-weight:700;')
            return
        if not fresh:
            self.live_swatch.setText('—')
            self.live_swatch.setStyleSheet('background:#35445a;color:#a9c8ff;border-radius:10px;font-size:26px;')
            self.live_title.setText('WAITING FOR BOTTLE' if self.running else 'INSPECTION IDLE')
            self.live_detail.setText('Place a bottle in the camera view' if self.running else 'Start live inspection')
            self.live_evidence.setText('YOLOX-S bottle detection + exposed drink color')
            self.live_route.setText('AWAITING')
            self.live_route.setStyleSheet('background:#243b61;color:#c8dcff;padding:9px 12px;border-radius:8px;font-weight:700;')
            return
        # Show the bottle nearest the decision line when several are visible.
        width = self.last_packet['frame'].shape[1] if self.last_packet else WIDTH
        target = self.settings['line'] * width
        track = min(fresh, key=lambda item: abs((item.bbox[0]+item.bbox[2])/2-target))
        meta = self.track_meta.get(track.id,{})
        color = str(meta.get('color','unknown')).lower()
        support = max(0.0,min(1.0,float(meta.get('color_confidence',0))))
        self.show_live_color(color,support)
        self.live_title.setText(f'LIVE BOTTLE  #{track.id:03d}')
        label = 'label visible' if meta.get('gatorade_label_match') else 'label not confirmed'
        self.live_evidence.setText(f'{label}  •  {track.hits} camera frame(s) tracked')
        passing = color == self.settings['pass_color']
        self.live_route.setText('PREDICTED 0 · PASS' if passing else 'PREDICTED 1 · DIVERT')
        tone = '#174b3f' if passing else '#633942'
        ink = '#75f0c7' if passing else '#ffc3cc'
        self.live_route.setStyleSheet(f'background:{tone};color:{ink};padding:9px 12px;border-radius:8px;font-weight:700;')

    def show_live_color(self,color,support):
        palette = {'blue':('#1d5db7','#e6f0ff'),'yellow':('#f4c841','#242424'),
                   'white':('#f0f2f5','#242424')}
        background, foreground = palette.get(color,('#43546a','#f2f4f7'))
        self.live_swatch.setText(color[:1].upper() if color in palette else '?')
        self.live_swatch.setStyleSheet(f'background:{background};color:{foreground};border-radius:10px;font-size:25px;font-weight:800;')
        evidence_name = 'color support' if self.settings['yolox_mode']=='gatorade' else 'color confidence'
        self.live_detail.setText(f'{color.upper()}  •  {support:.0%} {evidence_name}' if color!='unknown' else 'COLOR UNCERTAIN')

    def show_barcode(self,tid,meta):
        self.barcode_title.setText('LAST BARCODE  •  SYNTHETIC DEMO DATA' if self.settings['source']=='simulation' else 'LAST BARCODE  •  LIVE DECODE')
        self.barcode_text.setText(str(meta.get('barcode','UNREAD')))
        self.barcode_info.setText(f"Bottle #{tid:03d}  •  {meta.get('color','unknown').upper()}  •  {meta.get('format','')}")

    def scanner_read(self):
        code=self.scanner_input.text().strip()
        self.scanner_input.clear()
        if not code: return
        self.barcode_title.setText('LAST BARCODE  •  USB SCANNER INPUT')
        self.barcode_text.setText(code)
        self.barcode_info.setText('Scanner text received • independent scan; bottle association not assigned')
        path=self.root/'data'/f'scanner-{datetime.now():%Y%m%d}.csv'
        try:
            exists=path.exists()
            with path.open('a',newline='',encoding='utf-8') as file:
                writer=csv.writer(file)
                if not exists: writer.writerow(['time','barcode','source'])
                # Preserve text when this log is opened as a spreadsheet.
                safe="'"+code if code.startswith(('=','+','-','@')) else code
                writer.writerow([datetime.now().astimezone().isoformat(timespec='milliseconds'),safe,'usb_scanner'])
        except OSError as exc:
            self.set_status('Scanner log could not be written: '+str(exc),'#fb8b94')

    def decision(self,decision):
        meta = self.track_meta.get(decision.id,{'color':'unknown','barcode':'UNREAD','format':''})
        self.show_barcode(decision.id,meta)
        if decision.bad: self.divert_count+=1
        else: self.pass_count+=1
        if self.settings['source']=='simulation':
            output = 'SIMULATED' if decision.bad else 'PASS'
        elif not self.armed:
            output = 'DISARMED'
        else:
            output = 'PENDING' if decision.bad else 'PASS'
        event = {'time':datetime.now().astimezone().isoformat(timespec='milliseconds'),'session':self.session,
                 'event_id':f'{self.session}-{self.generation}-{decision.id}',
                 'bottle_id':decision.id,'color':meta['color'],'decision':1 if decision.bad else 0,
                 'gatorade_label_match':bool(meta.get('gatorade_label_match',False)),
                 'barcode':meta.get('barcode','UNREAD'),'barcode_format':meta.get('format',''),
                 'source':self.settings['source'],'output':output,
                 'detail':'; '.join(decision.reasons),'request_id':'','run_id':''}
        self.events.append(event)
        if decision.bad and self.settings['source']=='simulation':
            self.sim.eject(decision.bbox); event['output']='SIMULATED'
        elif self.armed and self.settings['source'] in ('usb','basler'):
            recipe=diverter.plan(self.settings,decision.bad,decision.captured)
            event['_plan']=recipe
            event['_send_deadline']=min(recipe['due_at']+.25,recipe['arrival_at']-self.settings['move_ms']/1000)
            event['program_id']=recipe['program_id']; event['return_program_id']=recipe['return_program_id']
            event['cycles']=recipe['repeats']; event['cycles_completed']=0
            event['output']='SCHEDULED' if recipe['program_id'] else 'PASS CHECK'
            event['request_id']=f'ualr-{event["event_id"]}' if recipe['program_id'] else ''
            heapq.heappush(self.pending,(recipe['due_at'],decision.id,event))
        self.add_row(event)
        self.save_events()
        self.refresh_counts()

    def add_row(self,event):
        self.table.insertRow(0)
        values=[event['time'][11:19]+f"  #{event['bottle_id']:03d}",event['color'].upper(),f"{event['decision']} · {'DIVERT' if event['decision'] else 'PASS'}",event['barcode'],event['output'],event['detail']]
        for i,text in enumerate(values):
            item=QTableWidgetItem(str(text)); item.setData(Qt.ItemDataRole.UserRole,event['event_id'])
            if i==2: item.setForeground(QColor('#fb8b94' if event['decision'] else '#54dfbb'))
            self.table.setItem(0,i,item)
        if self.table.rowCount()>100: self.table.removeRow(100)

    def refresh_event(self,event):
        for row in range(self.table.rowCount()):
            if self.table.item(row,0).data(Qt.ItemDataRole.UserRole)==event['event_id']:
                self.table.item(row,4).setText(event['output'])
                self.table.item(row,5).setText(event['detail'])
                break
        self.save_events()

    def dispatch_due(self,now):
        if not self.pending or self.pending[0][0]>now: return
        due,tid,event=heapq.heappop(self.pending)
        if not self.armed:
            event['output']='CANCELLED'; self.refresh_event(event); return
        if now-due>.25 or (event['_plan']['program_id'] and now>event['_send_deadline']):
            event['output']='MISSED TIMING'; self.refresh_event(event); self.fail('Divert event arrived late; inspection stopped.'); return
        if self.output_busy or self.owns_motion:
            event['output']='REJECTOR BUSY'; self.refresh_event(event); self.fail('Diverter sequence overlaps the next bottle. Output disarmed; stop the conveyor using its hardware controls. Increase bottle spacing.'); return
        recipe=event['_plan']
        if not recipe['program_id']:
            self.pass_clearance_until=max(self.pass_clearance_until,recipe['clearance_at'])
            event['output']='PASS'; self.refresh_event(event); return
        if now<self.pass_clearance_until:
            event['output']='SPACING CONFLICT'; self.refresh_event(event); self.fail('A passing bottle has not cleared the diverter. Output disarmed; stop the conveyor using its hardware controls.'); return
        self.owns_motion=self.output_busy=True
        self.active_event=event; self.active_run=None
        self.sequence_plan=recipe; self.sequence_cycle=1; self.sequence_stage='primary'
        self.start_sequence_program(recipe['program_id'],event['_send_deadline'])

    def start_sequence_program(self, program, deadline=None):
        event=self.active_event
        self.active_program=program
        self.phase_generation+=1; phase=self.phase_generation
        self.sequence_wait_until=None; self.sequence_next=None
        self.active_run=None
        self.previous_run=None
        self.request_pending=True
        self.output_started=time.monotonic()
        client=self.client; generation=self.generation; send_gate=self.send_gate
        request_id=event['request_id']
        if self.sequence_cycle!=1 or self.sequence_stage!='primary':
            request_id+=f'-c{self.sequence_cycle}-{self.sequence_stage}'
        event['output']='REQUESTING'; self.refresh_event(event)
        # Capture the pre-run identifier so an old completed run cannot be counted.
        def send():
            if not send_gate.is_set():
                raise RuntimeError('Divert cancelled before the motion request.')
            before=client.program_status(program)
            result=client.trigger(program,request_id,allow_send=send_gate.is_set,deadline=deadline)
            return {'response':result,'before':before.get('run_id')}
        def accepted(result,error):
            if self.active_event is not event or phase!=self.phase_generation: return
            self.request_pending=False
            if error:
                event['output']='UNCERTAIN' if getattr(error,'uncertain',False) else 'REFUSED'
                event['detail']+='; '+str(error); self.refresh_event(event)
                self.fail('EtherMotion: '+str(error)); return
            self.previous_run=result['before']
            event['output']='ACCEPTED'; self.refresh_event(event)
            self.motion_label.setText(f"Bottle #{event['bottle_id']}: {self.sequence_stage}, cycle {self.sequence_cycle}/{self.sequence_plan['repeats']} accepted; waiting for completion.")
            if generation!=self.generation or not self.armed:
                self.request_motion_stop()
        self.jobs.submit(send,accepted)

    def sequence_program_completed(self, now):
        recipe=self.sequence_plan
        if self.sequence_stage=='primary' and recipe['return_program_id']:
            self.sequence_next='return'
            self.sequence_wait_until=max(now+recipe['hold_seconds'],recipe['clearance_at'])
        else:
            self.active_event['cycles_completed']=self.sequence_cycle
            self.sequence_next='repeat' if self.sequence_cycle<recipe['repeats'] else 'complete'
            # A complete saved cycle owns its physical dwell. This reservation
            # still prevents another bottle's action before tail clearance.
            self.sequence_wait_until=max(recipe['clearance_at'],now+(recipe['hold_seconds'] if self.sequence_next=='repeat' else 0))
        self.active_event['output']='HOLD / CLEARANCE'
        self.refresh_event(self.active_event)
        self.motion_label.setText(f"Bottle #{self.active_event['bottle_id']}: waiting for hold / bottle clearance before {self.sequence_next}.")
        self.resume_sequence(now)

    def resume_sequence(self, now):
        if self.sequence_wait_until is None or now<self.sequence_wait_until: return
        if not self.running or not self.armed or not self.send_gate.is_set(): return
        action=self.sequence_next
        self.sequence_wait_until=None; self.sequence_next=None
        if action=='return':
            self.sequence_stage='return'
            self.start_sequence_program(self.sequence_plan['return_program_id'])
        elif action=='repeat':
            self.sequence_cycle+=1; self.sequence_stage='primary'
            self.start_sequence_program(self.sequence_plan['program_id'])
        else:
            event=self.active_event; event['output']='COMPLETED'; self.complete_count+=1
            self.owns_motion=self.output_busy=False
            self.motion_label.setText(f"Bottle #{event['bottle_id']}: {self.sequence_cycle} diverter cycle(s) completed; bottle clearance time reached.")
            self.refresh_event(event); self.refresh_counts(); self.update_enabled()

    def discover(self):
        if self.owns_motion or self.armed: return
        try:
            url=self.fields['base_url'].text().strip()
            client=EtherMotionClient(url)
        except Exception as exc:
            self.connection_note.setText(str(exc)); return
        self.connect_button.setEnabled(False); self.connection_note.setText('Reading EtherMotion configuration…')
        def done(state,error):
            self.connect_button.setEnabled(True)
            if error:
                self.client=None; self.connection_note.setText(str(error)); self.update_enabled(); return
            self.client=client
            programs=client.list_once_programs(state)
            for widget,key,empty in ((self.program,'program_id','Select REJECT program…'),
                                     (self.pass_program,'pass_program_id','Let pass / no movement'),
                                     (self.return_program,'return_program_id','Return included in main cycle')):
                widget.clear(); widget.addItem(empty,'')
                for program in programs: widget.addItem(program['name'],program['id'])
                index=widget.findData(self.settings.get(key,''))
                if index>=0: widget.setCurrentIndex(index)
            self.connection_note.setText(f"Connected • {len(programs)} Once program(s)." if programs else 'Connected. Save a divert cycle with Repeat = Once in EtherMotion, then discover again.')
            self.settings['base_url']=url
            self.update_enabled()
        self.jobs.submit(client.discover,done)

    def toggle_arm(self,checked):
        if not checked:
            self.set_disarmed()
            for _,_,event in self.pending: event['output']='CANCELLED'; self.refresh_event(event)
            self.pending.clear(); self.request_motion_stop(); self.update_enabled(); return
        if self.confidence_timer.isActive() or (self.last_packet or {}).get('confidence_revision',0)<self.expected_confidence_revision:
            self.set_disarmed(); self.output_note.setText('Wait for a fresh inspection using the selected confidence thresholds.'); return
        if (not self.running or self.settings['source'] not in ('usb','basler') or not self.last_packet
                or time.monotonic()-self.last_packet['captured']>.85 or not self.last_packet.get('inspection_ready',True)):
            self.set_disarmed(); self.output_note.setText('Start a fresh live camera before enabling output.'); return
        if self.owns_motion:
            self.set_disarmed(); self.output_note.setText('Wait for the current diverter sequence to stop.'); return
        program=self.program.currentData()
        if not self.client or not program:
            self.set_disarmed(); return
        self.settings['program_id']=program
        self.settings['pass_program_id']=self.pass_program.currentData() or ''
        self.settings['return_program_id']=self.return_program.currentData() or ''
        try: diverter.validate_timing(self.settings)
        except ValueError as exc:
            self.set_disarmed(); self.output_note.setText(str(exc)); return
        store.save(self.root,self.settings)
        generation=self.generation
        self.arm_generation+=1; arm_generation=self.arm_generation
        self.arming=True; self.update_enabled()
        self.output_note.setText('Checking Once cycle and every drive…')
        def done(result,error):
            if generation!=self.generation or arm_generation!=self.arm_generation or not self.arming: return
            self.arming=False
            if error:
                self.set_disarmed(); self.output_note.setText(str(error))
            else:
                self.armed=True
                self.send_gate=threading.Event(); self.send_gate.set()
                self.output_note.setText('LIVE OUTPUT ENABLED • PASS / REJECT actions and bottle-clearance checks active. Conveyor remains hardware controlled.')
                self.badge.setText('LIVE CAMERA • DIVERT ENABLED')
            self.update_enabled()
        programs=sorted({p for p in (program,self.settings['pass_program_id'],self.settings['return_program_id']) if p})
        client=self.client
        self.jobs.submit(lambda:[client.check_ready(p) for p in programs],done)

    def poll_motion(self):
        if self.active_event is None or getattr(self,'request_pending',False): return
        if self.sequence_wait_until is not None and not self.stopping_motion: return
        if self.stopping_motion and not self.stop_acknowledged: return
        self.network_poll=True; self.last_poll=time.monotonic()
        event=self.active_event; program=self.active_program; client=self.client; phase=self.phase_generation
        def done(status,error):
            if not self.owns_motion or self.active_event is not event or phase!=self.phase_generation: return
            self.network_poll=False
            # A poll queued before Stop describes the pre-stop operation. Only
            # status received after acknowledgement can release Stop ownership.
            if self.stopping_motion and not self.stop_acknowledged: return
            if error:
                if self.stopping_motion:
                    self.output_busy=False
                    self.motion_label.setText('Stop status could not be confirmed: '+str(error)+'. Use EtherMotion and retry Stop + disarm.'); return
                self.fail('Motion status unavailable: '+str(error)); return
            if self.stopping_motion:
                if (not status.get('running') and status.get('status') in ('stopped','completed','idle')
                        and not status.get('error') and not status.get('stop_errors')):
                    self.owns_motion=self.output_busy=self.stopping_motion=False
                    self.sequence_wait_until=None; self.sequence_next=None
                    self.motion_label.setText('EtherMotion cycle stopped. Re-enable Ethernet triggers there before the next run.')
                    self.update_enabled()
                elif not status.get('running') and status.get('status') not in ('running','stopping'):
                    self.output_busy=False
                    self.motion_label.setText('EtherMotion could not confirm the stop: '+str(status.get('error') or status.get('stop_errors') or status.get('status'))+'. Review the mechanism in EtherMotion and retry Stop + disarm.')
                    self.update_enabled()
                elif time.monotonic()-self.stop_started>10:
                    self.output_busy=False
                    self.motion_label.setText('Cycle has not stopped after 10 seconds. Use EtherMotion and retry Stop + disarm.')
                return
            run_id=status.get('run_id')
            if status.get('repeat_mode','once')!='once':
                self.fail('EtherMotion repeat mode changed. Stopping the selected cycle.'); return
            if not run_id or run_id==self.previous_run:
                if time.monotonic()-self.output_started>2:
                    self.fail('No new EtherMotion run was confirmed after acceptance.')
                return
            if self.active_run is None:
                self.active_run=run_id
                event['run_id']=' | '.join(filter(None,(event['run_id'],str(run_id))))
            if run_id!=self.active_run:
                self.fail('EtherMotion run changed unexpectedly. Inspection stopped.'); return
            if status.get('status')=='completed' and not status.get('running'):
                self.sequence_program_completed(time.monotonic())
            elif status.get('error') or status.get('status') in ('failed','error','stopped','cancelled'):
                event['output']='FAILED'; event['detail']+='; '+str(status.get('error') or status.get('status'))
                self.refresh_event(event); self.fail('Divert motion did not complete: '+str(status.get('error') or status.get('status')))
            elif time.monotonic()-self.output_started>20:
                self.fail('Divert motion exceeded 20 seconds. Inspection stopped.')
        self.jobs.submit(lambda:client.program_status(program),done)

    def request_motion_stop(self):
        if not self.owns_motion or not self.client or (self.stopping_motion and self.output_busy): return
        self.stopping_motion=True
        self.stop_acknowledged=False
        self.stop_started=time.monotonic()
        client=self.client; program=self.active_program or self.settings['program_id']; event=self.active_event
        def done(result,error):
            if error:
                self.motion_label.setText('Stop could not be confirmed: '+str(error)+'. Use the EtherMotion stop control.')
                # Retain motion ownership so a new run cannot start on unknown state.
                self.output_busy=False
            else:
                self.stop_acknowledged=True; self.output_busy=True
                self.motion_label.setText('EtherMotion stop acknowledged; waiting for the cycle to stop.')
            if event:
                event['output']='STOP UNCERTAIN' if error else 'STOP REQUESTED'; self.refresh_event(event)
            self.update_enabled()
        self.jobs.submit(lambda:client.stop(program,'ualr-stop-'+uuid.uuid4().hex),done)

    def launch_ethermotion(self):
        original=Path(self.settings['ethermotion_path'])
        executable=original if original.is_file() else self.root/'EtherMotion'/'EtherMotion.exe'
        if not executable.is_file():
            self.connection_note.setText('EtherMotion.exe was not found. Open your EtherMotion folder manually.'); return
        try:
            # User clicked Open EtherMotion. Default workspace/server only; launching never triggers a move.
            subprocess.Popen([str(executable)],cwd=str(executable.parent),creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
            self.connection_note.setText('EtherMotion opened. Set its divert cycle to Once, then discover.')
        except OSError as exc: self.connection_note.setText(str(exc))

    def log(self,text):
        logging.info(text)

    def set_status(self,text,color):
        self.status.setText(text); self.status.setStyleSheet('color:'+color)

    def refresh_counts(self):
        self.stats['total'].setText(str(self.pass_count+self.divert_count))
        self.stats['pass'].setText(str(self.pass_count)); self.stats['divert'].setText(str(self.divert_count))
        self.stats['output'].setText(str(self.complete_count))

    def reset_counts(self):
        if self.running: return
        self.pass_count=self.divert_count=self.complete_count=0
        self.table.setRowCount(0); self.events.clear(); self.session=uuid.uuid4().hex[:12]
        self.refresh_counts()

    def write_csv(self,path):
        fields=['time','session','event_id','bottle_id','color','decision','gatorade_label_match','barcode','barcode_format','source','output','detail','request_id','run_id','program_id','return_program_id','cycles','cycles_completed']
        with Path(path).open('w',newline='',encoding='utf-8-sig') as file:
            writer=csv.DictWriter(file,fieldnames=fields); writer.writeheader()
            writer.writerows({key:event.get(key,'') for key in fields} for event in self.events)

    def save_events(self):
        try: self.write_csv(self.root/'data'/f'session-{self.session}.csv')
        except OSError as exc: self.set_status('Log write failed: '+str(exc),'#fb8b94')

    def export(self):
        path,_=QFileDialog.getSaveFileName(self,'Export bottle decisions',str(self.root/f'UALR-bottles-{datetime.now():%Y%m%d-%H%M%S}.csv'),'CSV (*.csv)')
        if path:
            try: self.write_csv(path); self.set_status('Exported '+path,'#54dfbb')
            except OSError as exc: self.set_status(str(exc),'#fb8b94')

    def finish_smoke_test(self):
        self.grab().save(str(self.root/'data'/'demo-preview.png'))
        report={'pass':self.pass_count,'divert':self.divert_count,'events':len(self.events),
                'hardware_commands':0,'has_barcode':any(e['barcode']!='UNREAD' for e in self.events),
                'duplicate_decisions':len(self.events)-len({e['event_id'] for e in self.events})}
        (self.root/'data'/'smoke-test.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
        self.close()

    def closeEvent(self,event):
        self.stop()
        if self.owns_motion:
            event.ignore(); self.set_status('Waiting for EtherMotion stop acknowledgement; close again after it finishes.','#f3b252'); return
        if self.worker and self.worker.isRunning():
            if not self.worker.wait(1200):
                event.ignore(); self.set_status('Camera is releasing; close again in a moment.','#f3b252'); return
        self.timer.stop()
        if self.fullscreen is not None: self.fullscreen.close()
        self.jobs.closed=True
        self.jobs.pool.shutdown(wait=False,cancel_futures=True)
        event.accept()
