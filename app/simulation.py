"""Deterministic conveyor imagery and ground truth, with no hardware calls."""
from __future__ import annotations

import math

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QLinearGradient, QPainter, QPainterPath, QPen

WIDTH, HEIGHT = 1200, 600


class Simulation:
    def __init__(self):
        self.bottles = []
        self.elapsed = 0.0
        self.sequence = 0
        self.until_next = .15
        self.next_bad = False

    def update(self, dt, settings):
        self.elapsed += dt
        speed = settings['belt_speed'] * WIDTH / settings['field_width']
        rtl = settings['direction'] == 'rtl'
        self.until_next -= dt
        if self.until_next <= 0:
            self.sequence += 1
            kind = ('blue', 'yellow', 'white', 'orange', 'green', 'red', 'purple', 'clear')[((self.sequence-1) % 8)]
            if self.next_bad:
                kind, self.next_bad = ('blue' if settings['pass_color'] != 'blue' else 'red'), False
            self.bottles.append({'x': 1260.0 if rtl else -60.0, 'kind': kind, 'seq': self.sequence, 'ejected': False})
            self.until_next = max(1.25, 230.0 / max(speed, 1))
        boxes, reasons = [], []
        for bottle in self.bottles:
            bottle['x'] += speed * dt * (-1 if rtl else 1)
            x = bottle['x']
            if 44 <= x <= WIDTH - 44 and not bottle['ejected']:
                boxes.append((max(0,x-44), 160, min(WIDTH,x+44), 418))
                rule = settings['rule']
                bad = []
                if rule == 'color' and bottle['kind'] != settings['pass_color']:
                    bad = [f"Color: {bottle['kind']} (divert)"]
                elif rule == 'all':
                    bad = ['Reject all bottles']
                elif rule == 'every_n' and bottle['seq'] % settings['every_n'] == 0:
                    bad = [f"Every {settings['every_n']} bottles"]
                elif rule in ('cap', 'cap_label') and bottle['kind'] == 'cap':
                    bad = ['Missing cap']
                elif rule == 'cap_label' and bottle['kind'] == 'label':
                    bad = ['Missing label']
                reasons.append(bad)
        self.bottles = [b for b in self.bottles if -180 < b['x'] < WIDTH + 180]
        return boxes, reasons

    def eject(self, bbox):
        cx = (bbox[0] + bbox[2]) / 2
        if self.bottles:
            bottle = min(self.bottles, key=lambda b: abs(b['x'] - cx))
            if abs(bottle['x'] - cx) < 90:
                bottle['ejected'] = True
                bottle['eject_time'] = self.elapsed

    def draw(self, painter: QPainter, settings):
        p = painter
        gradient = QLinearGradient(0, 0, 0, HEIGHT)
        gradient.setColorAt(0, QColor('#0d1727'))
        gradient.setColorAt(1, QColor('#172940'))
        p.fillRect(QRectF(0, 0, WIDTH, HEIGHT), gradient)
        p.setPen(QColor('#9aacbf'))
        p.setFont(QFont('Segoe UI', 12, QFont.Weight.DemiBold))
        p.drawText(QRectF(28, 24, 1000, 30), 'SIMULATED VISION  /  GATOR BOTTLE LINE')
        p.setFont(QFont('Segoe UI', 10))
        p.setPen(QColor('#657d98'))
        p.drawText(QRectF(28, 57, 1080, 26), 'Synthetic bottles and inspection results • Hardware output stays disabled')
        # Conveyor, rollers and moving slats.
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor('#304359'))
        p.drawRoundedRect(QRectF(0, 402, WIDTH, 92), 22, 22)
        p.setBrush(QColor('#182634'))
        p.drawRoundedRect(QRectF(10, 415, WIDTH-20, 57), 20, 20)
        p.setPen(QPen(QColor('#3b5061'), 2))
        offset = (self.elapsed * settings['belt_speed'] * WIDTH / settings['field_width']) % 42
        if settings['direction'] == 'rtl':
            offset = -offset
        for i in range(-2, 31):
            x = i * 42 + offset
            p.drawLine(QPointF(x, 419), QPointF(x-18, 469))
        p.setBrush(QColor('#53667a'))
        p.setPen(QPen(QColor('#101b29'), 3))
        for x in range(35, WIDTH, 65):
            p.drawEllipse(QPointF(x, 489), 13, 13)
        p.setPen(QPen(QColor('#40536b'), 12))
        p.drawLine(140, 501, 120, 572)
        p.drawLine(1060, 501, 1080, 572)
        for b in self.bottles:
            y = 0
            opacity = 1.0
            if b['ejected']:
                age = self.elapsed - b['eject_time']
                y = min(210, age * 470)
                opacity = max(0, 1-age*2)
            if opacity <= 0:
                continue
            p.save()
            p.setOpacity(opacity)
            self._bottle(p, b['x'], 160+y, b['kind'])
            p.restore()
        line = WIDTH * (1-settings['line'] if settings['direction'] == 'rtl' else settings['line'])
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor('#f3b252'))
        p.drawRoundedRect(QRectF(line-14, 113, 28, 35), 6, 6)
        p.setBrush(QColor('#a4b2c4'))
        p.drawRoundedRect(QRectF(line-30, 503, 60, 21), 5, 5)
        p.setPen(QColor('#9aacbf'))
        p.setFont(QFont('Segoe UI', 11))
        direction = '←' if settings['direction'] == 'rtl' else '→'
        p.drawText(QRectF(380, 536, 500, 30), f"BELT {direction}  {settings['belt_speed']:.0f} mm/s")

    @staticmethod
    def _bottle(p, x, y, kind):
        p.setPen(QPen(QColor('#a4d2df'), 2))
        liquid = QLinearGradient(x-43, 0, x+43, 0)
        liquid.setColorAt(0, QColor('#b4dae4'))
        liquid.setColorAt(.18, QColor('#e2f3ee'))
        palettes = {'orange': ('#ffac37','#e77826'), 'blue': ('#4dd7fb','#2184b8'),
                    'green': ('#b1e84a','#4a9c35'), 'red': ('#ff7881','#c53c57'),
                    'yellow': ('#ffe866','#dbb235'), 'purple': ('#b88aff','#7d4cba'),
                    'white': ('#f7f8f4','#c7d2d9'),
                    'clear': ('#e7f5f8','#acc8d0')}
        light, dark = palettes.get(kind, palettes['orange'])
        liquid.setColorAt(.30, QColor(light))
        liquid.setColorAt(.80, QColor(dark))
        liquid.setColorAt(1, QColor('#d0e5df'))
        p.setBrush(liquid)
        path = QPainterPath()
        path.moveTo(x-20, y+16)
        path.lineTo(x+20, y+16)
        path.lineTo(x+22, y+48)
        path.cubicTo(x+22, y+62, x+43, y+63, x+43, y+90)
        path.lineTo(x+43, y+238)
        path.quadTo(x+43, y+255, x+28, y+257)
        path.lineTo(x-28, y+257)
        path.quadTo(x-43, y+255, x-43, y+238)
        path.lineTo(x-43, y+90)
        path.cubicTo(x-43, y+63, x-22, y+62, x-22, y+48)
        path.closeSubpath()
        p.drawPath(path)
        p.setPen(QPen(QColor('#b9cfbc'), 2))
        for yy in (91, 98, 105, 220, 228, 236):
            p.drawLine(QPointF(x-39, y+yy), QPointF(x+39, y+yy))
        if kind != 'cap':
            p.setPen(QPen(QColor('#e5722e'), 2))
            p.setBrush(QColor('#ff8c36'))
            p.drawRoundedRect(QRectF(x-25, y, 50, 30), 5, 5)
            p.setPen(QPen(QColor('#ffc67b'), 1))
            for xx in range(-20, 24, 6):
                p.drawLine(QPointF(x+xx, y+5), QPointF(x+xx, y+25))
        if kind != 'label':
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor('#eaf1e6'))
            p.drawRoundedRect(QRectF(x-43, y+123, 86, 83), 3, 3)
            p.setBrush(QColor('#154749'))
            p.drawRect(QRectF(x-43, y+173, 86, 24))
            p.setPen(QColor('#193a3b'))
            p.setFont(QFont('Segoe UI', 40, QFont.Weight.Black))
            p.drawText(QRectF(x-35, y+113, 70, 65), Qt.AlignmentFlag.AlignCenter, 'G')
            p.setFont(QFont('Segoe UI', 8, QFont.Weight.Bold))
            p.setPen(QColor('#f9f3d9'))
            p.drawText(QRectF(x-42, y+174, 84, 20), Qt.AlignmentFlag.AlignCenter, 'DEMO')
