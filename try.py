import sys
from PyQt5 import QtWidgets
from PyQt5.QtWidgets import QLabel, QMainWindow, QWidget, QVBoxLayout
from PyQt5.QtGui import QPixmap, QPainter, QPen, QColor, QFont
from PyQt5.QtSvg import QSvgRenderer
from PyQt5.QtCore import Qt, QRectF, QPointF

import matplotlib.pyplot as plt
from matplotlib.offsetbox import OffsetImage, AnnotationBbox


class HandLabel(QLabel):
    """
    Label大小变化 → 自动重绘图像（SVG + 红圈），保持比例
    """
    def __init__(self, svg_path, points_svg_coords, parent=None):
        super().__init__(parent)
        self.svg_path = svg_path
        self.points_svg_coords = points_svg_coords

        # 获取 SVG 原始大小
        self.renderer = QSvgRenderer(svg_path)
        size = self.renderer.defaultSize()
        self.svg_w = size.width()
        self.svg_h = size.height()

        # 允许 QLabel 自动缩放（关键）
        self.setScaledContents(False)
        self.setAlignment(Qt.AlignCenter)
        self.setMinimumSize(20, 20)

    def resizeEvent(self, event):
        """窗口变化 → 自动重绘 pixmap"""
        self.update_pixmap()
        super().resizeEvent(event)

    def update_pixmap(self):
        w = max(1, self.width())
        h = max(1, self.height())

        # 生成白色背景 pixmap
        pixmap = QPixmap(w, h)
        pixmap.fill(Qt.white)

        painter = QPainter(pixmap)

        # 保持比例：计算统一缩放因子
        scale = min(w / self.svg_w, h / self.svg_h)
        draw_w = self.svg_w * scale
        draw_h = self.svg_h * scale

        # 居中显示
        offset_x = (w - draw_w) / 2
        offset_y = (h - draw_h) / 2

        # 绘制 SVG
        target_rect = QRectF(offset_x, offset_y, draw_w, draw_h)
        self.renderer.render(painter, target_rect)

        # 红圈画笔
        pen = QPen(QColor(255, 0, 0))
        pen.setWidth(int(3 * scale))
        painter.setPen(pen)

        # 字体
        font = QFont()
        font.setPointSize(int(8 * scale + 4))
        painter.setFont(font)

        radius = 20 * scale

        # 绘制点（使用 SVG 原始坐标 → 缩放）
        for sx, sy, text in self.points_svg_coords:
            x = offset_x + sx * scale
            y = offset_y + sy * scale

            painter.drawEllipse(QPointF(x, y), radius, radius)
            painter.drawText(QPointF(x + radius + 4, y + 4), text)

        painter.end()
        self.setPixmap(pixmap)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        central = QWidget()
        layout = QVBoxLayout(central)

        svg_path = "utils/hand.svg"

        # SVG 原始坐标（和 hand.svg 原大小一致）
        points = [
            (237, 344, "MCP-T"),
            (190, 257, "MCP-I"),
            (122, 251, "MCP-M"),
            (72, 271, "MCP-R"),
            (24, 297, "MCP-S"),

            (212, 146, "PIP-I"),
            (132, 123, "PIP-M"),
            (76, 149, "PIP-R"),
            (19, 201, "PIP-S"),

            (129, 531, "RS"),
            (154, 484, "STT"),
            (128, 489, "WS-3"),
            (62, 440, "WS-4"),
            (87, 437, "WS-5"),
            (111, 436, "WS-5"),
        ]

        self.hand_label = HandLabel(svg_path, points)
        layout.addWidget(self.hand_label)

        self.setCentralWidget(central)
        self.setWindowTitle("Auto Resize Hand Viewer")
        self.resize(600, 600)


if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    win = MainWindow()
    win.show()
    sys.exit(app.exec_())
