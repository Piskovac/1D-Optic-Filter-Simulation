import sys
import re
import random
import numpy as np
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                             QLabel, QLineEdit, QPushButton, QCheckBox, QTableWidget,
                             QTableWidgetItem, QScrollArea, QComboBox, QMessageBox,
                             QGroupBox, QSplitter, QFrame, QTabWidget, QHeaderView,
                             QColorDialog, QSlider, QFormLayout, QDoubleSpinBox, QSpinBox)
from PyQt5.QtCore import Qt, QSize, QRect, QPoint, QThread, pyqtSignal
from PyQt5.QtGui import QPainter, QColor, QBrush, QPen, QFont, QPalette
import matplotlib.pyplot as plt
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
import traceback


class MaterialSearchAPI:
    """Class to handle interaction with refractiveindex.info database"""

    def __init__(self):
        # Import the refractiveindex package
        try:
            from refractiveindex import RefractiveIndexMaterial
            import refractiveindex.refractiveindex as ri
            self.RefractiveIndexMaterial = RefractiveIndexMaterial
            self.RefractiveIndex = ri.RefractiveIndex
            self.initialized = True

            # Initialize the database
            self.database = self.RefractiveIndex()
            print("Refractiveindex.info database loaded successfully!")
        except ImportError:
            print("Error: refractiveindex package not found. Install with 'pip install refractiveindex'")
            self.initialized = False
            sys.exit(1)  # Exit if refractiveindex is not available

    def search_materials(self, query):
        """
        Search for materials matching the query in the database
        """
        if not query or not self.initialized:
            return []

        results = []

        # Search through the catalog
        for shelf in self.database.catalog:
            if 'DIVIDER' in shelf:
                continue

            shelf_name = shelf.get('name', shelf.get('SHELF', ''))
            shelf_id = shelf.get('SHELF', '')

            for book in shelf.get('content', []):
                if 'DIVIDER' in book:
                    continue

                book_name = book.get('name', book.get('BOOK', ''))
                book_id = book.get('BOOK', '')

                # Check if book name matches query
                if query.lower() in book_id.lower() or query.lower() in book_name.lower():
                    # Add all pages from this book
                    for page in book.get('content', []):
                        if 'DIVIDER' in page:
                            continue

                        page_name = page.get('name', page.get('PAGE', ''))
                        page_id = page.get('PAGE', '')

                        # Skip if page_id is empty
                        if not page_id:
                            continue

                        material_id = f"{shelf_id}|{book_id}|{page_id}"
                        material_name = f"{book_name} - {page_name}"
                        results.append((material_id, material_name))

                # If not, check individual pages
                else:
                    for page in book.get('content', []):
                        if 'DIVIDER' in page:
                            continue

                        page_name = page.get('name', page.get('PAGE', ''))
                        page_id = page.get('PAGE', '')

                        # Skip if page_id is empty
                        if not page_id:
                            continue

                        if query.lower() in page_id.lower() or query.lower() in page_name.lower():
                            material_id = f"{shelf_id}|{book_id}|{page_id}"
                            material_name = f"{book_name} - {page_name}"
                            results.append((material_id, material_name))

        return results

    def get_material_details(self, material_id):
        """Get shelf, book, page from material_id"""
        if not material_id or not self.initialized:
            return None, None, None

        parts = material_id.split('|')
        if len(parts) == 3:
            return parts[0], parts[1], parts[2]
        return None, None, None

    def get_wavelength_range(self, material_id):
        """Get the valid wavelength range for a material"""
        if not material_id or not self.initialized:
            return (0, 0)

        try:
            shelf, book, page = self.get_material_details(material_id)
            if shelf and book and page:
                material_data = self.RefractiveIndexMaterial(shelf=shelf, book=book, page=page)
                material = material_data.material

                # Check refractive index range
                if material.refractiveIndex:
                    range_min = material.refractiveIndex.rangeMin * 1000  # Convert from μm to nm
                    range_max = material.refractiveIndex.rangeMax * 1000  # Convert from μm to nm
                    return (range_min, range_max)

            return (0, 0)

        except Exception as e:
            print(f"Error getting wavelength range for {material_id}: {e}")
            return (0, 0)

    def get_refractive_index(self, material_id, wavelength):
        """
        Get refractive index for a material at a specific wavelength
        """
        if not material_id or not self.initialized:
            return 1.0  # Default to air if not initialized

        try:
            shelf, book, page = self.get_material_details(material_id)
            if shelf and book and page:
                # Get the material data
                material_data = self.RefractiveIndexMaterial(shelf=shelf, book=book, page=page)

                # Get refractive index at the specified wavelength
                n = material_data.get_refractive_index(wavelength)

                # Check if the material has extinction coefficient (k)
                try:
                    k = material_data.get_extinction_coefficient(wavelength)
                    if k > 0:
                        return complex(n, k)
                    return n
                except:
                    return n
            else:
                return 1.0  # Default to air if material details not found

        except Exception as e:
            print(f"Error getting refractive index for {material_id}: {e}")
            return 1.0  # Default to air if there's an error


class TMM_Calculator:

    def __init__(self):
        self.material_cache = {}  # Cache for material refractive indices

    def get_refractive_index(self, material_id, wavelength):
        """
        Get refractive index with caching to improve performance
        """
        # If it's a direct numerical value, return it
        if not isinstance(material_id, str):
            return material_id

        # Check if we have already computed this value
        cache_key = f"{material_id}_{wavelength}"
        if cache_key in self.material_cache:
            return self.material_cache[cache_key]

        # Otherwise, compute and cache it
        try:
            from refractiveindex import RefractiveIndexMaterial
            shelf, book, page = material_id.split('|')
            material_obj = RefractiveIndexMaterial(shelf=shelf, book=book, page=page)

            # Get refractive index
            n = material_obj.get_refractive_index(wavelength)

            # Try to get extinction coefficient if available
            try:
                k = material_obj.get_extinction_coefficient(wavelength)
                if k > 0:
                    n = complex(n, k)
            except:
                pass

            # Cache the result
            self.material_cache[cache_key] = n
            return n

        except Exception as e:
            # Store the error in cache to avoid repeated attempts
            self.material_cache[cache_key] = 1.0
            return 1.0  # Default to air

    def precompute_indices(self, stack, wavelengths):
        """
        Precompute all refractive indices for the stack at all wavelengths
        to avoid repeatedly creating RefractiveIndexMaterial objects

        Returns: dictionary of problematic materials with their wavelength ranges
        """
        from refractiveindex import RefractiveIndexMaterial

        # First, identify all unique material IDs
        material_ids = set()
        for material, _ in stack:
            if isinstance(material, str):
                material_ids.add(material)

        # Track problematic materials
        problematic = {}

        # Precompute all indices
        for material_id in material_ids:
            try:
                # Create the material object just once
                shelf, book, page = material_id.split('|')
                material_obj = RefractiveIndexMaterial(shelf=shelf, book=book, page=page)

                # Get the valid wavelength range
                range_min = material_obj.material.refractiveIndex.rangeMin * 1000  # μm to nm
                range_max = material_obj.material.refractiveIndex.rangeMax * 1000  # μm to nm

                # Check if wavelengths are within range
                if np.min(wavelengths) < range_min or np.max(wavelengths) > range_max:
                    problematic[material_id] = (range_min, range_max)

                # Still try to compute for all wavelengths in range
                for wavelength in wavelengths:
                    if range_min <= wavelength <= range_max:
                        try:
                            # Get refractive index
                            n = material_obj.get_refractive_index(wavelength)

                            # Try to get extinction coefficient if available
                            try:
                                k = material_obj.get_extinction_coefficient(wavelength)
                                if k > 0:
                                    n = complex(n, k)
                            except:
                                pass

                            # Cache the result
                            cache_key = f"{material_id}_{wavelength}"
                            self.material_cache[cache_key] = n
                        except:
                            # Skip wavelengths that fail
                            pass

            except Exception as e:
                # Record error but continue with other materials
                print(f"Error precomputing indices for {material_id}: {e}")

        return problematic

    def calculate_reflection(self, stack, wavelengths, angle=0, show_progress=None):
        """
        Calculate reflection for TM polarization only

        Parameters:
        stack: List of (material, thickness) tuples
        wavelengths: Array of wavelengths in nm
        angle: Incident angle in radians
        show_progress: Optional callback function to show progress (percent)

        Returns:
        R, problematic: Arrays of reflection coefficients and dict of problematic materials
        """
        from PyTMM.transferMatrix import TransferMatrix, Polarization, solvePropagation

        # Precompute all material indices to avoid repeated material object creation
        problematic = self.precompute_indices(stack, wavelengths)

        # Initialize result arrays
        R = np.zeros(len(wavelengths))
        T = np.zeros(len(wavelengths))

        # Always use TM polarization (p)
        pol = Polarization.p

        # Calculate for each wavelength
        for i, wavelength in enumerate(wavelengths):
            # Build layers with refractive indices at current wavelength
            indices = []
            thicknesses = []

            # Get all indices and thicknesses
            for material, thickness in stack:
                n = self.get_refractive_index(material, wavelength)
                indices.append(n)
                thicknesses.append(thickness)

            # Create matrices
            matrices = []

            # Add interfaces and propagation for all layers
            for j in range(len(indices) - 1):
                n1 = indices[j]
                n2 = indices[j + 1]
                d = thicknesses[j]

                # Interface
                boundary = TransferMatrix.boundingLayer(n1, n2, angle, pol)
                matrices.append(boundary)

                # Propagation (except for the last layer)
                if j < len(indices) - 2:
                    propagation = TransferMatrix.propagationLayer(n2, thicknesses[j + 1], wavelength, angle, pol)
                    matrices.append(propagation)

            # Create structure and solve
            if matrices:
                structure = TransferMatrix.structure(*matrices)
                r, t = solvePropagation(structure)

                R[i] = np.abs(r) ** 2
                T[i] = np.abs(t) ** 2

            # Update progress if callback provided
            if show_progress is not None and i % 10 == 0:
                progress = int((i + 1) / len(wavelengths) * 100)
                show_progress(progress)

        return R, problematic


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

    def add_material(self, label, material_name, material_id, is_defect=False):
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
        material_item.setData(Qt.UserRole, material_id)  # Store material_id as user data
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
        """Return a dictionary of all materials {label: (name, material_id, is_defect)}"""
        materials = {}
        for row in range(self.rowCount()):
            label = self.item(row, 0).text()
            material_name = self.item(row, 1).text()
            material_id = self.item(row, 1).data(Qt.UserRole)
            is_defect = self.item(row, 2).text() == "Yes"
            materials[label] = (material_name, material_id, is_defect)
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

            # Check if it's a defect - this check was previously in the TMM calculation
            if materials[part][2]:  # is_defect is True
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

        # Create scroll area for horizontal scrolling
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

        # Setup layout
        layout = QVBoxLayout(self)
        self.setLayout(layout)

        # We don't need the nested scroll area anymore since parent has one
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

        # Get material colors
        colors = self.material_table.get_material_colors()

        # Use fixed rect width since zoom slider is removed
        rect_width = 30

        # Calculate total width needed
        total_width = len(self.expanded_definition) * rect_width
        self.setMinimumWidth(total_width)

        # Rectangle height
        rect_height = self.height() - 10
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


class TMM_Plots(QWidget):
    """Widget for displaying TMM calculation results with single-type data"""

    def __init__(self, parent=None):
        super().__init__(parent)

        # Setup layout
        layout = QVBoxLayout(self)

        # Create figure and canvas for plots - no toolbar
        self.figure = Figure(figsize=(10, 4))
        self.canvas = FigureCanvas(self.figure)

        # Create single plot
        self.ax = self.figure.add_subplot(111)

        # Set initial titles and labels
        self.ax.set_title('Reflection Spectrum')
        self.ax.set_xlabel('Wavelength (nm)')
        self.ax.set_ylabel('Reflection (dB)')

        # Add canvas to layout
        layout.addWidget(self.canvas)

    def plot_results(self, wavelengths, R_TE, R_TM):
        """Plot the reflection spectrum with TM data only but dual-style line"""
        # Clear previous plot
        self.ax.clear()

        # Set titles and labels
        self.ax.set_title('Reflection Spectrum')
        self.ax.set_xlabel('Wavelength (nm)')
        self.ax.set_ylabel('Reflection (dB)')

        # Small epsilon to avoid log(0) errors
        epsilon = 1e-10

        # Convert to dB scale - just use TM data
        R_dB = 10 * np.log10(R_TM + epsilon)

        # Plot TM data with dual style (solid red line with blue dotted overlay)
        # This gives the appearance of two lines while only plotting one set of data
        self.ax.plot(wavelengths, R_dB, 'r-', linewidth=2)
        self.ax.plot(wavelengths, R_dB, 'b--', linewidth=1.5)

        # Set x-axis limits to the wavelength range
        self.ax.set_xlim(wavelengths[0], wavelengths[-1])

        # Set y-axis limits automatically with padding
        y_min = np.min(R_dB)
        y_max = np.max(R_dB)

        # Check for valid values (not NaN or Inf)
        if np.isfinite(y_min) and np.isfinite(y_max):
            # Ensure minimum visible range of 10dB
            if y_max - y_min < 10:
                y_center = (y_min + y_max) / 2
                y_min = y_center - 5
                y_max = y_center + 5

            # Add padding
            y_range = y_max - y_min
            self.ax.set_ylim(y_min - 0.1 * y_range, y_max + 0.1 * y_range)

        # Add grid and legend (just show TM in legend)
        self.ax.grid(True, linestyle='--', alpha=0.7)
        self.ax.legend(loc='upper right')

        # Adjust layout to prevent clipping of labels
        self.figure.tight_layout()

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

        # Create a status bar
        self.setStatusBar(self.statusBar())

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

        # Create remaining section (TMM calculation)
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
        for material_id, material_name in results:
            self.material_dropdown.addItem(material_name, material_id)

    def add_material(self):
        """Add a material to the library"""
        # Check if we've reached the maximum
        if self.material_table.rowCount() >= 100:
            QMessageBox.warning(self, "Maximum Reached", "Cannot add more than 100 materials.")
            return

        # Get values from inputs
        label = self.label_entry.text().strip()

        # Get selected material from dropdown
        selected_index = self.material_dropdown.currentIndex()
        if selected_index < 0:
            QMessageBox.warning(self, "No Material", "Please select a material.")
            return

        material_id = self.material_dropdown.itemData(selected_index)
        material_name = self.material_dropdown.currentText()
        is_defect = self.defect_checkbox.isChecked()

        # Validate label
        if not label:
            QMessageBox.warning(self, "Invalid Label", "Please enter a label (max 3 characters).")
            return

        if not self.material_table.is_label_unique(label):
            QMessageBox.warning(self, "Duplicate Label", f"Label '{label}' is already in use.")
            return

        # Add to table
        self.material_table.add_material(label, material_name, material_id, is_defect)

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

    def calculate_tmm(self):
        """Calculate and display TMM results with threading to prevent UI freezing"""

        # Define a worker thread for TMM calculations
        class TMM_Worker(QThread):
            # Define signals for results or errors
            finished = pyqtSignal(object, object, object)
            error = pyqtSignal(str)

            def __init__(self, stack, wavelengths, angle, parent=None):
                super().__init__(parent)
                self.stack = stack
                self.wavelengths = wavelengths
                self.angle = angle

            def run(self):
                try:
                    # Create calculator
                    calculator = TMM_Calculator()

                    # Calculate reflection for TM mode only
                    R_TM, problematic = calculator.calculate_reflection(self.stack, self.wavelengths, self.angle)

                    # Emit results when finished
                    self.finished.emit(self.wavelengths, R_TM, problematic)
                except Exception as e:
                    # Capture the full traceback for debugging
                    error_msg = f"Error: {str(e)}\n{traceback.format_exc()}"
                    self.error.emit(error_msg)

        # Main calculation function continues here
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
            # Create status message
            self.status_bar = self.statusBar()
            self.status_bar.showMessage("Building layer structure...")

            # Build the layer structure - use the filter_visualizer from the visualization window
            expanded_filter = self.visualization_window.filter_visualizer.expand_filter(filter_def)

            # Remove any "..." from the expanded definition
            expanded_filter = [layer for layer in expanded_filter if layer != "..."]

            # Show layer count in status
            self.status_bar.showMessage(f"Processing {len(expanded_filter)} layers...")

            # Get material data
            materials_dict = self.material_table.get_materials()

            # Convert to layer structure for TMM
            stack = []

            # Add incident medium (air)
            stack.append((1.0, 0))  # n=1.0, d=0 (semi-infinite)

            # Add each layer from the filter (no defect check - this happens during array definition now)
            for material_id in expanded_filter:
                if material_id in materials_dict:
                    # Extract material_id from the materials dictionary
                    material_name, material_ref_id, _ = materials_dict[material_id]
                    stack.append((material_ref_id, default_thickness))

            # Add exit medium (substrate, using default silicon)
            stack.append((3.5, 0))  # Silicon substrate, semi-infinite

            # Disable calculate button during calculation
            self.calculate_btn.setEnabled(False)
            self.calculate_btn.setText("Calculating...")

            # Create and start worker thread
            self.status_bar.showMessage("Calculating reflection spectrum...")
            self.worker = TMM_Worker(stack, wavelengths, angle)

            # Connect signals
            self.worker.finished.connect(self.calculation_finished)
            self.worker.error.connect(self.calculation_error)

            # Start the calculation thread
            self.worker.start()

        except Exception as e:
            self.status_bar.clearMessage()
            QMessageBox.critical(self, "Preparation Error", f"Error preparing calculation: {str(e)}")
            traceback.print_exc()

            # Re-enable calculate button
            self.calculate_btn.setEnabled(True)
            self.calculate_btn.setText("Calculate")

    def calculation_finished(self, wavelengths, R_TM, problematic):
        """Handle the completion of TMM calculation"""
        # Update plots with only TM data - pass None for R_TE
        self.tmm_plots.plot_results(wavelengths, None, R_TM)

        # Show warning if there are problematic materials
        if problematic:
            warning_msg = "Some materials have wavelength ranges incompatible with your calculation:\n\n"

            for material_id, (min_range, max_range) in problematic.items():
                shelf, book, page = material_id.split('|')
                warning_msg += f"- {book}/{page}: Valid range {min_range:.1f}nm - {max_range:.1f}nm\n"

            warning_msg += f"\nYour calculation used: {wavelengths[0]:.1f}nm - {wavelengths[-1]:.1f}nm\n\n"
            warning_msg += "Results may not be accurate for these materials. Default values were used as fallback."

            QMessageBox.warning(self, "Wavelength Range Warning", warning_msg)

        # Clear status and re-enable button
        self.statusBar().showMessage("Calculation complete", 3000)
        self.calculate_btn.setEnabled(True)
        self.calculate_btn.setText("Calculate")

    def calculation_error(self, error_msg):
        """Handle errors in the TMM calculation"""
        # Show error message
        QMessageBox.critical(self, "Calculation Error", error_msg)

        # Clear status and re-enable button
        self.statusBar().clearMessage()
        self.calculate_btn.setEnabled(True)
        self.calculate_btn.setText("Calculate")

    def check_materials_wavelength_compatibility(self):
        """Check if all materials are compatible with the selected wavelength range"""
        # Get wavelength range
        start = self.wavelength_start.value()
        end = self.wavelength_end.value()

        # Get all materials
        materials = self.material_table.get_materials()

        incompatible = []

        # Check each material's wavelength range
        for label, (name, material_id, _) in materials.items():
            if isinstance(material_id, str) and '|' in material_id:
                min_range, max_range = self.material_api.get_wavelength_range(material_id)

                if min_range == 0 and max_range == 0:
                    # Couldn't determine range
                    continue

                if start < min_range or end > max_range:
                    incompatible.append((label, name, min_range, max_range))

        if incompatible:
            msg = "The following materials are incompatible with your wavelength range:\n\n"

            for label, name, min_range, max_range in incompatible:
                msg += f"- {label}: {name}\n"
                msg += f"  Valid range: {min_range:.1f}nm - {max_range:.1f}nm\n"

            msg += f"\nYour calculation range: {start}nm - {end}nm\n\n"
            msg += "Consider adjusting your wavelength range or selecting different materials."

            QMessageBox.warning(self, "Material Compatibility Warning", msg)
            return False

        return True


# Run the application
if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = OpticalFilterApp()
    sys.exit(app.exec_())