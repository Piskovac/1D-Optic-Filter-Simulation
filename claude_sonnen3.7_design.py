import sys
import re
import random
import numpy as np
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                             QLabel, QLineEdit, QPushButton, QCheckBox, QTableWidget,
                             QTableWidgetItem, QScrollArea, QComboBox, QMessageBox,
                             QGroupBox, QSplitter, QFrame, QTabWidget, QHeaderView,
                             QColorDialog, QSlider, QFormLayout, QDoubleSpinBox, QSpinBox)
from PyQt5.QtCore import Qt, QSize, QRect, QPoint
from PyQt5.QtGui import QPainter, QColor, QBrush, QPen, QFont, QPalette
import matplotlib.pyplot as plt
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
import matplotlib.colors as mcolors
import requests
from io import StringIO


class MaterialSearchAPI:
    """Class to handle interaction with refractiveindex.info"""

    def __init__(self):
        self.base_url = "https://refractiveindex.info/database/api"
        # In a real implementation, you would need proper API access
        # or scraping mechanics for refractiveindex.info

    def search_materials(self, query):
        """
        Search for materials matching the query
        In a real implementation, this would connect to the actual database
        """
        # Simulate a search result for demonstration purposes
        # In real app, this would fetch from the actual API
        if not query:
            return []

        sample_materials = [
            "Silicon dioxide (SiO2) (Glass)",
            "Silicon (Si) (Crystalline)",
            "Silicon nitride (Si3N4)",
            "Silver (Ag)",
            "Gold (Au)",
            "Aluminum (Al)",
            "Titanium dioxide (TiO2)",
            "Zinc oxide (ZnO)",
            "Indium tin oxide (ITO)",
            "Gallium arsenide (GaAs)"
        ]

        # Filter materials that contain the query (case insensitive)
        return [m for m in sample_materials if query.lower() in m.lower()]

    def get_refractive_index(self, material, wavelength):
        """
        Get refractive index for a material at a specific wavelength
        In a real implementation, this would fetch actual data
        """
        # Simulate refractive index data for demonstration
        # In real app, this would use data from the database
        material_indices = {
            "Silicon dioxide (SiO2) (Glass)": lambda w: 1.45 + 0.01 * np.sin(w / 1000),
            "Silicon (Si) (Crystalline)": lambda w: 3.5 + 0.1 * np.sin(w / 1000),
            "Silicon nitride (Si3N4)": lambda w: 2.0 + 0.05 * np.sin(w / 1000),
            "Silver (Ag)": lambda w: complex(0.1, 4.0 + 0.1 * w / 1000),
            "Gold (Au)": lambda w: complex(0.2, 3.0 + 0.05 * w / 1000),
            "Aluminum (Al)": lambda w: complex(1.0, 7.0),
            "Titanium dioxide (TiO2)": lambda w: 2.4 + 0.1 * np.sin(w / 1000),
            "Zinc oxide (ZnO)": lambda w: 2.0 + 0.05 * np.sin(w / 1000),
            "Indium tin oxide (ITO)": lambda w: 1.8 + 0.01 * np.sin(w / 1000),
            "Gallium arsenide (GaAs)": lambda w: 3.3 + 0.1 * np.sin(w / 1000)
        }

        if material in material_indices:
            return material_indices[material](wavelength)
        return 1.0  # Default to air if material not found


class TMM:
    """Transfer Matrix Method calculations for multilayer optical structures"""

    @staticmethod
    def calculate_single_layer(n1, n2, d, wavelength, theta_inc, polarization='TE'):
        """
        Calculate reflection and transmission for a single interface

        Parameters:
        n1, n2: Refractive indices of the two materials
        d: Thickness of the layer (nm)
        wavelength: Wavelength of light (nm)
        theta_inc: Incident angle (radians)
        polarization: 'TE' or 'TM'

        Returns:
        r, t: Reflection and transmission coefficients
        """
        # Calculate angles using Snell's law
        theta_t = np.arcsin(n1 * np.sin(theta_inc) / n2)

        # Calculate phase
        k0 = 2 * np.pi / wavelength
        kz = n2 * k0 * np.cos(theta_t)
        phase = kz * d

        # Calculate Fresnel coefficients
        if polarization == 'TE':
            n1_cos = n1 * np.cos(theta_inc)
            n2_cos = n2 * np.cos(theta_t)
            r = (n1_cos - n2_cos) / (n1_cos + n2_cos)
            t = 2 * n1_cos / (n1_cos + n2_cos)
        else:  # TM polarization
            n1_cos = n1 * np.cos(theta_inc)
            n2_cos = n2 * np.cos(theta_t)
            r = (n2_cos - n1_cos) / (n2_cos + n1_cos)
            t = 2 * n1_cos / (n2_cos + n1_cos)

        # Create transfer matrix
        # Note: This is a simplified implementation
        # A complete implementation would use 2x2 matrices
        m11 = np.exp(-1j * phase)
        m12 = r * np.exp(1j * phase)
        m21 = r * np.exp(-1j * phase)
        m22 = np.exp(1j * phase)

        return r, t, np.array([[m11, m12], [m21, m22]])

    @staticmethod
    def calculate_stack(layers, wavelengths, theta_inc=0, polarization='TE'):
        """
        Calculate reflection and transmission for a multilayer stack

        Parameters:
        layers: List of (n, d) tuples for each layer
        wavelengths: Array of wavelengths (nm)
        theta_inc: Incident angle (radians)
        polarization: 'TE' or 'TM'

        Returns:
        R, T: Arrays of reflection and transmission coefficients
        """
        R = np.zeros(len(wavelengths), dtype=complex)
        T = np.zeros(len(wavelengths), dtype=complex)

        for i, wavelength in enumerate(wavelengths):
            # Initialize with identity matrix
            M = np.eye(2, dtype=complex)

            # Multiply through all layers
            for j in range(len(layers) - 1):
                n1, d1 = layers[j]
                n2, d2 = layers[j + 1]

                r, t, m = TMM.calculate_single_layer(n1, n2, d1, wavelength, theta_inc, polarization)
                M = np.dot(M, m)

            # Extract reflection and transmission
            r = M[1, 0] / M[0, 0]
            t = 1 / M[0, 0]

            R[i] = abs(r) ** 2

            # Calculate transmission
            n_first = layers[0][0]
            n_last = layers[-1][0]
            T[i] = abs(t) ** 2 * (n_last * np.cos(np.arcsin(n_first * np.sin(theta_inc) / n_last)) /
                                  (n_first * np.cos(theta_inc)))

        return R, T


class MaterialTable(QTableWidget):
    """Table widget for displaying the list of materials"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setColumnCount(4)
        self.setHorizontalHeaderLabels(["ID", "Material", "Defect", "Remove"])

        # Set column widths to better fit content
        self.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)  # ID column
        self.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)  # Material column
        self.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)  # Defect column
        self.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)  # Remove column

        self.setSelectionBehavior(QTableWidget.SelectRows)

        # Material colors (for visualization)
        self.material_colors = {}

    def add_material(self, label, material_name, is_defect=False):
        """Add a material to the table"""
        row = self.rowCount()
        self.insertRow(row)

        # Add the label
        label_item = QTableWidgetItem(label)
        label_item.setFlags(label_item.flags() & ~Qt.ItemIsEditable)
        self.setItem(row, 0, label_item)

        # Add the material name
        material_item = QTableWidgetItem(material_name)
        material_item.setFlags(material_item.flags() & ~Qt.ItemIsEditable)
        self.setItem(row, 1, material_item)

        # Add the defect status
        defect_item = QTableWidgetItem("Yes" if is_defect else "No")
        defect_item.setFlags(defect_item.flags() & ~Qt.ItemIsEditable)
        self.setItem(row, 2, defect_item)

        # Add the remove button
        remove_btn = QPushButton("×")
        remove_btn.setMaximumWidth(30)
        remove_btn.clicked.connect(lambda: self.removeRow(self.indexAt(remove_btn.pos()).row()))
        self.setCellWidget(row, 3, remove_btn)

        # Assign a color to this material (for visualization)
        if label not in self.material_colors:
            # Generate a random color but ensure it's visible
            # (not too light or too similar to existing colors)
            color = QColor(random.randint(20, 240), random.randint(20, 240), random.randint(20, 240))
            self.material_colors[label] = color

        return row

    def get_materials(self):
        """Return a dictionary of all materials {label: (name, is_defect)}"""
        materials = {}
        for row in range(self.rowCount()):
            label = self.item(row, 0).text()
            material_name = self.item(row, 1).text()
            is_defect = self.item(row, 2).text() == "Yes"
            materials[label] = (material_name, is_defect)
        return materials

    def get_material_colors(self):
        """Return the color mapping for materials"""
        return self.material_colors

    def is_label_unique(self, label):
        """Check if a label is already used"""
        for row in range(self.rowCount()):
            if self.item(row, 0).text() == label:
                return False
        return True


class ArrayTable(QTableWidget):
    """Table widget for displaying arrays of materials"""

    def __init__(self, material_table, parent=None):
        super().__init__(parent)
        self.setColumnCount(4)
        self.setHorizontalHeaderLabels(["ID", "Definition", "Layers", "Remove"])

        # Set column widths to better fit content
        self.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)  # ID column
        self.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)  # Definition column
        self.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)  # Layers column
        self.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)  # Remove column

        self.setSelectionBehavior(QTableWidget.SelectRows)
        self.material_table = material_table

    def add_array(self, definition):
        """Add an array to the table"""
        row = self.rowCount()
        self.insertRow(row)

        # Generate automatic ID (M1, M2, etc.)
        array_id = f"M{row + 1}"

        # Add the array ID
        id_item = QTableWidgetItem(array_id)
        id_item.setFlags(id_item.flags() & ~Qt.ItemIsEditable)
        self.setItem(row, 0, id_item)

        # Add the definition
        def_item = QTableWidgetItem(definition)
        def_item.setFlags(def_item.flags() & ~Qt.ItemIsEditable)
        self.setItem(row, 1, def_item)

        # Count layers
        layers = definition.split("*")
        layers_item = QTableWidgetItem(str(len(layers)))
        layers_item.setFlags(layers_item.flags() & ~Qt.ItemIsEditable)
        self.setItem(row, 2, layers_item)

        # Add the remove button
        remove_btn = QPushButton("×")
        remove_btn.setMaximumWidth(30)
        remove_btn.clicked.connect(lambda: self.removeRow(self.indexAt(remove_btn.pos()).row()))
        self.setCellWidget(row, 3, remove_btn)

        return row

    def get_arrays(self):
        """Return a dictionary of all arrays {array_id: definition}"""
        arrays = {}
        for row in range(self.rowCount()):
            array_id = self.item(row, 0).text()
            definition = self.item(row, 1).text()
            arrays[array_id] = definition
        return arrays

    def validate_definition(self, definition):
        """Validate an array definition against existing materials"""
        materials = self.material_table.get_materials()

        # Split by * to get individual materials
        parts = definition.split("*")

        for part in parts:
            part = part.strip()
            if part not in materials:
                return False, f"Material '{part}' not found"

            # Check if it's a defect
            if materials[part][1]:  # is_defect is True
                return False, f"Cannot use defect material '{part}' in array definition"

        return True, ""


class FilterVisualizerWindow(QMainWindow):
    """Floating window for visualizing the optical filter structure"""

    def __init__(self, material_table, array_table, parent=None):
        super().__init__(parent)
        self.material_table = material_table
        self.array_table = array_table
        self.setWindowTitle("Filter Visualization")
        self.setMinimumSize(800, 200)

        # Create central widget and layout
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)

        # Create visualizer
        self.filter_visualizer = FilterVisualizer(material_table, array_table)
        layout.addWidget(self.filter_visualizer)

        # Create control buttons
        control_layout = QHBoxLayout()

        # Refresh button
        refresh_btn = QPushButton("Refresh Visualization")
        refresh_btn.clicked.connect(self.refresh_visualization)
        control_layout.addWidget(refresh_btn)

        # Zoom controls
        control_layout.addWidget(QLabel("Zoom:"))
        self.zoom_slider = QSlider(Qt.Horizontal)
        self.zoom_slider.setMinimum(5)
        self.zoom_slider.setMaximum(50)
        self.zoom_slider.setValue(20)
        self.zoom_slider.valueChanged.connect(self.filter_visualizer.update)
        control_layout.addWidget(self.zoom_slider)

        layout.addLayout(control_layout)

    def set_filter(self, filter_definition):
        """Set the filter definition to visualize"""
        self.filter_visualizer.set_filter(filter_definition)

    def refresh_visualization(self):
        """Refresh the visualization"""
        self.filter_visualizer.update()


class FilterVisualizer(QWidget):
    """Widget for visualizing the optical filter structure"""

    def __init__(self, material_table, array_table, parent=None):
        super().__init__(parent)
        self.material_table = material_table
        self.array_table = array_table
        self.filter_definition = ""
        self.expanded_definition = []
        self.setMinimumHeight(100)

        # Setup layout
        layout = QVBoxLayout(self)

        # Visualization area
        self.visual_area = QWidget()
        self.visual_area.setMinimumHeight(80)
        self.visual_area.paintEvent = self.paintVisualization

        # Scroll area for the visualization
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setWidget(self.visual_area)

        layout.addWidget(scroll_area)

    def set_filter(self, filter_definition):
        """Set the filter definition to visualize"""
        self.filter_definition = filter_definition
        self.expanded_definition = self.expand_filter(filter_definition)
        self.update()

    def expand_filter(self, filter_definition):
        """Expand the filter definition into a list of individual layers"""
        if not filter_definition:
            return []

        arrays = self.array_table.get_arrays()

        # Pattern to match array repetition like (M1)^5
        pattern = r'\(([^)]+)\)\^(\d+)'

        # Replace array repetitions with expanded form
        while re.search(pattern, filter_definition):
            match = re.search(pattern, filter_definition)
            array_id = match.group(1)
            repetitions = int(match.group(2))

            # Limit visualization to 3 repetitions plus ...
            if repetitions > 3:
                replacement = f"{array_id}*{array_id}*{array_id}*..."
            else:
                replacement = "*".join([array_id] * repetitions)

            filter_definition = filter_definition[:match.start()] + replacement + filter_definition[match.end():]

        # Split by * to get individual components
        components = filter_definition.split("*")
        expanded = []

        for component in components:
            component = component.strip()
            if component == "...":
                expanded.append("...")
            elif component in arrays:
                # Expand array definition
                array_def = arrays[component]
                array_components = array_def.split("*")
                expanded.extend(array_components)
            else:
                expanded.append(component)

        return expanded

    def paintVisualization(self, event):
        """Paint the visualization of the filter structure"""
        if not self.expanded_definition:
            return

        painter = QPainter(self.visual_area)
        painter.setRenderHint(QPainter.Antialiasing)

        # Get material colors
        colors = self.material_table.get_material_colors()

        # Calculate rectangle width based on zoom value passed from parent
        zoom_value = 20  # Default value
        if hasattr(self.parent(), 'zoom_slider'):
            zoom_value = self.parent().zoom_slider.value()
        rect_width = zoom_value

        # Calculate total width needed
        total_width = len(self.expanded_definition) * rect_width
        self.visual_area.setMinimumWidth(total_width)

        # Rectangle height
        rect_height = self.visual_area.height() - 10
        y_pos = 5

        for i, layer in enumerate(self.expanded_definition):
            x_pos = i * rect_width

            if layer == "...":
                # Draw ellipsis
                painter.setPen(QPen(Qt.black, 2))
                painter.drawText(QRect(x_pos, y_pos, rect_width, rect_height),
                                 Qt.AlignCenter, "...")
            else:
                # Draw rectangle for the layer
                if layer in colors:
                    painter.setBrush(QBrush(colors[layer]))
                else:
                    # Use a default color if not found
                    painter.setBrush(QBrush(Qt.lightGray))

                painter.setPen(QPen(Qt.black, 1))
                painter.drawRect(x_pos, y_pos, rect_width, rect_height)

                # Draw the layer label
                painter.setPen(Qt.black)
                font = painter.font()
                font.setPointSize(8)
                painter.setFont(font)
                painter.drawText(QRect(x_pos, y_pos, rect_width, 20),
                                 Qt.AlignCenter, layer)


class TMM_Plots(QWidget):
    """Widget for displaying TMM calculation results"""

    def __init__(self, parent=None):
        super().__init__(parent)

        # Setup layout
        layout = QVBoxLayout(self)

        # Create figure and canvas for plots
        self.figure = Figure(figsize=(10, 4))
        self.canvas = FigureCanvas(self.figure)
        self.figure.subplots_adjust(wspace=0.3)

        # Create TE and TM subplots
        self.ax_te = self.figure.add_subplot(121)
        self.ax_tm = self.figure.add_subplot(122)

        # Set titles and labels
        self.ax_te.set_title('TE Mode')
        self.ax_te.set_xlabel('Wavelength (nm)')
        self.ax_te.set_ylabel('Reflection')
        self.ax_te.set_ylim(0, 1)

        self.ax_tm.set_title('TM Mode')
        self.ax_tm.set_xlabel('Wavelength (nm)')
        self.ax_tm.set_ylabel('Reflection')
        self.ax_tm.set_ylim(0, 1)

        layout.addWidget(self.canvas)

    def plot_results(self, wavelengths, R_TE, R_TM):
        """Plot the reflection spectra for TE and TM modes"""
        # Clear previous plots
        self.ax_te.clear()
        self.ax_tm.clear()

        # Set titles and labels again
        self.ax_te.set_title('TE Mode')
        self.ax_te.set_xlabel('Wavelength (nm)')
        self.ax_te.set_ylabel('Reflection')
        self.ax_te.set_ylim(0, 1)

        self.ax_tm.set_title('TM Mode')
        self.ax_tm.set_xlabel('Wavelength (nm)')
        self.ax_tm.set_ylabel('Reflection')
        self.ax_tm.set_ylim(0, 1)

        # Plot the data
        self.ax_te.plot(wavelengths, R_TE, 'b-')
        self.ax_tm.plot(wavelengths, R_TM, 'r-')

        # Refresh canvas
        self.canvas.draw()


class OpticalFilterApp(QMainWindow):
    """Main application window"""

    def __init__(self):
        super().__init__()

        # Initialize API for material search
        self.material_api = MaterialSearchAPI()

        # Setup UI
        self.setup_ui()

        # Set window properties
        self.setWindowTitle("Optical Filter Designer & TMM Calculator")
        self.setMinimumSize(900, 700)

        self.show()

    def setup_ui(self):
        """Setup the user interface"""
        # Create central widget and main layout
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)

        # Create horizontal layout for top three sections
        top_sections_layout = QHBoxLayout()

        # Create top sections side by side
        self.create_material_section(top_sections_layout)
        self.create_array_section(top_sections_layout)
        self.create_filter_section(top_sections_layout)

        # Add top layout to main layout
        main_layout.addLayout(top_sections_layout)

        # Create remaining section (TMM calculation) - removed visualization section from main UI
        self.create_calculation_section(main_layout)

        # Create visualization window (but don't show it yet)
        self.visualization_window = FilterVisualizerWindow(self.material_table, self.array_table, self)

    def create_material_section(self, parent_layout):
        """Create the material definition section"""
        group_box = QGroupBox("Material Library")
        group_box.setMinimumWidth(300)  # Ensure minimum width when in horizontal layout
        layout = QVBoxLayout(group_box)

        # Search and add controls
        controls_layout = QHBoxLayout()

        # Search bar
        self.search_field = QLineEdit()
        self.search_field.setPlaceholderText("Search materials...")
        self.search_field.textChanged.connect(self.search_materials)
        controls_layout.addWidget(QLabel("Search:"))
        controls_layout.addWidget(self.search_field)

        # Material dropdown
        self.material_dropdown = QComboBox()
        self.material_dropdown.setMinimumWidth(200)
        controls_layout.addWidget(self.material_dropdown)

        # Label entry
        self.label_entry = QLineEdit()
        self.label_entry.setMaxLength(3)
        self.label_entry.setMaximumWidth(50)
        controls_layout.addWidget(QLabel("ID:"))
        controls_layout.addWidget(self.label_entry)

        # Defect checkbox
        self.defect_checkbox = QCheckBox("Defect")
        controls_layout.addWidget(self.defect_checkbox)

        # Add material button
        self.add_material_btn = QPushButton("Add Material")
        self.add_material_btn.clicked.connect(self.add_material)
        controls_layout.addWidget(self.add_material_btn)

        layout.addLayout(controls_layout)

        # Material table
        self.material_table = MaterialTable()
        layout.addWidget(self.material_table)

        # Material count label
        self.material_count_label = QLabel("0/100 materials defined")
        layout.addWidget(self.material_count_label)

        parent_layout.addWidget(group_box)

    def create_array_section(self, parent_layout):
        """Create the array definition section"""
        group_box = QGroupBox("Array Definitions")
        group_box.setMinimumWidth(300)  # Ensure minimum width when in horizontal layout
        layout = QVBoxLayout(group_box)

        # Definition and add controls
        controls_layout = QHBoxLayout()

        # Definition entry
        self.array_def_entry = QLineEdit()
        self.array_def_entry.setPlaceholderText("Example: A*B*Si")
        controls_layout.addWidget(QLabel("Definition:"))
        controls_layout.addWidget(self.array_def_entry, 1)

        # Add array button
        self.add_array_btn = QPushButton("Add Array")
        self.add_array_btn.clicked.connect(self.add_array)
        controls_layout.addWidget(self.add_array_btn)

        layout.addLayout(controls_layout)

        # Warning label
        self.array_warning_label = QLabel("")
        self.array_warning_label.setStyleSheet("color: red;")
        layout.addWidget(self.array_warning_label)

        # Array table
        self.array_table = ArrayTable(self.material_table)
        layout.addWidget(self.array_table)

        # Array count label
        self.array_count_label = QLabel("0/20 arrays defined")
        layout.addWidget(self.array_count_label)

        parent_layout.addWidget(group_box)

    def create_filter_section(self, parent_layout):
        """Create the optical filter definition section"""
        group_box = QGroupBox("Optical Filter Structure")
        group_box.setMinimumWidth(300)  # Ensure minimum width when in horizontal layout
        layout = QVBoxLayout(group_box)

        # Filter definition controls
        controls_layout = QHBoxLayout()

        # Filter entry
        self.filter_entry = QLineEdit()
        self.filter_entry.setPlaceholderText("Example: [(M1)^5*D*(M2)^3*B]")
        controls_layout.addWidget(QLabel("Filter:"))
        controls_layout.addWidget(self.filter_entry, 1)

        # Validate button
        self.validate_filter_btn = QPushButton("Validate")
        self.validate_filter_btn.clicked.connect(self.validate_filter)
        controls_layout.addWidget(self.validate_filter_btn)

        layout.addLayout(controls_layout)

        # Status label
        self.filter_status_label = QLabel("")
        layout.addWidget(self.filter_status_label)

        # Add syntax help text
        help_text = QLabel("Syntax: Use (M1)^5 for repetition, * to combine layers")
        help_text.setWordWrap(True)
        help_text.setStyleSheet("color: #666; font-style: italic;")
        layout.addWidget(help_text)

        # Add button to show filter visualization
        self.show_visualization_btn = QPushButton("Show Filter")
        self.show_visualization_btn.clicked.connect(self.show_visualization)
        layout.addWidget(self.show_visualization_btn)

        # Add stretching space to fill the vertical area
        layout.addStretch()

        parent_layout.addWidget(group_box)

    def create_visualization_section(self, parent_layout):
        """Create button to open the filter visualization window"""
        # Create button to open visualization window
        self.show_visualization_btn = QPushButton("Show Filter Visualization")
        self.show_visualization_btn.clicked.connect(self.show_visualization)
        parent_layout.addWidget(self.show_visualization_btn)

        # Create visualization window (but don't show it yet)
        self.visualization_window = FilterVisualizerWindow(self.material_table, self.array_table, self)

    def show_visualization(self):
        """Show the filter visualization window"""
        filter_def = self.filter_entry.text().strip()

        # Validate filter before showing visualization
        if not filter_def:
            QMessageBox.warning(self, "No Filter", "Please define a filter first.")
            return

        # Validate the filter definition
        if not self.validate_filter():
            QMessageBox.warning(self, "Invalid Filter", "Please correct the filter definition first.")
            return

        # Update the visualization and show the window
        self.visualization_window.set_filter(filter_def)
        self.visualization_window.show()
        self.visualization_window.activateWindow()  # Bring to front

    def create_calculation_section(self, parent_layout):
        """Create the TMM calculation section"""
        group_box = QGroupBox("TMM Calculation")
        layout = QHBoxLayout(group_box)  # Changed to horizontal layout

        # Left side: Parameters
        params_widget = QWidget()
        params_layout = QVBoxLayout(params_widget)
        params_layout.setContentsMargins(0, 0, 0, 0)

        # Parameters form
        form_layout = QFormLayout()

        # Wavelength range
        self.wavelength_start = QDoubleSpinBox()
        self.wavelength_start.setRange(200, 2000)
        self.wavelength_start.setValue(400)
        self.wavelength_start.setSuffix(" nm")

        self.wavelength_end = QDoubleSpinBox()
        self.wavelength_end.setRange(200, 2000)
        self.wavelength_end.setValue(800)
        self.wavelength_end.setSuffix(" nm")

        self.wavelength_steps = QSpinBox()
        self.wavelength_steps.setRange(10, 1000)
        self.wavelength_steps.setValue(100)

        wavelength_layout = QHBoxLayout()
        wavelength_layout.addWidget(self.wavelength_start)
        wavelength_layout.addWidget(QLabel("to"))
        wavelength_layout.addWidget(self.wavelength_end)
        wavelength_layout.addWidget(QLabel("Steps:"))
        wavelength_layout.addWidget(self.wavelength_steps)

        form_layout.addRow("Wavelength:", wavelength_layout)

        # Incident angle
        self.incident_angle = QDoubleSpinBox()
        self.incident_angle.setRange(0, 89)
        self.incident_angle.setValue(0)
        self.incident_angle.setSuffix("°")
        form_layout.addRow("Incident Angle:", self.incident_angle)

        # Default thickness
        self.default_thickness = QDoubleSpinBox()
        self.default_thickness.setRange(1, 1000)
        self.default_thickness.setValue(100)
        self.default_thickness.setSuffix(" nm")
        form_layout.addRow("Default Layer Thickness:", self.default_thickness)

        params_layout.addLayout(form_layout)

        # Calculate button
        self.calculate_btn = QPushButton("Calculate")
        self.calculate_btn.setStyleSheet("font-weight: bold; padding: 8px;")
        self.calculate_btn.clicked.connect(self.calculate_tmm)
        params_layout.addWidget(self.calculate_btn)

        # Add stretching space
        params_layout.addStretch()

        # Right side: TMM result plots
        self.tmm_plots = TMM_Plots()

        # Add both sides to the main layout
        layout.addWidget(params_widget, 1)  # Parameters take 1/3 of space
        layout.addWidget(self.tmm_plots, 2)  # Plots take 2/3 of space

        parent_layout.addWidget(group_box)

    def search_materials(self):
        """Search materials from the database"""
        query = self.search_field.text()
        results = self.material_api.search_materials(query)

        self.material_dropdown.clear()
        for material in results:
            self.material_dropdown.addItem(material)

    def add_material(self):
        """Add a material to the library"""
        # Check if we've reached the maximum
        if self.material_table.rowCount() >= 100:
            QMessageBox.warning(self, "Maximum Reached", "Cannot add more than 100 materials.")
            return

        # Get values from inputs
        label = self.label_entry.text().strip()
        material_name = self.material_dropdown.currentText()
        is_defect = self.defect_checkbox.isChecked()

        # Validate label
        if not label:
            QMessageBox.warning(self, "Invalid Label", "Please enter a label (max 3 characters).")
            return

        if not self.material_table.is_label_unique(label):
            QMessageBox.warning(self, "Duplicate Label", f"Label '{label}' is already in use.")
            return

        # Validate material selection
        if not material_name:
            QMessageBox.warning(self, "No Material", "Please select a material.")
            return

        # Add to table
        self.material_table.add_material(label, material_name, is_defect)

        # Update the count label
        count = self.material_table.rowCount()
        self.material_count_label.setText(f"{count}/100 materials defined")

        # Clear inputs
        self.label_entry.clear()
        self.defect_checkbox.setChecked(False)

    def add_array(self):
        """Add an array to the definitions"""
        # Check if we've reached the maximum
        if self.array_table.rowCount() >= 20:
            QMessageBox.warning(self, "Maximum Reached", "Cannot add more than 20 arrays.")
            return

        # Get the definition
        definition = self.array_def_entry.text().strip()

        # Validate definition
        if not definition:
            QMessageBox.warning(self, "Empty Definition", "Please enter an array definition.")
            return

        # Check if all materials exist and aren't defects
        valid, message = self.array_table.validate_definition(definition)
        if not valid:
            self.array_warning_label.setText(message)
            return

        # Clear any previous warnings
        self.array_warning_label.setText("")

        # Add to table
        self.array_table.add_array(definition)

        # Update the count label
        count = self.array_table.rowCount()
        self.array_count_label.setText(f"{count}/20 arrays defined")

        # Clear input
        self.array_def_entry.clear()

    def validate_filter(self):
        """Validate the optical filter definition"""
        filter_def = self.filter_entry.text().strip()

        if not filter_def:
            self.filter_status_label.setText("Please enter a filter definition.")
            self.filter_status_label.setStyleSheet("color: red;")
            return False  # Return validation result

        # Basic syntax check
        arrays = self.array_table.get_arrays()
        materials = self.material_table.get_materials()

        # Regex to check for valid pattern: [(M1)^5*D*(M2)^3*B]
        valid_syntax = True

        # Check if all referenced arrays and materials exist
        pattern = r'\(([^)]+)\)\^(\d+)|([A-Za-z0-9]{1,3})'
        matches = re.findall(pattern, filter_def)

        for match in matches:
            array_id = match[0]
            repetitions = match[1]
            single_material = match[2]

            if array_id and array_id not in arrays:
                valid_syntax = False
                self.filter_status_label.setText(f"Array '{array_id}' not found.")
                break

            if single_material and single_material not in materials and single_material != "":
                valid_syntax = False
                self.filter_status_label.setText(f"Material '{single_material}' not found.")
                break

            if repetitions and not repetitions.isdigit():
                valid_syntax = False
                self.filter_status_label.setText(f"Invalid repetition count '{repetitions}'.")
                break

        if valid_syntax:
            self.filter_status_label.setText("Filter definition is valid.")
            self.filter_status_label.setStyleSheet("color: green;")
            return True
        else:
            self.filter_status_label.setStyleSheet("color: red;")
            return False

    def calculate_tmm(self):
        """Calculate and display TMM results"""
        filter_def = self.filter_entry.text().strip()

        if not filter_def:
            QMessageBox.warning(self, "No Filter", "Please define and validate an optical filter first.")
            return

        # Get wavelength range
        start = self.wavelength_start.value()
        end = self.wavelength_end.value()
        steps = self.wavelength_steps.value()
        wavelengths = np.linspace(start, end, steps)

        # Get incident angle (convert to radians)
        angle = self.incident_angle.value() * np.pi / 180

        # Get default thickness
        default_thickness = self.default_thickness.value()

        try:
            # Build the layer structure - use the filter_visualizer from the visualization window
            expanded_filter = self.visualization_window.filter_visualizer.expand_filter(filter_def)

            # Remove any "..." from the expanded definition
            expanded_filter = [layer for layer in expanded_filter if layer != "..."]

            # Get material data
            materials_dict = self.material_table.get_materials()

            # Convert to layer structure for TMM
            layers = []

            # Add incident medium (air)
            layers.append((1.0, 0))  # n=1.0, d=0 (semi-infinite)

            # Add each layer from the filter
            for material_id in expanded_filter:
                if material_id in materials_dict:
                    material_name = materials_dict[material_id][0]
                    # Get refractive index (this would use the actual material data in a real app)
                    n = self.material_api.get_refractive_index(material_name, wavelengths[0])
                    layers.append((n, default_thickness))

            # Add exit medium (substrate, using silicon as example)
            layers.append((3.5, 0))  # Silicon substrate, semi-infinite

            # Calculate for TE and TM modes
            R_TE, T_TE = TMM.calculate_stack(layers, wavelengths, angle, 'TE')
            R_TM, T_TM = TMM.calculate_stack(layers, wavelengths, angle, 'TM')

            # Update plots
            self.tmm_plots.plot_results(wavelengths, R_TE, R_TM)

        except Exception as e:
            QMessageBox.critical(self, "Calculation Error", f"Error in TMM calculation: {str(e)}")
            # Show full exception details in console for debugging
            import traceback
            traceback.print_exc()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = OpticalFilterApp()
    sys.exit(app.exec_())