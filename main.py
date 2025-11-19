import os
import sys

from PyQt5 import QtWidgets, QtCore, QtGui, QtSvg
from PyQt5.QtCore import Qt, QRectF, QPointF
from PyQt5.QtGui import QPixmap, QPainter, QPen, QColor, QFont

from ui_GUI import Ui_RAScorer
from functools import partial

import vtkmodules.all as vtk
from vtkmodules.qt.QVTKRenderWindowInteractor import QVTKRenderWindowInteractor
from scorer import Scorer
import random
import datetime


class MainWindow(QtWidgets.QMainWindow, Ui_RAScorer):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setupUi(self)

        self.scorer = Scorer(score_type='svdh')
        self.case_path = ''

        # 当前高亮的关节 index（JSN/BE 共用）
        self.current_highlight_idx = None
        # 当前选择的关节 index（用于在两个 tab 间同步 RB 状态，如需要可进一步利用）
        self.current_joint_idx = None

        # ================== VTK 嵌入到 GL_Xray ==================
        self.vtkWidget = QVTKRenderWindowInteractor(self.GL_Xray)
        layout = QtWidgets.QVBoxLayout(self.GL_Xray)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.vtkWidget)

        self.renderer = vtk.vtkRenderer()
        self.vtkWidget.GetRenderWindow().AddRenderer(self.renderer)
        self.interactor = self.vtkWidget.GetRenderWindow().GetInteractor()

        style = vtk.vtkInteractorStyleImage()
        self.interactor.SetInteractorStyle(style)
        self.interactor.Initialize()

        # ================== Hand SVG 显示相关 ==================
        # 两个 label 都设成可伸缩
        for lb in (self.LB_HandModel_JSN, self.LB_HandModel_BE):
            sp = lb.sizePolicy()
            sp.setHorizontalPolicy(QtWidgets.QSizePolicy.Expanding)
            sp.setVerticalPolicy(QtWidgets.QSizePolicy.Expanding)
            lb.setSizePolicy(sp)
            lb.setMinimumSize(20, 20)
            lb.setAlignment(Qt.AlignCenter)

        self.hand_svg_renderer = None
        self.hand_svg_w = 300
        self.hand_svg_h = 300

        # ===== JSN 标注点 =====
        self.jsn_label_dict = [
            {'Name': 'MCP-T', 'RB': self.RB_JSN_1, 'CB': self.CB_JSN_1, 'Point': (237, 344), 'Score_L': None, 'Score_R': None},
            {'Name': 'MCP-I', 'RB': self.RB_JSN_2, 'CB': self.CB_JSN_2, 'Point': (190, 257), 'Score_L': None, 'Score_R': None},
            {'Name': 'MCP-M', 'RB': self.RB_JSN_3, 'CB': self.CB_JSN_3, 'Point': (122, 251), 'Score_L': None, 'Score_R': None},
            {'Name': 'MCP-R', 'RB': self.RB_JSN_4, 'CB': self.CB_JSN_4, 'Point': (72, 271), 'Score_L': None, 'Score_R': None},
            {'Name': 'MCP-S', 'RB': self.RB_JSN_5, 'CB': self.CB_JSN_5, 'Point': (24, 297), 'Score_L': None, 'Score_R': None},

            {'Name': 'PIP-I', 'RB': self.RB_JSN_6, 'CB': self.CB_JSN_6, 'Point': (212, 146), 'Score_L': None, 'Score_R': None},
            {'Name': 'PIP-M', 'RB': self.RB_JSN_7, 'CB': self.CB_JSN_7, 'Point': (132, 123), 'Score_L': None, 'Score_R': None},
            {'Name': 'PIP-R', 'RB': self.RB_JSN_8, 'CB': self.CB_JSN_8, 'Point': (76, 149), 'Score_L': None, 'Score_R': None},
            {'Name': 'PIP-S', 'RB': self.RB_JSN_9, 'CB': self.CB_JSN_9, 'Point': (19, 201), 'Score_L': None, 'Score_R': None},

            {'Name': 'CMC-M', 'RB': self.RB_JSN_10, 'CB': self.CB_JSN_10, 'Point': (129, 531), 'Score_L': None, 'Score_R': None},
            {'Name': 'CMC-R', 'RB': self.RB_JSN_11, 'CB': self.CB_JSN_11, 'Point': (154, 484), 'Score_L': None, 'Score_R': None},
            {'Name': 'CMC-S', 'RB': self.RB_JSN_12, 'CB': self.CB_JSN_12, 'Point': (128, 489), 'Score_L': None, 'Score_R': None},
            {'Name': 'S-TmTd', 'RB': self.RB_JSN_13, 'CB': self.CB_JSN_13, 'Point': (62, 440), 'Score_L': None, 'Score_R': None},
            {'Name': 'S-C', 'RB': self.RB_JSN_14, 'CB': self.CB_JSN_14, 'Point': (87, 437), 'Score_L': None, 'Score_R': None},
            {'Name': 'S-Ra', 'RB': self.RB_JSN_15, 'CB': self.CB_JSN_15, 'Point': (111, 436), 'Score_L': None, 'Score_R': None},
        ]

        # ===== BE 标注点 =====
        self.be_label_dict = [
            {'Name': 'MCP-T', 'RB': self.RB_BE_1, 'CB': self.CB_BE_1, 'Point': (237, 344), 'Score_L': None, 'Score_R': None},
            {'Name': 'MCP-I', 'RB': self.RB_BE_2, 'CB': self.CB_BE_2, 'Point': (190, 257), 'Score_L': None, 'Score_R': None},
            {'Name': 'MCP-M', 'RB': self.RB_BE_3, 'CB': self.CB_BE_3, 'Point': (122, 251), 'Score_L': None, 'Score_R': None},
            {'Name': 'MCP-R', 'RB': self.RB_BE_4, 'CB': self.CB_BE_4, 'Point': (72, 271), 'Score_L': None, 'Score_R': None},
            {'Name': 'MCP-S', 'RB': self.RB_BE_5, 'CB': self.CB_BE_5, 'Point': (24, 297), 'Score_L': None, 'Score_R': None},

            {'Name': 'IP', 'RB': self.RB_BE_6, 'CB': self.CB_BE_6, 'Point': (252, 263), 'Score_L': None, 'Score_R': None},
            {'Name': 'PIP-I', 'RB': self.RB_BE_7, 'CB': self.CB_BE_7, 'Point': (212, 146), 'Score_L': None, 'Score_R': None},
            {'Name': 'PIP-M', 'RB': self.RB_BE_8, 'CB': self.CB_BE_8, 'Point': (132, 123), 'Score_L': None, 'Score_R': None},
            {'Name': 'PIP-R', 'RB': self.RB_BE_9, 'CB': self.CB_BE_9, 'Point': (76, 149), 'Score_L': None, 'Score_R': None},
            {'Name': 'PIP-S', 'RB': self.RB_BE_10, 'CB': self.CB_BE_10, 'Point': (19, 201), 'Score_L': None, 'Score_R': None},

            {'Name': 'CMC-T', 'RB': self.RB_BE_11, 'CB': self.CB_BE_11, 'Point': (199, 450), 'Score_L': None, 'Score_R': None},
            {'Name': 'Tm', 'RB': self.RB_BE_12, 'CB': self.CB_BE_12, 'Point': (179, 476), 'Score_L': None, 'Score_R': None},
            {'Name': 'S', 'RB': self.RB_BE_13, 'CB': self.CB_BE_13, 'Point': (134, 507), 'Score_L': None, 'Score_R': None},
            {'Name': 'L', 'RB': self.RB_BE_14, 'CB': self.CB_BE_14, 'Point': (84, 514), 'Score_L': None, 'Score_R': None},
            {'Name': 'Ul', 'RB': self.RB_BE_15, 'CB': self.CB_BE_15, 'Point': (30, 529), 'Score_L': None, 'Score_R': None},
            {'Name': 'Ra', 'RB': self.RB_BE_16, 'CB': self.CB_BE_16, 'Point': (106, 546), 'Score_L': None, 'Score_R': None},
        ]

        # ===== Reviewed 按钮 =====
        self.PB_Reviewed.clicked.connect(self.on_reviewed_clicked)

        # ===== 当前使用哪个 hand model、哪个 label =====
        # 默认：tab 0 = JSN
        self.current_LorR = 'L'
        self.current_hand_model = self.jsn_label_dict
        self.current_hand_label = self.LB_HandModel_JSN

        # 安装事件过滤器
        self.LB_HandModel_BE.installEventFilter(self)
        self.LB_HandModel_JSN.installEventFilter(self)

        # 加载 SVG
        self.load_hand(self.current_hand_model, target_label=self.current_hand_label)

        # ================== 绑定信号 ==================
        self.action_Input.triggered.connect(self.select_input_folder)
        self.action_Save.triggered.connect(self.save_scores_to_json)
        self.action_Open.triggered.connect(self.load_scores_from_json)
        self.action_Output.triggered.connect(self.export_scores_to_excel)

        self.LW_Files.currentRowChanged.connect(self.on_file_selected)

        # JSN CB / RB
        for idx, item in enumerate(self.jsn_label_dict):
            item['CB'].setCurrentIndex(-1)
            item['CB'].currentIndexChanged.connect(
                lambda _, name=idx: self.change_score(name)
            )
            item['RB'].toggled.connect(
                lambda checked, name=idx: self.select_joint(name) if checked else None
            )

        # BE CB / RB（用同样的槽函数）
        for idx, item in enumerate(self.be_label_dict):
            item['CB'].setCurrentIndex(-1)
            item['CB'].currentIndexChanged.connect(
                lambda _, name=idx: self.change_score(name)
            )
            item['RB'].toggled.connect(
                lambda checked, name=idx: self.select_joint(name) if checked else None
            )

        # 左右手切换（JSN + BE 共用逻辑）
        self.RB_Left_JSN.toggled.connect(lambda checked, name='L': self.LorR_change(name) if checked else None)
        self.RB_Right_JSN.toggled.connect(lambda checked, name='R': self.LorR_change(name) if checked else None)
        self.RB_Left_BE.toggled.connect(lambda checked, name='L': self.LorR_change(name) if checked else None)
        self.RB_Right_BE.toggled.connect(lambda checked, name='R': self.LorR_change(name) if checked else None)

        # ======== tabWidget 切换 JSN / BE ========
        self.tabWidget.currentChanged.connect(self.on_tab_changed)
        self.tabWidget.setEnabled(False)

        # 初始化默认 Radio 状态
        self.sync_lr_radio_buttons()

    # --------- 通用刷新函数 ---------
    def sync_lr_radio_buttons(self):
        """
        同步 JSN / BE 两个 tab 的左右手单选按钮，使其与 self.current_LorR 一致。
        """
        # 避免递归触发 LorR_change
        for rb in (self.RB_Left_JSN, self.RB_Right_JSN, self.RB_Left_BE, self.RB_Right_BE):
            rb.blockSignals(True)

        if self.current_LorR == 'L':
            self.RB_Left_JSN.setChecked(True)
            self.RB_Left_BE.setChecked(True)
            self.RB_Right_JSN.setChecked(False)
            self.RB_Right_BE.setChecked(False)
        else:
            self.RB_Right_JSN.setChecked(True)
            self.RB_Right_BE.setChecked(True)
            self.RB_Left_JSN.setChecked(False)
            self.RB_Left_BE.setChecked(False)

        for rb in (self.RB_Left_JSN, self.RB_Right_JSN, self.RB_Left_BE, self.RB_Right_BE):
            rb.blockSignals(False)

    def refresh_current_view(self):
        """
        根据 current_hand_model / current_LorR 刷新：
        - combobox 显示
        - 手图显示（包括高亮）
        """
        hand_model = self.current_hand_model
        LorR = self.current_LorR

        for item in hand_model:
            cb = item['CB']
            score = item[f'Score_{LorR}']

            cb.blockSignals(True)
            if score is None or score == '':
                cb.setCurrentIndex(-1)
            else:
                cb.setCurrentText(str(score))
            cb.blockSignals(False)

        self.update_hand(hand_model,
                         highlight_idx=self.current_highlight_idx,
                         LorR=LorR,
                         target_label=self.current_hand_label)

    # ================== scorer 相关 ==================
    def load_score(self):
        """
        从 self.scorer 中读取当前 case_path 左右手的分数到 jsn_label_dict / be_label_dict，
        然后刷新当前视图。
        """
        result_L = self.scorer.find_row(self.case_path, LorR='L')[0]
        result_R = self.scorer.find_row(self.case_path, LorR='R')[0]

        for item in self.jsn_label_dict:
            score_key = 'JSN_' + item['Name'].replace('-', '_')
            item['Score_L'] = result_L[score_key]
            item['Score_R'] = result_R[score_key]

        for item in self.be_label_dict:
            score_key = 'BE_' + item['Name'].replace('-', '_')
            item['Score_L'] = result_L[score_key]
            item['Score_R'] = result_R[score_key]

        # 默认切到左手
        self.current_LorR = 'L'
        self.sync_lr_radio_buttons()
        self.refresh_current_view()

    def write_to_scorer(self):
        """
        将 jsn_label_dict / be_label_dict 中的 Score_L 或 Score_R
        按顺序写入 scorer（顺序必须与 SVDH_TEMPLATE 一致）
        """
        for LorR in ['L', 'R']:
            score_key = "Score_L" if LorR == "L" else "Score_R"

            jsn_scores = [item[score_key] for item in self.jsn_label_dict]
            be_scores = [item[score_key] for item in self.be_label_dict]

            final_scores = jsn_scores + be_scores
            self.scorer.update_score(self.case_path, LorR, *final_scores)

    # ===== tab 切换回调 =====
    def on_tab_changed(self, index: int):
        """
        index == 0: JSN tab
        index == 1: BE tab
        """
        if index == 0:
            self.switch_to_jsn_view()
        elif index == 1:
            self.switch_to_be_view()

    def switch_to_jsn_view(self):
        """切换为 JSN 视图"""
        self.current_hand_model = self.jsn_label_dict
        self.current_hand_label = self.LB_HandModel_JSN
        self.sync_lr_radio_buttons()
        self.refresh_current_view()

    def switch_to_be_view(self):
        """切换为 BE 视图"""
        self.current_hand_model = self.be_label_dict
        self.current_hand_label = self.LB_HandModel_BE
        self.sync_lr_radio_buttons()
        self.refresh_current_view()

    def LorR_change(self, LorR):
        """
        左右手切换时调用：
        - 更新 current_LorR
        - 同步两个 tab 的 Radio Button
        - 刷新当前 tab 的 combobox + 手图
        """
        self.current_LorR = LorR
        self.sync_lr_radio_buttons()
        self.refresh_current_view()

    def select_joint(self, idx):
        """
        选择具体关节（Radio Button 触发），用于高亮。
        JSN / BE 共用一个 current_highlight_idx。
        """
        self.current_joint_idx = idx
        self.current_highlight_idx = idx
        self.refresh_current_view()

    def change_score(self, idx):
        """
        combobox 改变时更新 Score_L / Score_R，然后刷新显示。
        """
        obj = self.sender()
        self.current_hand_model[idx][f'Score_{self.current_LorR}'] = obj.currentText()
        self.current_highlight_idx = idx
        self.refresh_current_view()

    # ========= 事件过滤器 =========
    def eventFilter(self, obj, event):
        if event.type() == QtCore.QEvent.Resize and obj in (self.LB_HandModel_JSN, self.LB_HandModel_BE):
            # 谁在当前 Tab（也就是可见），谁 resize 就在谁上重画
            self.current_hand_label = obj
            self.update_hand(self.current_hand_model,
                             highlight_idx=self.current_highlight_idx,
                             LorR=self.current_LorR,
                             target_label=obj)
        return super().eventFilter(obj, event)

    # ========= 加载 SVG =========
    def load_hand(self, hand_points, target_label=None):
        base_dir = os.path.dirname(os.path.abspath(__file__))
        svg_path = os.path.join(base_dir, "utils", "hand.svg")

        renderer = QtSvg.QSvgRenderer(svg_path)
        label = target_label or self.current_hand_label or self.LB_HandModel_JSN

        if not renderer.isValid():
            label.setText("Invalid SVG: utils/hand.svg")
            self.hand_svg_renderer = None
            return

        self.hand_svg_renderer = renderer
        size = renderer.defaultSize()
        self.hand_svg_w = size.width() if size.width() > 0 else 300
        self.hand_svg_h = size.height() if size.height() > 0 else 300

        self.update_hand(hand_points, highlight_idx=None, LorR='L', target_label=label)

    def update_hand(self, hand_points, highlight_idx=None, LorR='L', target_label=None):
        if self.hand_svg_renderer is None:
            return

        label = target_label or self.current_hand_label or self.LB_HandModel_JSN

        label_size = label.size()
        w = label_size.width()
        h = label_size.height()
        if w <= 0 or h <= 0:
            return

        pixmap = QPixmap(w, h)
        pixmap.fill(Qt.white)

        painter = QPainter(pixmap)

        scale = min(w / self.hand_svg_w, h / self.hand_svg_h)
        draw_w = self.hand_svg_w * scale
        draw_h = self.hand_svg_h * scale

        offset_x = (w - draw_w) / 2
        offset_y = (h - draw_h) / 2

        target_rect = QRectF(offset_x, offset_y, draw_w, draw_h)

        if LorR.upper() == 'R':
            painter.save()
            painter.translate(w, 0)
            painter.scale(-1, 1)
            self.hand_svg_renderer.render(painter, target_rect)
            painter.restore()
        else:
            self.hand_svg_renderer.render(painter, target_rect)

        # ====== 这里根据 JSN / BE 选择圆圈颜色 ======
        if label is self.LB_HandModel_JSN:
            base_color = QColor(0, 200, 0)  # 绿色
        elif label is self.LB_HandModel_BE:
            base_color = QColor(0, 0, 220)  # 蓝色
        else:
            base_color = QColor(255, 0, 0)  # fallback：红色

        base_font = QFont()
        base_font.setPointSize(max(6, int(8 * scale + 4)))
        radius = 20 * scale

        for idx, item in enumerate(hand_points):
            sx, sy = item['Point']
            score_text = str(item[f'Score_{LorR}'])

            if LorR.upper() == 'R':
                sx_flipped = self.hand_svg_w - sx
                sx_draw = offset_x + sx_flipped * scale
            else:
                sx_draw = offset_x + sx * scale
            sy_draw = offset_y + sy * scale

            is_highlight = (highlight_idx is not None and idx == highlight_idx)

            # ===== 画圆圈（根据 base_color）=====
            if is_highlight:
                pen_circle = QPen(base_color)
                pen_circle.setWidth(max(5, int(3 * scale)))
                painter.setPen(pen_circle)
                highlight_brush = QColor(base_color.red(),
                                         base_color.green(),
                                         base_color.blue(), 100)
                painter.setBrush(highlight_brush)
            else:
                pen_circle = QPen(base_color)
                pen_circle.setWidth(max(3, int(2 * scale)))
                painter.setPen(pen_circle)
                painter.setBrush(Qt.NoBrush)

            painter.drawEllipse(QPointF(sx_draw, sy_draw), radius, radius)

            # --- 文字（上方 + 白底 + 黑字） ---
            font = QFont(base_font)
            if is_highlight:
                font.setBold(True)
            painter.setFont(font)

            painter.setPen(Qt.black)
            fm = painter.fontMetrics()
            text_w = fm.horizontalAdvance(score_text)
            text_h = fm.height()

            text_x = sx_draw - text_w / 2
            text_y = sy_draw - radius - 6 * scale

            bg_rect = QRectF(text_x - 4, text_y - text_h + 4,
                             text_w + 8, text_h)
            painter.fillRect(bg_rect, Qt.white)
            painter.drawText(QPointF(text_x, text_y), score_text)

        painter.end()

        label.setPixmap(pixmap)
        label.setAlignment(Qt.AlignCenter)

    # ========= X-ray 相关 =========
    def select_input_folder(self):
        folder = QtWidgets.QFileDialog.getExistingDirectory(
            self,
            "Select X-ray Folder",
            ""
        )
        if not folder:
            return

        exts = {".dcm", ".bmp"}
        filepaths = []
        for name in sorted(os.listdir(folder)):
            full_path = os.path.join(folder, name)
            if not os.path.isfile(full_path):
                continue
            if os.path.splitext(name)[1].lower() in exts:
                filepaths.append(full_path)

        if not filepaths:
            QtWidgets.QMessageBox.information(
                self,
                "No Images",
                "选中的文件夹中没有 .dcm 或 .bmp 图像。"
            )
            return

        self.LW_Files.clear()
        self.show_xray_vtk(filepaths[0])

        for path in filepaths:
            item = QtWidgets.QListWidgetItem(path)
            item.setData(QtCore.Qt.UserRole, path)
            self.LW_Files.addItem(item)

        self.LW_Files.setCurrentRow(0)

    def on_file_selected(self, row: int):
        if row < 0:
            return
        item = self.LW_Files.item(row)
        if item is None:
            return
        path = item.data(QtCore.Qt.UserRole) or item.text()
        if path and os.path.exists(path):
            self.write_to_scorer()
            self.show_xray_vtk(path)
            self.load_score()
            self.update_reviewed_label()

    def show_xray_vtk(self, filepath: str):
        self.case_path = filepath
        if not os.path.exists(filepath):
            QtWidgets.QMessageBox.warning(self, "Error", f"File not found:\n{filepath}")
            return

        ext = os.path.splitext(filepath)[1].lower()

        if ext == ".dcm":
            reader = vtk.vtkDICOMImageReader()
            case_id = str(random.randint(10000, 99999))
            case_name = os.path.basename(self.case_path)[:-4]
            detectiontime = 'unknown'
            reader.SetFileName(filepath)
        elif ext == ".bmp":
            reader = vtk.vtkBMPReader()
            case_id = str(random.randint(10000, 99999))
            case_name = os.path.basename(self.case_path)[:-4]
            detectiontime = 'unknown'
            reader.SetFileName(filepath)
        else:
            QtWidgets.QMessageBox.warning(
                self,
                "Unsupported",
                "当前示例只支持 .dcm（DICOM） 和 .bmp 文件。",
            )
            return

        reader.Update()
        image_data = reader.GetOutput()
        min_val, max_val = image_data.GetScalarRange()

        window = max_val - min_val
        if window <= 0:
            window = 1.0
        level = (max_val + min_val) / 2.0

        window_level = vtk.vtkImageMapToWindowLevelColors()
        window_level.SetInputData(image_data)
        window_level.SetWindow(window)
        window_level.SetLevel(level)
        window_level.Update()

        image_actor = vtk.vtkImageActor()
        image_actor.GetMapper().SetInputConnection(window_level.GetOutputPort())

        self.renderer.RemoveAllViewProps()
        self.renderer.AddActor(image_actor)

        camera = self.renderer.GetActiveCamera()
        camera.ParallelProjectionOn()
        self.renderer.ResetCamera()

        extent = image_data.GetExtent()
        spacing = image_data.GetSpacing()
        img_w = (extent[1] - extent[0] + 1) * spacing[0]
        img_h = (extent[3] - extent[2] + 1) * spacing[1]

        if img_w > 0 and img_h > 0:
            rw = max(self.vtkWidget.width(), 1)
            rh = max(self.vtkWidget.height(), 1)

            view_aspect = rw / rh
            img_aspect = img_w / img_h

            if view_aspect > img_aspect:
                scale = img_h / 2.0
            else:
                scale = img_w / (2.0 * view_aspect)

            camera.SetParallelScale(scale)

        self.renderer.ResetCameraClippingRange()
        self.vtkWidget.GetRenderWindow().Render()


        # ================== scorer 初始化 ==================
        if self.case_path not in self.scorer.get_case_path_list():
            svdh_scores = [None for _ in range(31)]
            self.scorer.new_info(self.case_path,
                                 case_id,
                                 case_name,
                                 detectiontime, 'L',
                                 *svdh_scores)
            self.scorer.new_info(self.case_path,
                                 case_id,
                                 case_name,
                                 detectiontime, 'R',
                                 *svdh_scores)

        self.tabWidget.setEnabled(True)

    def open_xray_file(self):
        fname, _ = QtWidgets.QFileDialog.getOpenFileName(
            self,
            "Open X-ray",
            "",
            "DICOM (*.dcm);;Bitmap (*.bmp);;All Files (*)"
        )
        if fname:
            self.show_xray_vtk(fname)

    # ========= 分数的保存 / 读取 / 导出 =========
    def save_scores_to_json(self):
        """
        将当前 self.scorer 中的打分结果保存为 JSON 文件
        """
        self.write_to_scorer()

        default_name = datetime.datetime.now().strftime("%Y%m%d_%H%M%S.json")
        default_path = f'RAScorer_{default_name}'

        path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self,
            "保存打分为 JSON",
            default_path,
            "JSON 文件 (*.json);;所有文件 (*)"
        )
        if not path:
            return

        try:
            self.scorer.save(path)
            QtWidgets.QMessageBox.information(
                self,
                "保存成功",
                f"打分结果已保存到：\n{path}"
            )
        except Exception as e:
            QtWidgets.QMessageBox.critical(
                self,
                "保存失败",
                f"保存 JSON 失败：\n{e}"
            )

    def load_scores_from_json(self):
        """
        从 JSON 文件中读取打分结果并替换当前 self.scorer
        """
        path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self,
            "打开打分 JSON",
            "",
            "JSON 文件 (*.json);;所有文件 (*)"
        )
        if not path:
            return

        try:
            new_scorer = Scorer.load(path)
            self.scorer = new_scorer

            # 使用 recent_path 作为当前 case
            self.case_path = getattr(self.scorer, "recent_path", "")

            self.LW_Files.clear()
            current_row = 0
            for cp in self.scorer.get_case_path_list():
                item = QtWidgets.QListWidgetItem(cp)
                item.setData(QtCore.Qt.UserRole, cp)
                self.LW_Files.addItem(item)
                if cp == self.case_path:
                    current_row = self.LW_Files.count() - 1

            if self.LW_Files.count() > 0:
                self.LW_Files.setCurrentRow(current_row)

            QtWidgets.QMessageBox.information(
                self,
                "读取成功",
                f"已从 JSON 载入打分结果：\n{path}"
            )

        except Exception as e:
            QtWidgets.QMessageBox.critical(
                self,
                "读取失败",
                f"读取 JSON 失败：\n{e}"
            )

    def export_scores_to_excel(self):
        """
        将当前 self.scorer 中的打分结果导出为 Excel（.xlsx）
        """

        default_name = datetime.datetime.now().strftime("%Y%m%d_%H%M%S.xlsx")
        default_path = f'RAScorer_{default_name}'

        path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self,
            "导出打分为 Excel",
            default_path,
            "Excel 文件 (*.xlsx);;所有文件 (*)"
        )
        if not path:
            return

        if not path.lower().endswith(".xlsx"):
            path += ".xlsx"

        try:
            self.scorer.output(path)
            QtWidgets.QMessageBox.information(
                self,
                "导出成功",
                f"打分结果已导出到：\n{path}"
            )
        except Exception as e:
            QtWidgets.QMessageBox.critical(
                self,
                "导出失败",
                f"导出 Excel 失败：\n{e}"
            )

    def update_reviewed_label(self, reviewed=None):
        """
        根据 reviewed 状态更新 LB_Reviewed 的样式：
        - True: 红色 + 加粗
        - False: 灰色 + 普通
        如果 reviewed 为 None，则根据当前 case_path 去 scorer 里查询。
        """
        if reviewed is None:
            if not self.case_path:
                reviewed = False
            else:
                reviewed = self.scorer.get_case_reviewed_status(self.case_path)

        font = self.LB_Reviewed.font()
        if reviewed:
            font.setBold(True)
            self.LB_Reviewed.setFont(font)
            self.LB_Reviewed.setStyleSheet("color: red;")
        else:
            font.setBold(False)
            self.LB_Reviewed.setFont(font)
            self.LB_Reviewed.setStyleSheet("color: gray;")

    def on_reviewed_clicked(self):
        """
        点击 PB_Reviewed 时：
        1. 切换当前 case_path 的全部 reviewed 字段
        2. 更新 LB_Reviewed 的显示（红色加粗 / 灰色普通）
        """
        if not self.case_path:
            return

        new_status = self.scorer.toggle_reviewed(self.case_path)
        self.update_reviewed_label(new_status)


if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())
