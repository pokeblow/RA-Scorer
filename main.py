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

JSN_POINT = {
    'MCP-T': (237, 344),
    'MCP-I': (190, 257),
    'MCP-M': (122, 251),
    'MCP-R': (72, 271),
    'MCP-S': (24, 297),

    'PIP-I': (212, 146),
    'PIP-M': (132, 123),
    'PIP-R': (76, 149),
    'PIP-S': (19, 201),

    'CMC-M': (129, 531),
    'CMC-R': (154, 484),
    'CMC-S': (128, 489),
    'STT': (62, 440),
    'SC': (87, 437),
    'SR': (111, 436),
}

BE_POINT = {
    'MCP-T': (237, 344),
    'MCP-I': (190, 257),
    'MCP-M': (122, 251),
    'MCP-R': (72, 271),
    'MCP-S': (24, 297),

    'IP': (252, 263),
    'PIP-I': (212, 146),
    'PIP-M': (132, 123),
    'PIP-R': (76, 149),
    'PIP-S': (19, 201),

    'CMC-T': (199, 450),
    'Tm': (179, 476),
    'S': (134, 507),
    'L': (84, 514),
    'U': (30, 529),
    'R': (106, 546),
}


# ================== 独立 VTK 交互类 ==================
class XRayVTKViewer(QtWidgets.QWidget):
    """
    单独封装 VTK 显示逻辑的类：
    - 负责创建 QVTKRenderWindowInteractor
    - 设置 renderer / interactor style
    - 提供 show_xray(filepath) 接口
    """
    def __init__(self, parent=None):
        super().__init__(parent)

        # QVTK 组件
        self.vtkWidget = QVTKRenderWindowInteractor(self)
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.vtkWidget)

        # renderer / interactor
        self.renderer = vtk.vtkRenderer()
        self.vtkWidget.GetRenderWindow().AddRenderer(self.renderer)

        self.interactor = self.vtkWidget.GetRenderWindow().GetInteractor()
        style = vtk.vtkInteractorStyleImage()
        self.interactor.SetInteractorStyle(style)
        self.interactor.Initialize()

    def update_image(self, filepath: str) -> bool:
        """
        显示 X-ray 图像（DICOM 或 BMP）。
        只负责图像显示和相机设置，不处理 scorer 逻辑。
        返回：
            True  - 显示成功
            False - 文件不存在或格式不支持
        """
        if not os.path.exists(filepath):
            QtWidgets.QMessageBox.warning(self, "Error", f"File not found:\n{filepath}")
            return False

        ext = os.path.splitext(filepath)[1].lower()

        if ext == ".dcm":
            reader = vtk.vtkDICOMImageReader()
            reader.SetFileName(filepath)
        elif ext == ".bmp":
            reader = vtk.vtkBMPReader()
            reader.SetFileName(filepath)
        else:
            QtWidgets.QMessageBox.warning(
                self,
                "Unsupported",
                "当前示例只支持 .dcm（DICOM） 和 .bmp 文件。",
            )
            return False

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

        # 清空并添加新 actor
        self.renderer.RemoveAllViewProps()
        self.renderer.AddActor(image_actor)

        # 相机设置
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

        return True


class SvgScoreWidget(QtWidgets.QWidget):
    """
    在本控件中绘制 SVG，并在 SVG 上叠加若干个 QComboBox。
    - 背景为白色
    - SVG 等比例缩放并居中
    - 根据 jsn_points / be_points 自动生成 combobox
    - 根据 score_mode 切换显示 JSN / BE
    - 根据 LorR_mode 实现左右水平翻转（SVG + combobox 一起翻）
    """

    def __init__(self, svg_path: str,
                 jsn_points: dict,
                 be_points: dict,
                 parent=None):
        super().__init__(parent)

        # ------------ SVG 加载 ------------
        self.svg_renderer = QtSvg.QSvgRenderer(svg_path, self)
        if not self.svg_renderer.isValid():
            print(f"[Warning] SVG 文件加载失败: {svg_path}")

        self.svg_size = self.svg_renderer.defaultSize()
        self.svg_w = max(self.svg_size.width(), 1)
        self.svg_h = max(self.svg_size.height(), 1)

        # 当前模式：'JSN' 或 'BE'
        self.score_mode = "JSN"
        # 左右模式：'L' 或 'R'
        self.LorR_mode = "L"

        # 原始点位字典（用构造函数传进来的）
        self.point_dicts = {
            "JSN": jsn_points or {},
            "BE": be_points or {},
        }

        # combobox 字典：{'JSN': {name: {'rel_position': QPointF, 'CB': QComboBox, 'tmp_score': {'L':..,'R':..}}}}
        self.combos = {"JSN": {}, "BE": {}}

        # 计算相对坐标并创建所有 combobox
        self._init_combos()

    # ---------- 初始化所有 combobox ----------
    def _init_combos(self):
        # JSN combobox
        for name, (x, y) in self.point_dicts["JSN"].items():
            rx = x / self.svg_w
            ry = y / self.svg_h

            self.combos["JSN"][name] = {}
            self.combos["JSN"][name]["rel_position"] = QtCore.QPointF(rx, ry)

            cb = QtWidgets.QComboBox(self)
            cb.addItems(["0", "1", "2", "3", "4"])
            cb.setCurrentIndex(-1)  # 初始为空
            self.combos["JSN"][name]["CB"] = cb
            # 为左右两侧分别保存一个临时分数
            self.combos["JSN"][name]["tmp_score"] = {"L": None, "R": None}

            # combobox 改变时更新 tmp_score
            cb.currentIndexChanged.connect(
                lambda idx, m="JSN", k=name: self._on_cb_changed(m, k, idx)
            )

        # BE combobox
        for name, (x, y) in self.point_dicts["BE"].items():
            rx = x / self.svg_w
            ry = y / self.svg_h

            self.combos["BE"][name] = {}
            self.combos["BE"][name]["rel_position"] = QtCore.QPointF(rx, ry)

            cb = QtWidgets.QComboBox(self)
            cb.addItems(["0", "1", "2", "3", "5"])
            cb.setCurrentIndex(-1)
            self.combos["BE"][name]["CB"] = cb
            self.combos["BE"][name]["tmp_score"] = {"L": None, "R": None}

            cb.currentIndexChanged.connect(
                lambda idx, m="BE", k=name: self._on_cb_changed(m, k, idx)
            )

        # 初始布局一次
        self.update_combo_positions()

    # ---------- combobox 改变时，写回 tmp_score ----------
    def _on_cb_changed(self, mode: str, name: str, index: int):
        """
        combobox 值改变时，把当前侧(L/R)的值写入 tmp_score[side]
        """
        info = self.combos.get(mode, {}).get(name, None)
        if info is None:
            return
        cb = info.get("CB", None)
        if cb is None:
            return

        text = cb.currentText()
        side = self.LorR_mode  # 当前是 L 还是 R
        tmp = info.get("tmp_score", None)
        if isinstance(tmp, dict) and side in tmp:
            tmp[side] = text if text != "" else None

    # ---------- 将当前 combobox 的值保存到 tmp_score[side] ----------
    def _save_current_scores_to_tmp(self, side: str):
        """
        在切换 L/R 前调用，把当前侧的所有 combobox 值保存到 tmp_score[side]
        """
        for mode, m_dict in self.combos.items():
            for name, info in m_dict.items():
                cb = info.get("CB", None)
                tmp = info.get("tmp_score", None)
                if cb is None or not isinstance(tmp, dict) or side not in tmp:
                    continue
                text = cb.currentText()
                tmp[side] = text if text != "" else None

    # ---------- 从 tmp_score[side] 恢复 combobox ----------
    def _restore_scores_from_tmp(self, side: str):
        """
        在切换到新的 L/R 后调用，从 tmp_score[side] 恢复 combobox 的选择
        """
        for mode, m_dict in self.combos.items():
            for name, info in m_dict.items():
                cb = info.get("CB", None)
                tmp = info.get("tmp_score", None)
                if cb is None or not isinstance(tmp, dict) or side not in tmp:
                    continue

                text = tmp[side]
                if text is None:
                    cb.setCurrentIndex(-1)
                else:
                    idx = cb.findText(str(text))
                    if idx >= 0:
                        cb.setCurrentIndex(idx)
                    else:
                        # 找不到就设为空
                        cb.setCurrentIndex(-1)

    # ---------- 对外接口：切换 JSN / BE ----------
    def set_score_mode(self, mode: str):
        if mode not in ("JSN", "BE"):
            return
        if self.score_mode == mode:
            return
        self.score_mode = mode
        self.update_combo_positions()
        self.update()

    # ---------- 对外接口：切换 L / R ----------
    def set_LorR_mode(self, side: str):
        if side not in ("L", "R"):
            return
        if self.LorR_mode == side:
            return

        # 先把原来的侧保存到 tmp_score
        old_side = self.LorR_mode
        self._save_current_scores_to_tmp(old_side)

        # 切换侧
        self.LorR_mode = side

        # 用新侧的 tmp_score 恢复 combobox
        self._restore_scores_from_tmp(side)

        # 位置和重绘
        self.update_combo_positions()
        self.update()

    # ---------- sizeHint（可选） ----------
    def sizeHint(self):
        # 给一个适当的默认大小（用 SVG 尺寸）
        return self.svg_size

    # ---------- 绘制事件 ----------
    def paintEvent(self, event):
        super().paintEvent(event)
        if not self.svg_renderer or not self.svg_renderer.isValid():
            return

        painter = QPainter(self)

        # 背景白色
        painter.fillRect(self.rect(), Qt.white)

        w = self.width()
        h = self.height()
        if w <= 0 or h <= 0:
            return

        # 等比例缩放 + 居中
        scale = min(w / self.svg_w, h / self.svg_h)
        draw_w = self.svg_w * scale
        draw_h = self.svg_h * scale
        offset_x = (w - draw_w) / 2
        offset_y = (h - draw_h) / 2

        target_rect = QRectF(offset_x, offset_y, draw_w, draw_h)

        # 画 SVG（根据 L / R 决定是否水平翻转）
        cx = target_rect.center().x()

        painter.save()
        if self.LorR_mode == "R":
            # 围绕 target_rect 的中心竖直线做镜像：
            # M = T(cx,0) * S(-1,1) * T(-cx,0)
            painter.translate(cx, 0)
            painter.scale(-1, 1)
            painter.translate(-cx, 0)

        self.svg_renderer.render(painter, target_rect)
        painter.restore()

        # 再更新 combobox 位置（SVG 已经翻转，所以这里只需要用 rx / 1-rx）
        self.update_combo_positions(target_rect)

    # ---------- 更新 combobox 位置 ----------
    def update_combo_positions(self, target_rect: QRectF = None):
        # 没有 SVG 或大小异常时直接返回
        if not self.svg_renderer or not self.svg_renderer.isValid():
            return

        w = self.width()
        h = self.height()
        if target_rect is None:
            if w <= 0 or h <= 0 or self.svg_w <= 0 or self.svg_h <= 0:
                return
            scale = min(w / self.svg_w, h / self.svg_h)
            draw_w = self.svg_w * scale
            draw_h = self.svg_h * scale
            offset_x = (w - draw_w) / 2
            offset_y = (h - draw_h) / 2
            target_rect = QRectF(offset_x, offset_y, draw_w, draw_h)

        # 当前显示模式：'JSN' 或 'BE'
        mode = self.score_mode

        # 遍历两种模式，控制显隐 & 位置
        for m, m_dict in self.combos.items():
            visible = (m == mode)
            for name, info in m_dict.items():
                cb = info.get("CB", None)
                rel = info.get("rel_position", None)
                if cb is None or rel is None:
                    continue

                cb.setVisible(visible)
                if not visible:
                    # 不显示的就不用算位置了
                    continue

                # 根据左右模式决定是否水平翻转 combobox 位置
                if self.LorR_mode == "R":
                    rx = 1.0 - rel.x()
                else:
                    rx = rel.x()
                ry = rel.y()

                size = cb.sizeHint()
                x = target_rect.left() + rx * target_rect.width() - size.width() / 2
                y = target_rect.top() + ry * target_rect.height() - size.height() / 2

                cb.setGeometry(int(x), int(y), size.width(), size.height())


    # ---------- 窗口大小变化时也要更新 ----------
    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.update_combo_positions()

    # ---------- 导出当前所有分数状态（JSN+BE，L+R） ----------
    def get_score_state(self):
        """
        返回所有关节、所有模式(JSN/BE)、左右(L/R)的分数状态。

        结构:
        {
            'JSN': {
                'L': {'MCP-T': 0, 'MCP-I': 1, ...},
                'R': {'MCP-T': 2, 'MCP-I': 0, ...},
            },
            'BE': {
                'L': {...},
                'R': {...},
            }
        }
        分数为 int 或 None（未选择）
        """
        # 先把当前侧正在显示的 combobox 写回 tmp_score
        self._save_current_scores_to_tmp(self.LorR_mode)

        state = {
            "JSN": {"L": {}, "R": {}},
            "BE": {"L": {}, "R": {}}
        }

        for mode, m_dict in self.combos.items():
            if mode not in state:
                continue
            for name, info in m_dict.items():
                tmp = info.get("tmp_score", {})
                for side in ("L", "R"):
                    text = tmp.get(side, None)
                    if text is None or text == "":
                        value = None
                    else:
                        try:
                            value = int(text)
                        except ValueError:
                            value = None
                    state[mode][side][name] = value

        return state

    # ---------- 从 state 中恢复所有分数状态 ----------
    def set_score_state(self, state: dict):
        """
        从 state 中恢复所有关节的分数状态。
        state 结构与 get_score_state() 返回值相同。

        只写入 tmp_score，当前侧(L/R)会同步刷新 combobox。
        """
        if not isinstance(state, dict):
            return

        for mode, m_dict in self.combos.items():
            mode_state = state.get(mode, {})
            if not isinstance(mode_state, dict):
                continue
            for name, info in m_dict.items():
                tmp = info.get("tmp_score", None)
                if not isinstance(tmp, dict):
                    continue

                for side in ("L", "R"):
                    side_dict = mode_state.get(side, {})
                    if not isinstance(side_dict, dict):
                        continue

                    val = side_dict.get(name, None)
                    if val is None:
                        tmp[side] = None
                    else:
                        tmp[side] = str(val)

        # 更新当前侧的 combobox 显示
        self._restore_scores_from_tmp(self.LorR_mode)
        self.update_combo_positions()
        self.update()

class MyListWidget(QtWidgets.QListWidget):
    orderChanged = QtCore.pyqtSignal(list)  # 信号：顺序变化时发出 list

    def dropEvent(self, event):
        super().dropEvent(event)

        # 获取新顺序
        new_order = [self.item(i).text() for i in range(self.count())]
        self.orderChanged.emit(new_order)  # 发射信号


class MainWindow(QtWidgets.QMainWindow, Ui_RAScorer):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setupUi(self)

        self.scorer = Scorer()
        self.file_paths = []
        self.current_case = 0
        self.save_path = ''

        # ================== VTK 交互类 GL_Xray ==================
        self.xray_viewer = XRayVTKViewer(self.GL_Xray)
        layout = QtWidgets.QVBoxLayout(self.GL_Xray)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.xray_viewer)

        # ================== Score_Model 相关 ==================
        # 假设 SVG 文件叫 hand.svg，和 main.py 在同一目录
        svg_path = os.path.join(os.path.dirname(__file__), "utils/hand.svg")  # 换成你的 svg 文件名
        self.svg_widget = SvgScoreWidget(
            svg_path=svg_path,
            jsn_points=JSN_POINT,
            be_points=BE_POINT,
            parent=self.Score_Model
        )

        score_layout = QtWidgets.QVBoxLayout(self.Score_Model)
        score_layout.setContentsMargins(0, 0, 0, 0)
        score_layout.addWidget(self.svg_widget)

        for rb in (self.RB_JSN, self.RB_BE, self.RB_L, self.RB_R):
            rb.setAutoExclusive(False)

        # 评分模式组：JSN / BE
        self.group_score_mode = QtWidgets.QButtonGroup(self)
        self.group_score_mode.setExclusive(True)
        self.group_score_mode.addButton(self.RB_JSN)
        self.group_score_mode.addButton(self.RB_BE)

        # 左右手组：L / R
        self.group_lr_mode = QtWidgets.QButtonGroup(self)
        self.group_lr_mode.setExclusive(True)
        self.group_lr_mode.addButton(self.RB_L)
        self.group_lr_mode.addButton(self.RB_R)

        # 默认选中一个组合：比如 JSN + L
        self.RB_JSN.setChecked(True)
        self.RB_L.setChecked(True)

        # JSN / BE 切换
        self.RB_JSN.toggled.connect(
            lambda checked: checked and self.score_mode_changed("JSN")
        )
        self.RB_BE.toggled.connect(
            lambda checked: checked and self.score_mode_changed("BE")
        )

        # L / R 切换
        self.RB_L.toggled.connect(
            lambda checked: checked and self.svg_widget.set_LorR_mode("L")
        )
        self.RB_R.toggled.connect(
            lambda checked: checked and self.svg_widget.set_LorR_mode("R")
        )

        # ================== 菜单槽函数 ==================
        self.action_Input.triggered.connect(self._action_input)
        self.action_Save.triggered.connect(self._save_json)
        self.action_Open.triggered.connect(self._load_json)
        self.action_Output.triggered.connect(self._export_excel)


        self.LW_Files.currentRowChanged.connect(self._file_changed)
        # self.LW_Files.itemClicked.connect(self._write_to_scorer)
        self.PB_All_Neg.clicked.connect(self._set_all_neg)
        self.PB_All_Pos.clicked.connect(self._set_all_pos)
        self.PB_Set.clicked.connect(self._set_score_from_order)

        self.PB_Reviewed.clicked.connect(self.set_reviewed)
        self.LB_Reviewed.setStyleSheet("color: gray; font-weight: normal;")
        self.current_reviewed = False


        old_widget = self.LW_Score_Order
        parent = old_widget.parent()

        # 创建新的自定义 ListWidget
        self.LW_Score_Order_new = MyListWidget(parent)
        self.verticalLayout_4.replaceWidget(old_widget, self.LW_Score_Order_new)
        old_widget.deleteLater()

        self.LW_Score_Order_new.setDragDropMode(QtWidgets.QAbstractItemView.InternalMove)
        self.LW_Score_Order_new.setDefaultDropAction(QtCore.Qt.MoveAction)

        self.LW_Score_Order_new.orderChanged.connect(self.on_list_order_changed)

        self.order_list = {'JSN': JSN_POINT.keys(), 'BE': BE_POINT.keys()}

        self.score_mode_changed('JSN')

        self.set_enable(False)

    def set_enable(self, state=False):
        self.LW_Score_Order_new.setEnabled(state)
        self.PB_All_Pos.setEnabled(state)
        self.PB_All_Neg.setEnabled(state)
        self.PTE_Load.setEnabled(state)
        self.PB_Set.setEnabled(state)

        self.RB_L.setEnabled(state)
        self.RB_R.setEnabled(state)
        self.RB_JSN.setEnabled(state)
        self.RB_BE.setEnabled(state)

        self.Score_Model.setEnabled(state)

    def update_reviewed(self):
        current_path = self.file_paths[self.current_case]
        reviewed_state = self.scorer.get_reviewed(current_path)

        if reviewed_state:
            # 红色 + 加粗
            self.LB_Reviewed.setStyleSheet("color: red; font-weight: bold;")
        else:
            # 灰色 + 不加粗
            self.LB_Reviewed.setStyleSheet("color: gray; font-weight: normal;")


    def set_reviewed(self):
        current_path = self.file_paths[self.current_case]
        reviewed_state = self.scorer.get_reviewed(current_path)
        self.scorer.set_reviewed(current_path, state=not reviewed_state)

        self.update_reviewed()



    def _set_score_from_order(self):
        current_path = self.file_paths[self.current_case]
        content = self.PTE_Load.toPlainText()
        score_mode = self._current_score_mode()
        LorR_mode = self._current_LorR_mode()

        tmp_dict = {}

        content = list(content)
        for idx, key in enumerate(self.order_list[score_mode]):
            if (idx + 1) <= len(content):
                tmp_dict[key] = content[idx]
            else:
                tmp_dict[key] = '0'

        print(tmp_dict)

        JSN_L, BE_L = self.scorer.get_info(case_path=current_path, LorR='L')
        JSN_R, BE_R = self.scorer.get_info(case_path=current_path, LorR='R')

        mapping = {'JSN_L': JSN_L, 'JSN_R': JSN_R, 'BE_L': BE_L, 'BE_R': BE_R}

        mapping[f'{score_mode}_{LorR_mode}'] = tmp_dict

        dict_tmp = {'JSN': {'L': mapping['JSN_L'], 'R': mapping['JSN_R']},
                    'BE': {'L': mapping['BE_L'], 'R': mapping['BE_R']}}

        self.scorer.update_info(case_path=current_path, LorR='L', JSN_dict=dict_tmp['JSN']['L'],
                                BE_dict=dict_tmp['BE']['L'])
        self.scorer.update_info(case_path=current_path, LorR='R', JSN_dict=dict_tmp['JSN']['R'],
                                BE_dict=dict_tmp['BE']['R'])

        self._load_scorer()

        self.PTE_Load.clear()

    def on_list_order_changed(self):
        order_list = []
        for i in range(self.LW_Score_Order_new.count()):
            item = self.LW_Score_Order_new.item(i)
            order_list.append(item.text())
        if self.RB_JSN.isChecked():
            self.order_list['JSN'] = order_list
        if self.RB_BE.isChecked():
            self.order_list['BE'] = order_list
    def score_mode_changed(self, value):
        self.svg_widget.set_score_mode(value)
        if self.RB_JSN.isChecked():
            self.LW_Score_Order_new.clear()
            for order in self.order_list['JSN']:
                self.LW_Score_Order_new.addItem(order)
        if self.RB_BE.isChecked():
            self.LW_Score_Order_new.clear()
            for order in self.order_list['BE']:
                self.LW_Score_Order_new.addItem(order)

    def _save_json(self):
        """
        将当前 self.scorer 中的打分结果保存为 JSON 文件
        """
        self._write_scorer()
        if self.save_path == '':
            default_name = datetime.datetime.now().strftime("%Y%m%d_%H%M%S.json")
            default_path = f'RAScorer_{default_name}'
        else:
            default_path = self.save_path

        path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self,
            "保存打分为 JSON",
            default_path,
            "JSON 文件 (*.json);;所有文件 (*)"
        )
        if not path:
            return

        try:
            self.scorer.save_to_json(path)
            self.statusbar.showMessage(
                f"JSON file saved to {path}"
            )
        except Exception as e:
            QtWidgets.QMessageBox.warning(
                self,
                "Failed",
                f"Save JSON Failed：\n{e}"
            )

    def _current_score_mode(self):
        if self.RB_JSN.isChecked():
            return "JSN"
        elif self.RB_BE.isChecked():
            return "BE"
        return None

    def _current_LorR_mode(self):
        if self.RB_L.isChecked():
            return "L"
        elif self.RB_R.isChecked():
            return "R"
        return None

    def _set_all_pos(self):
        score_type = self._current_score_mode()
        side = self._current_LorR_mode()
        state_tmp = self.svg_widget.get_score_state()
        for key in state_tmp[score_type][side]:
            state_tmp[score_type][side][key] = 0

        self.svg_widget.set_score_state(state_tmp)

    def _set_all_neg(self):
        score_type = self._current_score_mode()
        if score_type == 'JSN':
            value = 4
        else:
            value = 5
        side = self._current_LorR_mode()
        state_tmp = self.svg_widget.get_score_state()
        for key in state_tmp[score_type][side]:
            state_tmp[score_type][side][key] = value

        self.svg_widget.set_score_state(state_tmp)

    def _write_scorer(self):
        current_path = self.file_paths[self.current_case]
        repo_file_list = self.scorer.get_file_list()
        if (repo_file_list == None) or (current_path not in repo_file_list):
            self.scorer.new_info(case_path=current_path,
                                 case_id=f'{os.path.basename(current_path)[:-4]}',
                                 case_name=f'{os.path.basename(current_path)[:-4]}',
                                 LorR='L'
                                 )
            self.scorer.new_info(case_path=current_path,
                                 case_id=f'{os.path.basename(current_path)[:-4]}',
                                 case_name=f'{os.path.basename(current_path)[:-4]}',
                                 LorR='R'
                                 )
        else:
            state_tmp = self.svg_widget.get_score_state()

            self.scorer.update_info(case_path=current_path, LorR='L', JSN_dict=state_tmp['JSN']['L'],
                               BE_dict=state_tmp['BE']['L'])
            self.scorer.update_info(case_path=current_path, LorR='R', JSN_dict=state_tmp['JSN']['R'],
                               BE_dict=state_tmp['BE']['R'])


    def _load_scorer(self):
        current_path = self.file_paths[self.current_case]

        JSN_L, BE_L = self.scorer.get_info(case_path=current_path, LorR='L')
        JSN_R, BE_R = self.scorer.get_info(case_path=current_path, LorR='R')

        dict_tmp = {'JSN': {'L': JSN_L, 'R': JSN_R},
                    'BE': {'L': BE_L, 'R': BE_R}}

        self.svg_widget.set_score_state(dict_tmp)

    def _action_input(self):
        """
        修改版：
        - 打开文件夹对话框
        - 扫描文件夹中的 .dcm / .bmp
        - 文件名显示到 LW_Files
        - 默认显示第一个文件
        """
        dir_path = QtWidgets.QFileDialog.getExistingDirectory(
            self,
            "Open Folder",
            ""
        )
        if not dir_path:
            return

        # 扫描文件夹
        exts = (".dcm", ".bmp")
        files = [
            f for f in sorted(os.listdir(dir_path))
            if f.lower().endswith(exts)
        ]

        self.LW_Files.clear()
        self.file_paths = []

        if not files:
            self.statusbar.showMessage("Not found .dcm or .bmp files")
            return

        for fname in files:
            self.LW_Files.addItem(fname)
            self.file_paths.append(os.path.join(dir_path, fname))

        self.current_dir = dir_path
        self.statusbar.showMessage(
            f"Loaded folder: {dir_path}  ({len(self.file_paths)} files)"
        )

        # 选中第一个文件（会自动触发 on_file_changed）
        self.current_case = 0
        self.LW_Files.setCurrentRow(0)

        self.set_enable(True)



    def _file_changed(self, row: int):

        """
        当 LW_Files 当前行改变时，切换显示对应图像
        """
        if row < 0 or row >= len(self.file_paths):
            return

        file_path = self.file_paths[row]
        ok = self.xray_viewer.update_image(file_path)
        old_idx = self.current_case

        new_idx = row
        if old_idx != new_idx or self.scorer.get_file_list() == None:
            self._write_scorer()
            self.current_case = row

            self._load_scorer()
        else:
            self.current_case = row
            self._load_scorer()

        self.update_reviewed()

        if ok:
            self.case_path = file_path
            self.statusbar.showMessage(f"Loaded: {file_path}")
        else:
            self.statusbar.showMessage("Failed to load image.")

    # 如果想用 itemClicked，而不是 currentRowChanged，可以这样写：
    # def on_file_item_clicked(self, item: QtWidgets.QListWidgetItem):
    #     row = self.LW_Files.row(item)
    #     self.on_file_changed(row)


    def _export_excel(self):
        """
        将当前所有 case 的打分结果导出为 Excel（使用 Scorer.output_to_excel）
        """
        default_name = datetime.datetime.now().strftime("%Y%m%d_%H%M%S.xlsx")
        default_path = f"RAScorer_{default_name}"

        path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self,
            "导出为 Excel",
            default_path,
            "Excel 文件 (*.xlsx);;所有文件 (*)"
        )
        if not path:
            return

        try:
            # 同样先把当前界面分数写回 scorer
            try:
                if getattr(self, "file_paths", None):
                    self._write_scorer()
            except Exception:
                pass

            self.scorer.output_to_excel(path)
            self.statusbar.showMessage(f"Excel exported to {path}")
        except Exception as e:
            QtWidgets.QMessageBox.critical(
                self,
                "导出失败",
                f"导出 Excel 失败：\n{e}"
            )

    def _load_json(self):
        """
        从 JSON 文件读取后：
        1) 恢复 scorer score_repo
        2) 恢复左侧文件列表的选中项
        3) 恢复显示的图像（L/R）
        4) 恢复所有 combobox / radiobutton 的分数
        """

        path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self,
            "打开 JSON 打分文件",
            "",
            "JSON 文件 (*.json);;所有文件 (*)"
        )
        if not path:
            return

        self.save_path = path

        try:
            # ========== 1. 从 JSON 恢复 scorer ==========
            scorer_open = Scorer()
            scorer_open.load_from_json(path)
            self.scorer = scorer_open
            self.statusbar.showMessage(f"Load JSON：{path} Success")

        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "错误", f"读取 JSON 失败:\n{e}")
            return

        # ========== 2. 恢复左侧当前 case ==========
        self.file_paths = self.scorer.get_file_list()

        for path in self.file_paths:
            self.LW_Files.addItem(path)

        self.current_case = 0
        self.LW_Files.setCurrentRow(0)

        self.statusbar.showMessage("JSON Opened")


if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())
