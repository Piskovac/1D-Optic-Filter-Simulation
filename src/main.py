"""
Optical Filter Designer - Main Application

Refactored and organized version of the optical filter design application.
All functionality preserved while improving code structure and maintainability.
"""

import io
import json
import os
import pickle
import random
import re
import sys
import traceback

import numpy as np
import yaml

from PyQt5.QtCore import (
    QPoint, QRect, QSize, Qt, QThread, pyqtSignal
)
from PyQt5.QtGui import (
    QBrush, QColor, QFont, QPainter, QPalette, QPen
)
from PyQt5.QtWidgets import (
    QAction, QApplication, QCheckBox, QColorDialog, QComboBox, QDialog, QDialogButtonBox,
    QDoubleSpinBox, QFileDialog, QFormLayout, QFrame, QGroupBox, QHBoxLayout, QHeaderView,
    QLabel, QLineEdit, QMainWindow, QMenu, QMenuBar, QMessageBox, QPushButton, QScrollArea,
    QSlider, QSpinBox, QSplitter, QTabWidget, QTableWidget, QTableWidgetItem, QVBoxLayout,
    QWidget
)

from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure

# Import our modular components
from api.material_api import MaterialSearchAPI, MaterialHandler
from calculations.tmm_worker import TMM_Worker
from calculations.tmm_calculator import TMM_Calculator
from ui.dialogs import CustomMaterialDialog, ThicknessEditDialog
from ui.tables import MaterialTable, ArrayTable


class FilterVisualizerWindow(QMainWindow):
    """Floating window for visualizing the optical filter structure"""

    def __init__(self, material_table, array_table, parent=None):
        super().__init__(parent)
        self.material_table = material_table
        self.array_table = array_table
        self.setWindowTitle("Filter Visualization")
        self.setMinimumSize(800, 200)

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)

        self.filter_visualizer = FilterVisualizer(material_table, array_table)

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOn)
        scroll_area.setWidget(self.filter_visualizer)

        layout.addWidget(scroll_area)

    def set_filter(self, filter_definition):
        """Set the filter definition to visualize"""
        self.filter_visualizer.set_filter(filter_definition)


class FilterVisualizer(QWidget):
    """Widget for visualizing the optical filter structure"""

    def __init__(self, material_table, array_table, parent=None):
        super().__init__(parent)
        self.material_table = material_table
        self.array_table = array_table
        self.filter_definition = ""
        self.expanded_definition = []
        self.setMinimumHeight(100)

        layout = QVBoxLayout(self)
        self.setLayout(layout)
        self.setMinimumHeight(80)

    def set_filter(self, filter_definition):
        """Set the filter definition to visualize"""
        self.filter_definition = filter_definition
        self.expanded_definition = self.expand_filter(filter_definition)
        self.update()

    def paintEvent(self, event):
        """Paint the visualization of the filter structure"""
        if not self.expanded_definition:
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        colors = self.material_table.get_material_colors()
        rect_width = 30
        total_width = len(self.expanded_definition) * rect_width
        self.setMinimumWidth(total_width)

        rect_height = self.height() - 10
        y_pos = 5

        for i, layer in enumerate(self.expanded_definition):
            x_pos = i * rect_width

            if layer == "...":
                painter.setPen(QPen(Qt.black, 2))
                painter.drawText(QRect(x_pos, y_pos, rect_width, rect_height),
                                 Qt.AlignCenter, "...")
            else:
                if layer in colors:
                    painter.setBrush(QBrush(colors[layer]))
                else:
                    painter.setBrush(QBrush(Qt.lightGray))

                painter.setPen(QPen(Qt.black, 1))
                painter.drawRect(x_pos, y_pos, rect_width, rect_height)

                painter.setPen(Qt.black)
                font = painter.font()
                font.setPointSize(8)
                painter.setFont(font)
                painter.drawText(QRect(x_pos, y_pos, rect_width, 20),
                                 Qt.AlignCenter, layer)

    def expand_filter(self, filter_definition):
        """Expand the filter definition into a list of individual layers"""
        if not filter_definition:
            return []

        arrays = self.array_table.get_arrays()
        pattern = r'\(([^)]+)\)\^(\d+)'

        while re.search(pattern, filter_definition):
            match = re.search(pattern, filter_definition)
            array_id = match.group(1)
            repetitions = int(match.group(2))

            if repetitions > 3:
                replacement = f"{array_id}*{array_id}*{array_id}*..."
            else:
                replacement = "*".join([array_id] * repetitions)

            filter_definition = filter_definition[:match.start()] + replacement + filter_definition[match.end():]

        components = filter_definition.split("*")
        expanded = []

        for component in components:
            component = component.strip()
            if component == "...":
                expanded.append("...")
            elif component in arrays:
                array_def = arrays[component]
                array_components = array_def.split("*")
                expanded.extend(array_components)
            else:
                expanded.append(component)

        return expanded

    def expand_filter_for_calculation(self, filter_definition):
        """Expand the filter definition for calculation - FULL expansion"""
        if not filter_definition:
            return []

        arrays = self.array_table.get_arrays()
        pattern = r'\(([^)]+)\)\^(\d+)'

        while re.search(pattern, filter_definition):
            match = re.search(pattern, filter_definition)
            array_id = match.group(1)
            repetitions = int(match.group(2))

            replacement = "*".join([array_id] * repetitions)
            filter_definition = filter_definition[:match.start()] + replacement + filter_definition[match.end():]

        components = filter_definition.split("*")
        expanded = []

        for component in components:
            component = component.strip()
            if component in arrays:
                array_def = arrays[component]
                array_components = array_def.split("*")
                expanded.extend(array_components)
            else:
                expanded.append(component)

        return expanded


class TMM_Plots(QWidget):
    """Widget for displaying TMM calculation results"""

    def __init__(self, parent=None):
        super().__init__(parent)

        layout = QVBoxLayout(self)

        self.figure = Figure(figsize=(10, 4))
        self.canvas = FigureCanvas(self.figure)
        self.ax = self.figure.add_subplot(111)

        self.ax.set_title('Reflection Spectrum')
        self.ax.set_xlabel('Wavelength (nm)')
        self.ax.set_ylabel('Reflection (dB)')

        layout.addWidget(self.canvas)

    def plot_results(self, wavelengths, R_TE, R_TM):
        """Plot the reflection spectrum"""
        self.ax.clear()

        self.ax.set_title('Reflection Spectrum')
        self.ax.set_xlabel('Wavelength (nm)')
        self.ax.set_ylabel('Reflection (dB)')

        epsilon = 1e-10
        R_dB = 10 * np.log10(R_TM + epsilon)

        self.ax.plot(wavelengths, R_dB, 'r-', linewidth=2)
        self.ax.plot(wavelengths, R_dB, 'b--', linewidth=1.5)

        self.ax.set_xlim(wavelengths[0], wavelengths[-1])

        y_min = np.min(R_dB)
        y_max = np.max(R_dB)

        if np.isfinite(y_min) and np.isfinite(y_max):
            if y_max - y_min < 10:
                margin = 5
                self.ax.set_ylim(y_min - margin, y_max + margin)
            else:
                self.ax.set_ylim(y_min, y_max)

        self.ax.grid(True, alpha=0.3)
        self.canvas.draw()


class OpticalFilterApp(QMainWindow):
    """Main application window for the optical filter designer"""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Optical Filter Designer v5 - Refactored")
        self.setGeometry(100, 100, 1400, 900)

        # Initialize components with error handling
        try:
            self.material_api = MaterialSearchAPI()
        except Exception as e:
            print(f"Warning: MaterialSearchAPI initialization failed: {e}")
            self.material_api = None

        try:
            self.tmm_calculator = TMM_Calculator()
        except Exception as e:
            print(f"Warning: TMM_Calculator initialization failed: {e}")
            self.tmm_calculator = None

        self.last_calculation_data = None

        self.setup_ui()
        self.setup_menu()

        # Show warning if critical components failed
        if self.material_api is None or (hasattr(self.material_api, 'initialized') and not self.material_api.initialized):
            self.statusBar().showMessage("Warning: Material database not available. Some features may be limited.", 5000)

    def setup_ui(self):
        """Setup the user interface"""
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)

        top_sections_layout = QHBoxLayout()

        self.create_material_section(top_sections_layout)
        self.create_array_section(top_sections_layout)
        self.create_filter_section(top_sections_layout)

        main_layout.addLayout(top_sections_layout)
        self.create_calculation_section(main_layout)

        self.visualization_window = FilterVisualizerWindow(self.material_table, self.array_table, self)

    def create_material_section(self, parent_layout):
        """Create the material definition section"""
        group_box = QGroupBox("Material Library")
        group_box.setMinimumWidth(300)
        layout = QVBoxLayout(group_box)

        controls_layout = QHBoxLayout()

        self.search_field = QLineEdit()
        self.search_field.setPlaceholderText("Search materials...")
        self.search_field.textChanged.connect(self.search_materials)
        controls_layout.addWidget(QLabel("Search:"))
        controls_layout.addWidget(self.search_field)

        self.material_dropdown = QComboBox()
        self.material_dropdown.setMinimumWidth(200)
        controls_layout.addWidget(self.material_dropdown)

        self.label_entry = QLineEdit()
        self.label_entry.setMaxLength(3)
        self.label_entry.setMaximumWidth(50)
        controls_layout.addWidget(QLabel("ID:"))
        controls_layout.addWidget(self.label_entry)

        self.defect_checkbox = QCheckBox("Defect")
        controls_layout.addWidget(self.defect_checkbox)

        self.add_material_btn = QPushButton("Add Material")
        self.add_material_btn.clicked.connect(self.add_material)
        controls_layout.addWidget(self.add_material_btn)

        layout.addLayout(controls_layout)

        extra_buttons_layout = QHBoxLayout()

        self.browse_material_btn = QPushButton("Browse Material File...")
        self.browse_material_btn.clicked.connect(self.browse_material_file)
        extra_buttons_layout.addWidget(self.browse_material_btn)

        self.custom_material_btn = QPushButton("Add Custom Material...")
        self.custom_material_btn.clicked.connect(self.add_custom_material)
        extra_buttons_layout.addWidget(self.custom_material_btn)

        layout.addLayout(extra_buttons_layout)

        self.material_table = MaterialTable()
        layout.addWidget(self.material_table)

        self.material_count_label = QLabel("0/100 materials defined")
        layout.addWidget(self.material_count_label)

        parent_layout.addWidget(group_box)

    def create_array_section(self, parent_layout):
        """Create the array definition section"""
        group_box = QGroupBox("Array Definitions")
        group_box.setMinimumWidth(300)
        layout = QVBoxLayout(group_box)

        controls_layout = QHBoxLayout()

        self.array_def_entry = QLineEdit()
        self.array_def_entry.setPlaceholderText("Example: A*B*Si")
        controls_layout.addWidget(QLabel("Definition:"))
        controls_layout.addWidget(self.array_def_entry, 1)

        self.add_array_btn = QPushButton("Add Array")
        self.add_array_btn.clicked.connect(self.add_array)
        controls_layout.addWidget(self.add_array_btn)

        layout.addLayout(controls_layout)

        self.array_warning_label = QLabel("")
        self.array_warning_label.setStyleSheet("color: red;")
        layout.addWidget(self.array_warning_label)

        self.array_table = ArrayTable(self.material_table)
        layout.addWidget(self.array_table)

        self.array_count_label = QLabel("0/20 arrays defined")
        layout.addWidget(self.array_count_label)

        parent_layout.addWidget(group_box)

    def create_filter_section(self, parent_layout):
        """Create the optical filter definition section"""
        group_box = QGroupBox("Optical Filter Structure")
        group_box.setMinimumWidth(300)
        layout = QVBoxLayout(group_box)

        controls_layout = QHBoxLayout()

        self.filter_entry = QLineEdit()
        self.filter_entry.setPlaceholderText("Example: [(M1)^5*D*(M2)^3*B]")
        controls_layout.addWidget(QLabel("Filter:"))
        controls_layout.addWidget(self.filter_entry, 1)

        self.validate_filter_btn = QPushButton("Validate")
        self.validate_filter_btn.clicked.connect(self.validate_filter)
        controls_layout.addWidget(self.validate_filter_btn)

        layout.addLayout(controls_layout)

        self.filter_status_label = QLabel("")
        layout.addWidget(self.filter_status_label)

        help_text = QLabel("Syntax: Use (M1)^5 for repetition, * to combine layers")
        help_text.setWordWrap(True)
        help_text.setStyleSheet("color: #666; font-style: italic;")
        layout.addWidget(help_text)

        self.show_visualization_btn = QPushButton("Show Filter")
        self.show_visualization_btn.clicked.connect(self.show_visualization)
        layout.addWidget(self.show_visualization_btn)

        layout.addStretch()

        parent_layout.addWidget(group_box)

        # Connect filter entry to visualization
        self.filter_entry.textChanged.connect(self.update_filter_visualization)

    def create_calculation_section(self, parent_layout):
        """Create the TMM calculation section with improved input handling"""
        group_box = QGroupBox("TMM Calculation")
        layout = QHBoxLayout(group_box)

        params_widget = QWidget()
        params_layout = QVBoxLayout(params_widget)
        params_layout.setContentsMargins(0, 0, 0, 0)

        form_layout = QFormLayout()

        self.wavelength_start = QDoubleSpinBox()
        self.wavelength_start.setRange(100, 5000)
        self.wavelength_start.setValue(400)
        self.wavelength_start.setSuffix(" nm")
        self.wavelength_start.setDecimals(1)
        self.wavelength_start.setSingleStep(10.0)
        self.wavelength_start.setKeyboardTracking(False)

        self.wavelength_end = QDoubleSpinBox()
        self.wavelength_end.setRange(100, 5000)
        self.wavelength_end.setValue(800)
        self.wavelength_end.setSuffix(" nm")
        self.wavelength_end.setDecimals(1)
        self.wavelength_end.setSingleStep(10.0)
        self.wavelength_end.setKeyboardTracking(False)

        self.wavelength_steps = QSpinBox()
        self.wavelength_steps.setRange(10, 2000)
        self.wavelength_steps.setValue(100)
        self.wavelength_steps.setSingleStep(10)
        self.wavelength_steps.setKeyboardTracking(False)

        wavelength_layout = QHBoxLayout()
        wavelength_layout.addWidget(self.wavelength_start)
        wavelength_layout.addWidget(QLabel("to"))
        wavelength_layout.addWidget(self.wavelength_end)
        wavelength_layout.addWidget(QLabel("Steps:"))
        wavelength_layout.addWidget(self.wavelength_steps)

        form_layout.addRow("Wavelength:", wavelength_layout)

        self.incident_angle = QDoubleSpinBox()
        self.incident_angle.setRange(0, 89)
        self.incident_angle.setValue(0)
        self.incident_angle.setSuffix("°")
        self.incident_angle.setDecimals(1)
        self.incident_angle.setSingleStep(1.0)
        self.incident_angle.setKeyboardTracking(False)
        form_layout.addRow("Incident Angle:", self.incident_angle)

        self.default_thickness = QDoubleSpinBox()
        self.default_thickness.setRange(1, 10000)
        self.default_thickness.setValue(100)
        self.default_thickness.setSuffix(" nm")
        self.default_thickness.setDecimals(1)
        self.default_thickness.setSingleStep(10.0)
        self.default_thickness.setKeyboardTracking(False)
        form_layout.addRow("Default Layer Thickness:", self.default_thickness)

        params_layout.addLayout(form_layout)

        self.calculate_btn = QPushButton("Calculate")
        self.calculate_btn.setStyleSheet("font-weight: bold; padding: 8px;")
        self.calculate_btn.clicked.connect(self.calculate_filter)
        params_layout.addWidget(self.calculate_btn)

        self.save_btn = QPushButton("Save Filter")
        self.save_btn.setStyleSheet("padding: 8px;")
        self.save_btn.clicked.connect(self.save_project)
        params_layout.addWidget(self.save_btn)

        params_layout.addStretch()

        self.tmm_plots = TMM_Plots()

        layout.addWidget(params_widget, 1)
        layout.addWidget(self.tmm_plots, 2)

        parent_layout.addWidget(group_box)

    def setup_menu(self):
        """Setup the application menu"""
        menubar = self.menuBar()

        # File menu
        file_menu = menubar.addMenu('File')

        save_action = QAction('Save Project', self)
        save_action.triggered.connect(self.save_project)
        file_menu.addAction(save_action)

        load_action = QAction('Load Project', self)
        load_action.triggered.connect(self.load_project)
        file_menu.addAction(load_action)

        file_menu.addSeparator()

        export_action = QAction('Export Results', self)
        export_action.triggered.connect(self.export_results)
        file_menu.addAction(export_action)

    def search_materials(self):
        """Search for materials in the database"""
        query = self.search_field.text().strip()
        if not query:
            self.material_dropdown.clear()
            return

        # Check if material API is available
        if self.material_api is None:
            self.material_dropdown.clear()
            self.material_dropdown.addItem("Material database not available", None)
            return

        if not self.material_api.initialized:
            self.material_dropdown.clear()
            if self.material_api.error_message:
                self.material_dropdown.addItem(f"Database error: {self.material_api.error_message}", None)
            else:
                self.material_dropdown.addItem("Database not initialized", None)
            return

        try:
            results = self.material_api.search_materials(query)

            # Clear and populate dropdown
            self.material_dropdown.clear()

            if not results:
                self.material_dropdown.addItem("No materials found", None)
                return

            # Group materials by base name like in original code
            unique_materials = {}
            for material_id, material_name in results[:50]:  # Limit to 50 results
                clean_name = self.clean_material_name(material_name)

                # Extract base name
                base_name = None
                if "(" in clean_name and ")" in clean_name:
                    open_pos = clean_name.find("(")
                    close_pos = clean_name.find(")", open_pos)
                    if close_pos > open_pos:
                        base_name = clean_name[:close_pos + 1].strip()

                if base_name is None:
                    parts = clean_name.split(":")
                    base_name = parts[0].strip()

                if ":" in base_name:
                    base_name = base_name.split(":")[0].strip()

                # Remove wavelength info
                if "µm" in base_name or "nm" in base_name:
                    for unit in ["µm", "nm", ":"]:
                        if unit in base_name:
                            index = base_name.find(unit)
                            base_name = base_name[:index].strip()
                            break

                if base_name.strip() == "":
                    base_name = clean_name

                if base_name not in unique_materials:
                    unique_materials[base_name] = []
                unique_materials[base_name].append((material_id, clean_name))

            # Add grouped materials to dropdown
            for base_name in sorted(unique_materials.keys()):
                self.material_dropdown.addItem(base_name)
                index = self.material_dropdown.count() - 1
                # Store variants as data - for now just use first variant
                variants = unique_materials[base_name]
                if variants:
                    first_variant_id = variants[0][0]  # Use first variant ID
                    self.material_dropdown.setItemData(index, first_variant_id, Qt.UserRole)

        except Exception as e:
            print(f"Search error: {e}")  # Console logging
            self.material_dropdown.clear()
            self.material_dropdown.addItem("Search failed", None)

    def clean_material_name(self, name):
        """Clean up HTML tags and format material names properly"""
        subscript_map = {
            '0': '₀', '1': '₁', '2': '₂', '3': '₃', '4': '₄',
            '5': '₅', '6': '₆', '7': '₇', '8': '₈', '9': '₉'
        }

        superscript_map = {
            '0': '⁰', '1': '¹', '2': '²', '3': '³', '4': '⁴',
            '5': '⁵', '6': '⁶', '7': '⁷', '8': '⁸', '9': '⁹'
        }

        # Remove HTML tags
        import re
        clean = re.sub(r'<sub>(.*?)</sub>', lambda m: ''.join(subscript_map.get(c, c) for c in m.group(1)), name)
        clean = re.sub(r'<sup>(.*?)</sup>', lambda m: ''.join(superscript_map.get(c, c) for c in m.group(1)), clean)
        clean = re.sub(r'<.*?>', '', clean)  # Remove any remaining HTML tags

        return clean.strip()

    def show_search_results(self, results):
        """Show search results in a dialog"""
        dialog = QDialog(self)
        dialog.setWindowTitle("Search Results")
        dialog.setModal(True)
        dialog.resize(600, 400)

        layout = QVBoxLayout(dialog)

        results_table = QTableWidget()
        results_table.setColumnCount(3)
        results_table.setHorizontalHeaderLabels(["Material", "ID", "Add"])
        results_table.setRowCount(len(results))

        for i, (material_id, material_name) in enumerate(results):
            results_table.setItem(i, 0, QTableWidgetItem(material_name))
            results_table.setItem(i, 1, QTableWidgetItem(material_id))

            add_btn = QPushButton("Add")
            add_btn.clicked.connect(lambda checked, mid=material_id, mname=material_name:
                                   self.add_material_from_search(mid, mname, dialog))
            results_table.setCellWidget(i, 2, add_btn)

        layout.addWidget(results_table)

        button_box = QDialogButtonBox(QDialogButtonBox.Close)
        button_box.rejected.connect(dialog.reject)
        layout.addWidget(button_box)

        dialog.exec_()

    def add_material_from_search(self, material_id, material_name, dialog):
        """Add a material from search results"""
        try:
            # Check for variants
            if '|' in material_id:
                # Single material
                label, ok = self.get_unique_label("Enter material label:")
                if ok:
                    self.material_table.add_material(label, material_name, material_id)
                    dialog.accept()
            else:
                QMessageBox.warning(self, "Error", "Invalid material ID format")

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to add material: {str(e)}")

    def get_unique_label(self, prompt):
        """Get a unique label from the user"""
        from PyQt5.QtWidgets import QInputDialog

        while True:
            label, ok = QInputDialog.getText(self, "Material Label", prompt)
            if not ok:
                return None, False

            label = label.strip()
            if not label:
                QMessageBox.warning(self, "Invalid Input", "Please enter a label.")
                continue

            if self.material_table.is_label_unique(label):
                return label, True
            else:
                QMessageBox.warning(self, "Duplicate Label",
                                   f"Label '{label}' already exists. Please choose another.")

    def add_custom_material(self):
        """Add a custom material with fixed refractive index"""
        dialog = CustomMaterialDialog(self)
        if dialog.exec_() == QDialog.Accepted:
            name = dialog.name_edit.text().strip()
            label = dialog.id_edit.text().strip()
            n = dialog.n_spin.value()
            k = dialog.k_spin.value()
            is_defect = dialog.defect_checkbox.isChecked()

            if not self.material_table.is_label_unique(label):
                QMessageBox.warning(self, "Duplicate Label",
                                   f"Label '{label}' already exists.")
                return

            material_id = complex(n, k) if k > 0 else n
            self.material_table.add_material(label, name, material_id, is_defect)

    def browse_material_file(self):
        """Browse for a material file"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Select Material File", "", "YAML files (*.yml)")

        if file_path:
            try:
                # Validate the file
                with open(file_path, 'r') as f:
                    yaml.safe_load(f)

                name = os.path.basename(file_path)
                label, ok = self.get_unique_label("Enter material label:")

                if ok:
                    self.material_table.add_material(label, name, file_path)

            except Exception as e:
                QMessageBox.critical(self, "File Error",
                                   f"Invalid material file: {str(e)}")

    def add_array(self):
        """Add an array definition"""
        definition = self.array_def_entry.text().strip()
        if not definition:
            QMessageBox.warning(self, "Invalid Input", "Please enter an array definition.")
            return

        valid, message = self.array_table.validate_definition(definition)
        if not valid:
            QMessageBox.warning(self, "Invalid Array", message)
            return

        self.array_table.add_array(definition)
        self.array_def_entry.clear()

        count = self.array_table.rowCount()
        self.array_count_label.setText(f"{count}/20 arrays defined")

    def add_material(self):
        """Add base material to the library without selecting a specific variant"""
        if self.material_table.rowCount() >= 100:
            QMessageBox.warning(self, "Maximum Reached", "Cannot add more than 100 materials.")
            return

        label = self.label_entry.text().strip()
        selected_index = self.material_dropdown.currentIndex()

        if selected_index < 0:
            QMessageBox.warning(self, "No Material", "Please select a material.")
            return

        base_name = self.material_dropdown.currentText()
        material_data = self.material_dropdown.currentData()
        is_defect = self.defect_checkbox.isChecked()

        if not label:
            QMessageBox.warning(self, "Invalid Label", "Please enter a label (max 3 characters).")
            return

        if not self.material_table.is_label_unique(label):
            QMessageBox.warning(self, "Duplicate Label", f"Label '{label}' is already in use.")
            return

        # Handle different material types
        if material_data is None:
            QMessageBox.warning(self, "Invalid Material", "Selected material is not valid.")
            return

        # If it's a database material ID, use it directly
        if isinstance(material_data, str) and '|' in material_data:
            self.material_table.add_material(label, base_name, material_data, is_defect)
        else:
            # For other cases, store as-is
            self.material_table.add_material(label, base_name, material_data, is_defect)

        count = self.material_table.rowCount()
        self.material_count_label.setText(f"{count}/100 materials defined")

        self.label_entry.clear()
        self.defect_checkbox.setChecked(False)

        self.statusBar().showMessage(f"Material '{base_name}' added as '{label}'", 3000)

    def validate_filter(self):
        """Validate the filter definition"""
        filter_def = self.filter_entry.text().strip()
        if not filter_def:
            self.filter_status_label.setText("No filter defined")
            self.filter_status_label.setStyleSheet("color: red;")
            return

        try:
            # Basic validation - check if materials exist
            expanded = self.visualization_window.filter_visualizer.expand_filter_for_calculation(filter_def)
            materials = self.material_table.get_materials()

            missing = []
            for layer in expanded:
                if layer not in materials:
                    missing.append(layer)

            if missing:
                self.filter_status_label.setText(f"Missing materials: {', '.join(missing)}")
                self.filter_status_label.setStyleSheet("color: red;")
            else:
                self.filter_status_label.setText("Filter is valid")
                self.filter_status_label.setStyleSheet("color: green;")

        except Exception as e:
            self.filter_status_label.setText(f"Error: {str(e)}")
            self.filter_status_label.setStyleSheet("color: red;")

    def show_visualization(self):
        """Show the filter visualization window"""
        filter_def = self.filter_entry.text().strip()
        if filter_def:
            self.visualization_window.set_filter(filter_def)
            self.visualization_window.show()
            self.visualization_window.raise_()
        else:
            QMessageBox.warning(self, "No Filter", "Please define a filter first.")

    def update_filter_visualization(self):
        """Update the filter visualization"""
        filter_def = self.filter_entry.text().strip()
        self.visualization_window.set_filter(filter_def)

    def show_visualization_window(self):
        """Show the visualization window"""
        self.visualization_window.show()
        self.visualization_window.raise_()

    def calculate_filter(self):
        """Calculate the optical filter response"""
        try:
            filter_def = self.filter_entry.text().strip()
            if not filter_def:
                QMessageBox.warning(self, "No Filter", "Please define a filter.")
                return

            # Check materials compatibility
            incompatible = self.check_materials_compatibility()
            if incompatible:
                message = "The following materials have wavelength range issues:\n\n"
                for material_id, (min_range, max_range) in incompatible:
                    message += f"• {material_id}: {min_range:.0f}-{max_range:.0f} nm\n"
                message += "\nContinue anyway?"

                reply = QMessageBox.question(self, "Compatibility Warning", message)
                if reply != QMessageBox.Yes:
                    return

            # Build the stack
            start_wavelength = self.wavelength_start.value()
            end_wavelength = self.wavelength_end.value()
            steps = self.wavelength_steps.value()
            angle = self.incident_angle.value()
            default_thickness = self.default_thickness.value()

            wavelengths = np.linspace(start_wavelength, end_wavelength, steps)

            # Expand filter and build stack
            expanded_filter = self.visualization_window.filter_visualizer.expand_filter_for_calculation(filter_def)
            materials_dict = self.material_table.get_materials()
            array_thicknesses = self.array_table.get_array_thicknesses()

            stack = [(1.0, 0)]  # Air

            # Build array usage mapping
            array_usage_map = {}
            arrays = self.array_table.get_arrays()
            current_expanded_index = 0

            for component in filter_def.split():
                if component in arrays:
                    array_def = arrays[component]
                    array_layers = array_def.split("*")
                    for layer_pos, layer_name in enumerate(array_layers):
                        if current_expanded_index not in array_usage_map:
                            array_usage_map[current_expanded_index] = {
                                'array_id': component,
                                'layer_position': layer_pos,
                                'material': layer_name.strip()
                            }
                        current_expanded_index += 1
                else:
                    if current_expanded_index not in array_usage_map:
                        array_usage_map[current_expanded_index] = {
                            'array_id': None,
                            'layer_position': None,
                            'material': component
                        }
                    current_expanded_index += 1

            # Build the stack with correct thickness mapping
            for i, layer_material in enumerate(expanded_filter):
                layer_material = layer_material.strip()

                if layer_material in materials_dict:
                    _, material_data, is_defect = materials_dict[layer_material]

                    # Get thickness based on array mapping
                    layer_thickness = default_thickness

                    if i in array_usage_map:
                        mapping = array_usage_map[i]
                        array_id = mapping['array_id']
                        layer_pos = mapping['layer_position']

                        if array_id and layer_pos is not None:
                            array_thickness_data = array_thicknesses.get(array_id, {})
                            layer_key = f"layer_{layer_pos}"
                            layer_thickness = array_thickness_data.get(layer_key, default_thickness)

                    if isinstance(material_data, str) and material_data.startswith('{'):
                        try:
                            import json
                            variants_data = json.loads(material_data)
                            variants = variants_data.get("variants", [])
                            if variants:
                                first_variant = variants[0][0]
                                stack.append((first_variant, layer_thickness))
                            else:
                                raise ValueError(f"No variants found for {layer_material}")
                        except:
                            raise ValueError(f"Material {layer_material} has invalid variant data")
                    else:
                        stack.append((material_data, layer_thickness))
                else:
                    raise ValueError(f"Material {layer_material} not found in table")

            stack.append((3.5, 0))  # Silicon substrate

            self.tmm_calculator = TMM_Calculator()

            self.calculate_btn.setEnabled(False)
            self.calculate_btn.setText("Calculating...")

            self.statusBar().showMessage("Calculating...")
            self.worker = TMM_Worker(stack, wavelengths, angle)

            self.worker.finished.connect(self.calculation_finished)
            self.worker.error.connect(self.calculation_error)
            if hasattr(self.worker, 'progress'):
                self.worker.progress.connect(self.update_calculation_progress)

            self.worker.start()

        except ValueError as e:
            QMessageBox.critical(self, "Material Error", f"Cannot proceed:\n\n{str(e)}")
            self.calculate_btn.setEnabled(True)
            self.calculate_btn.setText("Calculate")
            self.statusBar().clearMessage()

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Calculation error: {str(e)}")
            import traceback
            traceback.print_exc()
            self.calculate_btn.setEnabled(True)
            self.calculate_btn.setText("Calculate")
            self.statusBar().clearMessage()

    def check_materials_compatibility(self):
        """Enhanced compatibility check with detailed wavelength range analysis"""
        start_wavelength = self.wavelength_start.value()
        end_wavelength = self.wavelength_end.value()

        filter_def = self.filter_entry.text().strip()
        expanded_filter = self.visualization_window.filter_visualizer.expand_filter_for_calculation(filter_def)
        expanded_filter = [layer for layer in expanded_filter if layer != "..."]

        materials_dict = self.material_table.get_materials()
        incompatible_materials = []

        for material_id in set(expanded_filter):
            if material_id in materials_dict:
                material_name, material_data, is_defect = materials_dict[material_id]

                if not isinstance(material_data, str):
                    continue

                if material_data.endswith('.yml'):
                    try:
                        import yaml
                        with open(material_data, 'r') as f:
                            yml_data = yaml.safe_load(f)

                        data_list = yml_data.get('DATA', [])
                        for data_item in data_list:
                            if data_item.get('type', '').startswith('tabulated'):
                                data_str = data_item.get('data', '')
                                if data_str:
                                    lines = data_str.strip().split('\n')
                                    wavelengths = []

                                    for line in lines:
                                        parts = line.strip().split()
                                        if len(parts) >= 1:
                                            try:
                                                wl = float(parts[0]) * 1000
                                                wavelengths.append(wl)
                                            except (ValueError, IndexError):
                                                continue

                                    if wavelengths:
                                        min_range = min(wavelengths)
                                        max_range = max(wavelengths)

                                        if start_wavelength < min_range or end_wavelength > max_range:
                                            incompatible_materials.append((material_id, (min_range, max_range)))
                                break

                    except Exception as e:
                        print(f"Error checking browsed material {material_id}: {e}")

                elif '{' in material_data:
                    try:
                        variants_data = json.loads(material_data)
                        variants = variants_data.get("variants", [])

                        best_variant = None
                        best_coverage = 0
                        best_range = (0, 0)

                        for variant_id, variant_name in variants:
                            min_range, max_range = self.material_api.get_wavelength_range(variant_id)

                            if min_range == 0 and max_range == 0:
                                continue

                            overlap_start = max(start_wavelength, min_range)
                            overlap_end = min(end_wavelength, max_range)
                            coverage = max(0, overlap_end - overlap_start)

                            if coverage > best_coverage:
                                best_coverage = coverage
                                best_variant = variant_id
                                best_range = (min_range, max_range)

                        if best_variant:
                            self.material_table.update_material_variant(material_id, best_variant)

                            min_range, max_range = best_range
                            if start_wavelength < min_range or end_wavelength > max_range:
                                incompatible_materials.append((material_id, best_range))
                        else:
                            incompatible_materials.append((material_id, (0, 0)))

                    except Exception as e:
                        print(f"Error selecting variant for {material_id}: {e}")

                elif '|' in material_data:
                    try:
                        min_range, max_range = self.material_api.get_wavelength_range(material_data)

                        if start_wavelength < min_range or end_wavelength > max_range:
                            incompatible_materials.append((material_id, (min_range, max_range)))

                    except Exception as e:
                        print(f"Error checking selected variant for {material_id}: {e}")

        return incompatible_materials

    def update_calculation_progress(self, percent):
        """Update the status bar with calculation progress"""
        self.statusBar().showMessage(f"Calculating: {percent}% complete")

    def calculation_finished(self, wavelengths, R_TM, problematic):
        """Handle the completion of TMM calculation"""
        self.last_calculation_data = {
            'wavelengths': wavelengths,
            'R_TM': R_TM
        }

        self.tmm_plots.plot_results(wavelengths, None, R_TM)

        self.statusBar().showMessage("Calculation complete", 3000)
        self.calculate_btn.setEnabled(True)
        self.calculate_btn.setText("Calculate")

    def calculation_error(self, error_msg):
        """Handle errors in the TMM calculation"""
        QMessageBox.critical(self, "Calculation Error", error_msg)

        self.statusBar().clearMessage()
        self.calculate_btn.setEnabled(True)
        self.calculate_btn.setText("Calculate")

    def save_project(self):
        """Save the current project"""
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Save Project", "", "JSON files (*.json)")

        if file_path:
            try:
                project_data = {
                    'materials': {},
                    'arrays': self.array_table.get_arrays(),
                    'array_thicknesses': self.array_table.get_array_thicknesses(),
                    'filter_definition': self.filter_entry.text(),
                    'wavelength_start': self.wavelength_start.value(),
                    'wavelength_end': self.wavelength_end.value(),
                    'wavelength_step': self.wavelength_step.value(),
                    'default_thickness': self.default_thickness.value(),
                    'angle': self.angle_input.value()
                }

                # Serialize materials
                materials = self.material_table.get_materials()
                for label, material in materials.items():
                    project_data['materials'][label] = MaterialHandler.serialize_material(material)

                with open(file_path, 'w') as f:
                    json.dump(project_data, f, indent=2)

                QMessageBox.information(self, "Save Successful",
                                       f"Project saved to {file_path}")

            except Exception as e:
                QMessageBox.critical(self, "Save Error",
                                   f"Failed to save project: {str(e)}")

    def load_project(self):
        """Load a project file"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Load Project", "", "JSON files (*.json)")

        if file_path:
            try:
                with open(file_path, 'r') as f:
                    project_data = json.load(f)

                # Clear current data
                self.material_table.setRowCount(0)
                self.array_table.setRowCount(0)

                # Load materials
                for label, material_data in project_data.get('materials', {}).items():
                    material = MaterialHandler.deserialize_material(material_data)
                    self.material_table.add_material(label, material[0], material[1], material[2])

                # Load arrays
                for array_def in project_data.get('arrays', {}).values():
                    self.array_table.add_array(array_def)

                # Load array thicknesses
                self.array_table.set_array_thicknesses(
                    project_data.get('array_thicknesses', {}))

                # Load other settings
                self.filter_entry.setText(project_data.get('filter_definition', ''))
                self.wavelength_start.setValue(project_data.get('wavelength_start', 400))
                self.wavelength_end.setValue(project_data.get('wavelength_end', 800))
                self.wavelength_step.setValue(project_data.get('wavelength_step', 1))
                self.default_thickness.setValue(project_data.get('default_thickness', 100))
                self.angle_input.setValue(project_data.get('angle', 0))

                QMessageBox.information(self, "Load Successful",
                                       f"Project loaded from {file_path}")

            except Exception as e:
                QMessageBox.critical(self, "Load Error",
                                   f"Failed to load project: {str(e)}")

    def export_results(self):
        """Export calculation results"""
        if not self.last_calculation_data:
            QMessageBox.warning(self, "No Results",
                               "No calculation results to export.")
            return

        file_path, _ = QFileDialog.getSaveFileName(
            self, "Export Results", "", "CSV files (*.csv)")

        if file_path:
            try:
                import csv
                with open(file_path, 'w', newline='') as f:
                    writer = csv.writer(f)
                    writer.writerow(['Wavelength (nm)', 'Reflection (%)'])

                    wavelengths = self.last_calculation_data['wavelengths']
                    R_TM = self.last_calculation_data['R_TM']

                    for wl, r in zip(wavelengths, R_TM):
                        writer.writerow([wl, r * 100])

                QMessageBox.information(self, "Export Successful",
                                       f"Results exported to {file_path}")

            except Exception as e:
                QMessageBox.critical(self, "Export Error",
                                   f"Failed to export results: {str(e)}")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = OpticalFilterApp()
    window.show()
    sys.exit(app.exec_())