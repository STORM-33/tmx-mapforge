import sys
import os
import logging
from collections import deque
from PyQt5.QtWidgets import (QApplication, QVBoxLayout, QHBoxLayout, QLabel, QComboBox, QPushButton,
                             QSpinBox, QSlider, QFileDialog, QWidget, QStackedWidget)
from PyQt5.QtCore import QThread, pyqtSignal, QTimer, QSize, Qt
from PyQt5.QtGui import QColor, QPixmap
from generator_main import generate_map, PreviewState
from tileset_renderer import TilesetExtractor, MapRenderer


class FixedGridWidget(QWidget):
    def __init__(self, rows, cols, button_size, spacing):
        super().__init__()
        self.rows = rows
        self.cols = cols
        self.button_size = button_size
        self.spacing = spacing
        self.buttons = []

    def addButton(self, button, row, col):
        button.setParent(self)
        button.setFixedSize(self.button_size, self.button_size)
        self.buttons.append((button, row, col))

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.updateButtonPositions()

    def updateButtonPositions(self):
        for button, row, col in self.buttons:
            x = col * (self.button_size + self.spacing)
            y = row * (self.button_size + self.spacing)
            button.move(x, y)

    def sizeHint(self):
        width = self.cols * (self.button_size + self.spacing) - self.spacing
        height = self.rows * (self.button_size + self.spacing) - self.spacing
        return QSize(width, height)

    def minimumSizeHint(self):
        return self.sizeHint()


class MapPreviewWidget(QWidget):
    """Widget that displays the map preview image and a stage label."""

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)

        self.image_label = QLabel()
        self.image_label.setFixedSize(512, 512)
        self.image_label.setAlignment(Qt.AlignCenter)
        self.image_label.setStyleSheet("background-color: #1a1a2e;")
        layout.addWidget(self.image_label, alignment=Qt.AlignCenter)

        self.stage_label = QLabel("Waiting...")
        self.stage_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.stage_label)

        self.setLayout(layout)

    def update_preview(self, pixmap, stage_text):
        self.image_label.setPixmap(pixmap)
        self.stage_label.setText(stage_text)

    def clear(self):
        self.image_label.clear()
        self.image_label.setStyleSheet("background-color: #1a1a2e;")
        self.stage_label.setText("Waiting...")


class MapGeneratorWorker(QThread):
    preview_signal = pyqtSignal(object)
    finished_signal = pyqtSignal()

    def __init__(self, generate_map_func, **kwargs):
        super().__init__()
        self.generate_map_func = generate_map_func
        self.kwargs = kwargs

    def run(self):
        logging.getLogger('procedural_map_generator_functions').setLevel(logging.WARNING)

        def preview_cb(stage, height_map, id_matrix, items_matrix, units_matrix):
            state = PreviewState(
                stage=stage,
                height_map=height_map,
                id_matrix=id_matrix,
                items_matrix=items_matrix,
                units_matrix=units_matrix,
            )
            self.preview_signal.emit(state)

        try:
            self.generate_map_func(preview_callback=preview_cb, **self.kwargs)
        finally:
            self.finished_signal.emit()


class ColorChangingButton(QPushButton):
    paintRequested = pyqtSignal(int, int)

    def __init__(self, color, row, col):
        super().__init__()
        self.setFixedSize(40, 40)
        self.row = row
        self.col = col
        self.setColor(color)

    def setColor(self, color):
        self.color = color
        self.setStyleSheet(f"background-color: {color.name()};")

    def toggleColor(self, color1, color2):
        self.setColor(color1 if self.color == color2 else color2)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.paintRequested.emit(self.row, self.col)
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if event.buttons() & Qt.LeftButton:
            target = QApplication.widgetAt(event.globalPos())
            if isinstance(target, ColorChangingButton):
                self.paintRequested.emit(target.row, target.col)
        super().mouseMoveEvent(event)

class MapGeneratorGUI(QWidget):
    def __init__(self):
        super().__init__()
        self.button_size = 26
        self.grid_spacing = 5
        self.pattern_colors = {
            "Forest": (QColor("green"), QColor("blue")),
            "Winter": (QColor("white"), QColor("blue")),
            "Volcanic": (QColor("gray"), QColor("red")),
            "Desert": (QColor("yellow"), QColor("brown")),
            "Jungle": (QColor("green"), QColor("blue"))
        }
        base_matrix = [[1, 0, 1, 0, 1],
                       [1, 1, 0, 1, 1],
                       [1, 0, 1, 0, 1],
                       [1, 1, 0, 1, 1],
                       [1, 0, 1, 0, 1]]
        self.matrix = [
            expanded_row[:]
            for row in base_matrix
            for expanded_row in ([cell for value in row for cell in (value, value)],) * 2
        ]
        self.default_output_path = os.path.dirname(sys.executable)
        self._extractor_cache = {}
        self._renderer = None
        self._preview_queue = deque()
        self.undo_stack = []
        self.redo_stack = []
        self._preview_timer = QTimer()
        self._preview_timer.setInterval(150)
        self._preview_timer.timeout.connect(self._flush_next_preview)
        self._generation_finished = False
        self.initUI()

    def initUI(self):
        layout = QVBoxLayout()

        default_pattern = "Forest"
        grid_container = QWidget()
        grid_container_layout = QVBoxLayout()
        grid_controls = QHBoxLayout()
        self.grid_size_spin = self.create_spinbox(5, 30, len(self.matrix))
        self.grid_size_spin.valueChanged.connect(self.resize_grid)
        grid_controls.addWidget(QLabel("Grid size (5-30):"))
        grid_controls.addWidget(self.grid_size_spin)
        self.grid_tool_combo = QComboBox()
        self.grid_tool_combo.addItems(["Brush", "Erase"])
        grid_controls.addWidget(self.grid_tool_combo)
        grid_container_layout.addLayout(grid_controls)
        grid_history_controls = QHBoxLayout()
        self.undo_button = QPushButton("Undo")
        self.undo_button.clicked.connect(self.undo_grid)
        grid_history_controls.addWidget(self.undo_button)
        self.redo_button = QPushButton("Redo")
        self.redo_button.clicked.connect(self.redo_grid)
        grid_history_controls.addWidget(self.redo_button)
        self.clear_button = QPushButton("Clear")
        self.clear_button.clicked.connect(self.clear_grid)
        grid_history_controls.addWidget(self.clear_button)
        grid_container_layout.addLayout(grid_history_controls)
        brush_size_controls = QHBoxLayout()
        self.grid_brush_size_label = QLabel("Brush / Eraser size: 1")
        brush_size_controls.addWidget(self.grid_brush_size_label)
        self.grid_brush_size_slider = QSlider(Qt.Horizontal)
        self.grid_brush_size_slider.setRange(1, min(10, len(self.matrix)))
        self.grid_brush_size_slider.setValue(1)
        self.grid_brush_size_slider.valueChanged.connect(
            lambda value: self.grid_brush_size_label.setText(f"Brush / Eraser size: {value}")
        )
        brush_size_controls.addWidget(self.grid_brush_size_slider, 1)
        grid_container_layout.addLayout(brush_size_controls)
        self.grid_container_layout = grid_container_layout
        grid_container_layout.setContentsMargins(0, 0, 0, 0)
        grid_container.setLayout(grid_container_layout)

        self.rebuild_grid()

        # Stacked widget: page 0 = grid, page 1 = preview
        self.stacked_widget = QStackedWidget()
        self.stacked_widget.addWidget(grid_container)

        self.preview_widget = MapPreviewWidget()
        self.stacked_widget.addWidget(self.preview_widget)

        layout.addWidget(self.stacked_widget)

        self.output_path_label = QLabel(f"Output path: {self.default_output_path}")
        layout.addWidget(self.output_path_label)

        select_path_button = QPushButton("Select output directory")
        select_path_button.clicked.connect(self.select_output_directory)
        layout.addWidget(select_path_button)

        height = self.create_spinbox(50, 640, 160)
        layout.addLayout(self.create_input("Height (50-640):", "height", height))

        width = self.create_spinbox(50, 640, 160)
        layout.addLayout(self.create_input("Width (50-640):", "width", width))

        self.mirroring_combo = QComboBox()
        self.mirroring_combo.addItems(["none", "horizontal", "vertical", "both", "diagonal1", "diagonal2"])
        self.mirroring_combo.setCurrentText("vertical")
        self.mirroring_combo.currentTextChanged.connect(self.update_matrix)
        layout.addLayout(self.create_input("Mirroring:", "mirroring", self.mirroring_combo))

        num_resource_pulls = self.create_spinbox(0, 50, 12)
        layout.addLayout(self.create_input("Num of resource pulls (0-50):", "num_resource_pulls", num_resource_pulls))

        num_command_centers = self.create_spinbox(0, 10, 4, 2)
        layout.addLayout(self.create_input("Num of players (even, 0-10):", "num_command_centers", num_command_centers))

        num_height_levels = self.create_spinbox(1, 7, 7)
        layout.addLayout(self.create_input("Num of height levels (1-7):", "num_height_levels", num_height_levels))

        num_ocean_levels = self.create_spinbox(1, 3, 3)
        layout.addLayout(self.create_input("Num of ocean levels (1-3):", "num_ocean_levels", num_ocean_levels))

        shoreline_smoothness = self.create_spinbox(0, 100, 0)
        layout.addLayout(self.create_input("Shoreline smoothness (0-100%):", "shoreline_smoothness", shoreline_smoothness))

        self.pattern_combo = QComboBox()
        self.pattern_combo.addItems(list(self.pattern_colors.keys()))
        self.pattern_combo.setCurrentText(default_pattern)
        self.pattern_combo.currentTextChanged.connect(self.update_colors)
        layout.addLayout(self.create_input("Tileset:", "pattern", self.pattern_combo))

        self.generate_button = QPushButton("Generate map")
        self.generate_button.clicked.connect(self.generate_map)
        layout.addWidget(self.generate_button)

        self.setLayout(layout)
        self.setWindowTitle('Map generator')
        self.show()

        self.update_matrix()
        self.refresh_grid_history()

    def select_output_directory(self):
        directory = QFileDialog.getExistingDirectory(self, "Select Output Directory", self.default_output_path)
        if directory:
            self.default_output_path = directory
        self.output_path_label.setText(f"Output path: {self.default_output_path}")

    def create_spinbox(self, min_value, max_value, default_value, step=1):
        spinbox = QSpinBox()
        spinbox.setMinimum(min_value)
        spinbox.setMaximum(max_value)
        spinbox.setSingleStep(step)
        spinbox.setValue(default_value)
        return spinbox

    def create_input(self, label, name, widget):
        layout = QHBoxLayout()
        layout.addWidget(QLabel(label))
        widget.setObjectName(name)
        layout.addWidget(widget)
        return layout

    def rebuild_grid(self):
        if hasattr(self, "grid_widget"):
            self.grid_container_layout.removeWidget(self.grid_widget)
            self.grid_widget.deleteLater()
        size = len(self.matrix)
        self.button_size = max(4, 260 // size)
        self.grid_widget = FixedGridWidget(size, size, self.button_size, 0)
        self.buttons = []
        pattern = self.pattern_combo.currentText() if hasattr(self, "pattern_combo") else "Forest"
        color1, color2 = self.pattern_colors[pattern]
        for row_index in range(size):
            row = []
            for col_index in range(size):
                color = color1 if self.matrix[row_index][col_index] == 1 else color2
                button = ColorChangingButton(color, row_index, col_index)
                button.paintRequested.connect(self.paint_grid_cell)
                self.grid_widget.addButton(button, row_index, col_index)
                row.append(button)
            self.buttons.append(row)
        self.grid_container_layout.addWidget(self.grid_widget, alignment=Qt.AlignCenter)

    def resize_grid(self, size):
        before = [row[:] for row in self.matrix]
        old_size = len(self.matrix)
        self.matrix = [
            [self.matrix[min(old_size - 1, row * old_size // size)][min(old_size - 1, col * old_size // size)] for col in range(size)]
            for row in range(size)
        ]
        self.rebuild_grid()
        self.grid_brush_size_slider.setMaximum(min(10, size))
        self.update_matrix()
        self.record_grid_change(before)

    def paint_grid_cell(self, row, col):
        before = [row[:] for row in self.matrix]
        value = 0 if self.grid_tool_combo.currentText() == "Erase" else 1
        brush_size = self.grid_brush_size_slider.value()
        start = -(brush_size // 2)
        for dr in range(start, start + brush_size):
            for dc in range(start, start + brush_size):
                brush_row, brush_col = row + dr, col + dc
                if 0 <= brush_row < len(self.matrix) and 0 <= brush_col < len(self.matrix):
                    self.matrix[brush_row][brush_col] = value
                    self.update_mirrored_buttons(brush_row, brush_col, update_colors=False)
        self.update_button_colors()
        self.record_grid_change(before)

    def record_grid_change(self, before):
        if before == self.matrix:
            return
        self.undo_stack.append(before)
        self.redo_stack.clear()
        self.refresh_grid_history()

    def refresh_grid_history(self):
        self.undo_button.setEnabled(bool(self.undo_stack))
        self.redo_button.setEnabled(bool(self.redo_stack))
        self.clear_button.setEnabled(any(value for row in self.matrix for value in row))

    def clear_grid(self):
        before = [row[:] for row in self.matrix]
        self.matrix = [[0] * len(self.matrix) for _ in self.matrix]
        self.update_button_colors()
        self.record_grid_change(before)

    def undo_grid(self):
        if not self.undo_stack:
            return
        self.redo_stack.append([row[:] for row in self.matrix])
        self.matrix = self.undo_stack.pop()
        self.set_grid_size_value()
        self.rebuild_grid()
        self.update_button_colors()
        self.refresh_grid_history()

    def redo_grid(self):
        if not self.redo_stack:
            return
        self.undo_stack.append([row[:] for row in self.matrix])
        self.matrix = self.redo_stack.pop()
        self.set_grid_size_value()
        self.rebuild_grid()
        self.update_button_colors()
        self.refresh_grid_history()

    def set_grid_size_value(self):
        self.grid_size_spin.blockSignals(True)
        self.grid_size_spin.setValue(len(self.matrix))
        self.grid_size_spin.blockSignals(False)
        self.grid_brush_size_slider.setMaximum(min(10, len(self.matrix)))

    def update_mirrored_buttons(self, row, col, update_colors=True):
        mirroring = self.mirroring_combo.currentText()
        last = len(self.matrix) - 1
        if mirroring == "horizontal":
            mirrored_row = last - row
            self.matrix[mirrored_row][col] = self.matrix[row][col]
        elif mirroring == "vertical":
            mirrored_col = last - col
            self.matrix[row][mirrored_col] = self.matrix[row][col]
        elif mirroring == "both":
            mirrored_row = last - row
            mirrored_col = last - col
            self.matrix[mirrored_row][col] = self.matrix[row][col]
            self.matrix[row][mirrored_col] = self.matrix[row][col]
            self.matrix[mirrored_row][mirrored_col] = self.matrix[row][col]
        elif mirroring == "diagonal1":
            self.matrix[col][row] = self.matrix[row][col]
        elif mirroring == "diagonal2":
            mirrored_row = last - col
            mirrored_col = last - row
            self.matrix[mirrored_row][mirrored_col] = self.matrix[row][col]

        if update_colors:
            self.update_button_colors()

    def update_matrix(self):
        for row in range(len(self.matrix)):
            for col in range(len(self.matrix[row])):
                self.update_mirrored_buttons(row, col)

    def update_colors(self):
        self.update_button_colors()
        self.update_matrix()

    def update_button_colors(self):
        current_pattern = self.pattern_combo.currentText()
        color1, color2 = self.pattern_colors[current_pattern]
        for i, row in enumerate(self.buttons):
            for j, button in enumerate(row):
                button.setColor(color1 if self.matrix[i][j] == 1 else color2)

    def get_matrix(self):
        return self.matrix

    def _get_extractor(self, pattern_index):
        if pattern_index not in self._extractor_cache:
            tmx_path = f"generator_blueprint{pattern_index}.tmx"
            self._extractor_cache[pattern_index] = TilesetExtractor(tmx_path)
        return self._extractor_cache[pattern_index]

    def generate_map(self):
        initial_matrix = self.get_matrix()
        height = self.findChild(QSpinBox, "height").value()
        width = self.findChild(QSpinBox, "width").value()
        mirroring = self.mirroring_combo.currentText()
        num_resource_pulls = self.findChild(QSpinBox, "num_resource_pulls").value()
        num_command_centers = self.findChild(QSpinBox, "num_command_centers").value()
        num_height_levels = self.findChild(QSpinBox, "num_height_levels").value()
        num_ocean_levels = self.findChild(QSpinBox, "num_ocean_levels").value()
        shoreline_smoothness = self.findChild(QSpinBox, "shoreline_smoothness").value() / 100.0
        pattern = list(self.pattern_colors.keys()).index(self.pattern_combo.currentText()) + 1

        output_path = self.default_output_path

        # Disable button to prevent concurrent generation
        self.generate_button.setEnabled(False)

        # Switch to preview page
        self.stacked_widget.setCurrentIndex(1)
        self.preview_widget.clear()
        self._preview_queue.clear()
        self._generation_finished = False

        # Initialize renderer for current pattern
        extractor = self._get_extractor(pattern)
        self._renderer = MapRenderer(extractor)

        self.worker = MapGeneratorWorker(
            generate_map,
            initial_matrix=initial_matrix,
            height=height, width=width,
            mirroring=mirroring,
            num_resource_pulls=num_resource_pulls,
            num_command_centers=num_command_centers,
            num_height_levels=num_height_levels,
            num_ocean_levels=num_ocean_levels,
            shoreline_smoothness=shoreline_smoothness,
            pattern=pattern,
            output_path=output_path
        )
        self.worker.preview_signal.connect(self._enqueue_preview)
        self.worker.finished_signal.connect(self._on_worker_finished)
        self.worker.start()
        self._preview_timer.start()

    def _enqueue_preview(self, state):
        self._preview_queue.append(state)

    def _flush_next_preview(self):
        if not self._preview_queue:
            if self._generation_finished:
                self._preview_timer.stop()
                QTimer.singleShot(3000, self._switch_to_grid)
            return

        state = self._preview_queue.popleft()
        if self._renderer is None:
            return

        if state.id_matrix is None:
            qimg = self._renderer.render_height_map(state.height_map)
        else:
            qimg = self._renderer.render_terrain(state.id_matrix, state.items_matrix, state.units_matrix)

        pixmap = QPixmap.fromImage(qimg)
        stage_text = state.stage.replace("_", " ").title()
        self.preview_widget.update_preview(pixmap, stage_text)

    def _on_worker_finished(self):
        self._generation_finished = True
        self.worker = None
        self.generate_button.setEnabled(True)

    def _switch_to_grid(self):
        self.stacked_widget.setCurrentIndex(0)

if __name__ == '__main__':
    from wizard_gui import MainWindow
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())
