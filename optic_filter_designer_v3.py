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
import json
import os
from PyQt5.QtWidgets import QFileDialog, QMenuBar, QMenu, QAction
from PyQt5.QtGui import QPixmap
from matplotlib.backends.backend_agg import FigureCanvasAgg
import io
import pickle


class MaterialSearchAPI:
    """Class to handle interaction with refractiveindex.info database"""

    def __init__(self):
        """Initialize the Material Search API with database caching"""
        # Import the refractiveindex package
        try:
            from refractiveindex import RefractiveIndexMaterial
            import refractiveindex.refractiveindex as ri
            self.RefractiveIndexMaterial = RefractiveIndexMaterial
            self.RefractiveIndex = ri.RefractiveIndex
            self.initialized = True

            # Define database cache location
            self.cache_dir = os.path.join(os.path.expanduser("~"), ".optical_filter_designer")
            self.db_cache_path = os.path.join(self.cache_dir, "refractive_index_db.pickle")

            # Create cache directory if it doesn't exist
            if not os.path.exists(self.cache_dir):
                os.makedirs(self.cache_dir)

            # Check if cached database exists
            if os.path.exists(self.db_cache_path):
                try:
                    # Load database from cache
                    with open(self.db_cache_path, 'rb') as f:
                        self.database = pickle.load(f)
                    print("Refractiveindex.info database loaded from cache!")
                except Exception as e:
                    print(f"Error loading cached database: {e}")
                    # Fall back to downloading if cache load fails
                    self._download_and_cache_database()
            else:
                # Download and cache the database
                self._download_and_cache_database()

        except ImportError:
            print("Error: refractiveindex package not found. Install with 'pip install refractiveindex'")
            self.initialized = False
            sys.exit(1)  # Exit if refractiveindex is not available

    def _download_and_cache_database(self):
        """Download the database and save to cache"""
        print("Downloading refractiveindex.info database...")
        self.database = self.RefractiveIndex()

        # Save to cache file
        try:
            with open(self.db_cache_path, 'wb') as f:
                pickle.dump(self.database, f)
            print("Refractiveindex.info database cached for future use!")
        except Exception as e:
            print(f"Warning: Could not cache database: {e}")

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
        Get refractive index with caching and handling out-of-range wavelengths
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

            # Get the valid wavelength range
            range_min = material_obj.material.refractiveIndex.rangeMin * 1000  # μm to nm
            range_max = material_obj.material.refractiveIndex.rangeMax * 1000  # μm to nm

            # Check if wavelength is within range
            actual_wavelength = wavelength
            if wavelength < range_min:
                # Use the minimum value for wavelengths below range
                actual_wavelength = range_min
            elif wavelength > range_max:
                # Use the maximum value for wavelengths above range
                actual_wavelength = range_max

            # Get refractive index at adjusted wavelength
            n = material_obj.get_refractive_index(actual_wavelength)

            # Try to get extinction coefficient if available
            try:
                k = material_obj.get_extinction_coefficient(actual_wavelength)
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


class TMM_Calculator:
    """Custom TMM (Transfer Matrix Method) calculator that doesn't rely on PyTMM"""

    def __init__(self):
        self.material_cache = {}  # Cache for material refractive indices
        import numpy as np
        self.np = np  # Store numpy reference for use in methods

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
                if self.np.min(wavelengths) < range_min or self.np.max(wavelengths) > range_max:
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
        Calculate reflection using custom TMM implementation

        Parameters:
        stack: List of (material, thickness) tuples
        wavelengths: Array of wavelengths in nm
        angle: Incident angle in radians
        show_progress: Optional callback function to show progress (percent)

        Returns:
        R, problematic: Arrays of reflection coefficients and dict of problematic materials
        """
        import numpy as np

        # Precompute all material indices to avoid repeated material object creation
        problematic = self.precompute_indices(stack, wavelengths)

        # Initialize result arrays
        R = np.zeros(len(wavelengths))
        T = np.zeros(len(wavelengths))

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

            # Calculate reflection using our custom TMM implementation
            r, t = self._calculate_tmm_matrices(indices, thicknesses, wavelength, angle)

            # Calculate reflection coefficient |r|²
            R[i] = np.abs(r) ** 2

            # Ensure physically valid value (no gain in passive system)
            if R[i] > 1.0:
                print(f"Warning: Capping unphysical reflection value {R[i]} at wavelength {wavelength}nm")
                R[i] = 1.0

            # Calculate transmission coefficient |t|²
            T[i] = np.abs(t) ** 2

            # Update progress if callback provided
            if show_progress is not None and i % 10 == 0:
                progress = int((i + 1) / len(wavelengths) * 100)
                show_progress(progress)

        return R, problematic

    def _calculate_tmm_matrices(self, indices, thicknesses, wavelength, angle):
        """
        Calculate reflection and transmission coefficients using the transfer matrix method

        Parameters:
        indices: List of complex refractive indices for each layer
        thicknesses: List of thicknesses for each layer (in nm)
        wavelength: Wavelength in nm
        angle: Incident angle in radians

        Returns:
        r, t: reflection and transmission coefficients
        """
        np = self.np
        # Convert wavelength to nm for calculation
        wavelength_nm = wavelength

        # Number of layers
        num_layers = len(indices)

        # Initialize the system matrix as identity
        M = np.eye(2, dtype=complex)

        # Calculate propagation through all layers (except first and last semi-infinite media)
        for j in range(num_layers - 1):  # Skip the last medium
            n1 = indices[j]
            n2 = indices[j + 1]
            d = thicknesses[j]

            # Skip first layer if it's the incident medium (zero thickness)
            if j == 0 and d == 0:
                continue

            # Calculate angle in the medium using Snell's law
            if angle > 0:
                # Handle complex refractive indices
                if isinstance(n1, complex) or isinstance(n2, complex):
                    # For complex indices, we use the real part for angle calculation
                    theta1 = angle if j == 0 else np.arcsin((indices[0].real / n1.real) * np.sin(angle))
                    theta2 = np.arcsin((n1.real / n2.real) * np.sin(theta1))
                else:
                    # Real indices
                    theta1 = angle if j == 0 else np.arcsin((indices[0] / n1) * np.sin(angle))
                    theta2 = np.arcsin((n1 / n2) * np.sin(theta1))
            else:
                # Normal incidence (angle = 0)
                theta1 = 0
                theta2 = 0

            # Calculate interface matrix (boundary conditions)
            # For TM (p) polarization
            if np.abs(angle) > 0:
                # TM (p) polarization
                r12 = (n2 * np.cos(theta1) - n1 * np.cos(theta2)) / (n2 * np.cos(theta1) + n1 * np.cos(theta2))
                t12 = (2 * n1 * np.cos(theta1)) / (n2 * np.cos(theta1) + n1 * np.cos(theta2))
            else:
                # Normal incidence - same for TE/TM
                r12 = (n2 - n1) / (n2 + n1)
                t12 = 2 * n1 / (n2 + n1)

            # Interface matrix
            I = (1 / t12) * np.array([[1, r12], [r12, 1]], dtype=complex)

            # Phase accumulation in the layer (only if not the last layer)
            if j < num_layers - 2:  # Skip the last interface
                thickness = thicknesses[j + 1]  # Thickness of next layer
                if thickness > 0:  # Only propagate if thickness > 0
                    # Phase factor
                    if isinstance(n2, complex) or angle > 0:
                        # Complex refractive index or non-normal incidence
                        # Calculate propagation constant (k vector in medium)
                        k0 = 2 * np.pi / wavelength_nm  # Wave number in vacuum
                        kz = n2 * k0 * np.cos(theta2)  # z-component of wave vector
                        phase = kz * thickness
                    else:
                        # Simple phase for real index and normal incidence
                        phase = 2 * np.pi * n2 * thickness / wavelength_nm

                    # Propagation matrix
                    P = np.array([
                        [np.exp(-1j * phase), 0],
                        [0, np.exp(1j * phase)]
                    ], dtype=complex)

                    # Combine with interface matrix
                    M = M @ I @ P
                else:
                    # Just add interface if zero thickness
                    M = M @ I
            else:
                # Last interface, no propagation
                M = M @ I

        # Calculate reflection and transmission coefficients
        r = M[1, 0] / M[0, 0]  # Reflection coefficient
        t = 1 / M[0, 0]  # Transmission coefficient

        return r, t


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
        """Add a material to the table with clean display"""
        row = self.rowCount()
        self.insertRow(row)

        # Add the label
        label_item = QTableWidgetItem(label)
        label_item.setFlags(label_item.flags() & ~Qt.ItemIsEditable)
        self.setItem(row, 0, label_item)

        # Add the material name - store the full name as data
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

    def expand_filter_for_calculation(self, filter_definition):
        """Expand the filter definition into a list of individual layers for calculation"""
        if not filter_definition:
            return []

        arrays = self.array_table.get_arrays()

        # Pattern to match array repetition like (M1)^5
        pattern = r'\(([^)]+)\)\^(\d+)'

        # Replace array repetitions with expanded form - FULL expansion for calculation
        while re.search(pattern, filter_definition):
            match = re.search(pattern, filter_definition)
            array_id = match.group(1)
            repetitions = int(match.group(2))

            # Always do full expansion for calculation (no truncation)
            replacement = "*".join([array_id] * repetitions)

            filter_definition = filter_definition[:match.start()] + replacement + filter_definition[match.end():]

        # Split by * to get individual components
        components = filter_definition.split("*")
        expanded = []

        for component in components:
            component = component.strip()
            if component in arrays:
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

        # Initialize recent files list
        self.recent_files = []
        self.load_recent_files()

        # Setup menu bar
        self.setup_menu_bar()

        # Setup UI
        self.setup_ui()

        # Set window properties
        self.setWindowTitle("Optical Filter Designer & TMM Calculator")
        self.setMinimumSize(900, 700)

        # Create a status bar
        self.setStatusBar(self.statusBar())

        self.show()

    def setup_menu_bar(self):
        """Setup the application menu bar"""
        self.menu_bar = QMenuBar(self)
        self.setMenuBar(self.menu_bar)

        # File menu
        self.file_menu = QMenu("File", self)
        self.menu_bar.addMenu(self.file_menu)

        # Save action
        save_action = QAction("Save Filter", self)
        save_action.setShortcut("Ctrl+S")
        save_action.triggered.connect(self.save_filter)
        self.file_menu.addAction(save_action)

        # Recent files section
        self.file_menu.addSeparator()
        self.recent_menu_actions = []

        # Add placeholder for recent files - using a different approach to avoid lambda issues
        for i in range(8):
            action = QAction("", self)
            action.setVisible(False)
            action.setData(i)  # Store the index as data
            action.triggered.connect(self.open_recent_file_from_action)
            self.recent_menu_actions.append(action)
            self.file_menu.addAction(action)

        # Update recent files menu
        self.update_recent_files_menu()

        # Browse action
        self.file_menu.addSeparator()
        browse_action = QAction("Browse...", self)
        browse_action.setShortcut("Ctrl+O")
        browse_action.triggered.connect(self.browse_filter)
        self.file_menu.addAction(browse_action)

        self.database_menu = QMenu("Database", self)
        self.menu_bar.addMenu(self.database_menu)

        # Force refresh database action
        refresh_action = QAction("Update Materials Database", self)
        refresh_action.triggered.connect(self.refresh_database)
        self.database_menu.addAction(refresh_action)

    def refresh_database(self):
        """Force refresh the refractiveindex.info database"""
        reply = QMessageBox.question(self, "Refresh Database",
                                     "Are you sure you want to update the materials database? This may take a few minutes.",
                                     QMessageBox.Yes | QMessageBox.No, QMessageBox.No)

        if reply == QMessageBox.Yes:
            # Show progress message
            self.statusBar().showMessage("Updating materials database...")

            # Force re-download
            if os.path.exists(self.material_api.db_cache_path):
                os.remove(self.material_api.db_cache_path)

            self.material_api._download_and_cache_database()

            # Refresh material search
            self.search_materials()
            self.statusBar().showMessage("Materials database updated successfully!", 3000)

    def open_recent_file_from_action(self):
        """Open a file from the recent files list using the sender's data"""
        action = self.sender()
        if action:
            index = action.data()
            self.open_recent_file(index)

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
        layout = QHBoxLayout(group_box)  # Horizontal layout

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

        # Save button - NEW
        self.save_btn = QPushButton("Save Filter")
        self.save_btn.setStyleSheet("padding: 8px;")
        self.save_btn.clicked.connect(self.save_filter)
        params_layout.addWidget(self.save_btn)

        # Add stretching space
        params_layout.addStretch()

        # Right side: TMM result plots
        self.tmm_plots = TMM_Plots()

        # Add both sides to the main layout
        layout.addWidget(params_widget, 1)  # Parameters take 1/3 of space
        layout.addWidget(self.tmm_plots, 2)  # Plots take 2/3 of space

        parent_layout.addWidget(group_box)

    def save_filter(self):
        """Save the current filter configuration"""
        # Ask user for save location
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Save Filter", "", "Filter Files (*.filter);;All Files (*)"
        )

        if not file_path:
            return  # User cancelled

        # Ensure .filter extension
        if not file_path.endswith(".filter"):
            file_path += ".filter"

        try:
            # Save plot data if available
            plot_data = None
            if hasattr(self, 'last_calculation_data'):
                plot_data = {
                    'wavelengths': self.last_calculation_data['wavelengths'].tolist(),
                    'R_TM': self.last_calculation_data['R_TM'].tolist()
                }

            # Create data structure to save
            save_data = {
                "materials": {
                    label: {
                        "name": material[0],
                        "id": material[1],
                        "is_defect": material[2]
                    }
                    for label, material in self.material_table.get_materials().items()
                },
                "arrays": self.array_table.get_arrays(),
                "filter": self.filter_entry.text(),
                "calculation": {
                    "wavelength_start": self.wavelength_start.value(),
                    "wavelength_end": self.wavelength_end.value(),
                    "wavelength_steps": self.wavelength_steps.value(),
                    "incident_angle": self.incident_angle.value(),
                    "default_thickness": self.default_thickness.value()
                },
                "material_colors": {
                    label: color.name()
                    for label, color in self.material_table.get_material_colors().items()
                },
                "plot_data": plot_data
            }

            # Save to file
            with open(file_path, "w") as f:
                json.dump(save_data, f, indent=2)

            # Add to recent files
            self.add_to_recent_files(file_path)

            # Show success message
            self.statusBar().showMessage(f"Filter saved to {file_path}", 3000)

        except Exception as e:
            # Show error message
            QMessageBox.critical(self, "Save Error", f"Error saving filter: {str(e)}")

    def load_filter(self, file_path):
        """Load a filter configuration from a file"""
        try:
            # Load from file
            with open(file_path, "r") as f:
                data = json.load(f)

            # Clear current data
            self.material_table.setRowCount(0)
            self.array_table.setRowCount(0)

            # Load materials
            for label, material in data["materials"].items():
                self.material_table.add_material(
                    label, material["name"], material["id"], material["is_defect"]
                )

            # Restore material colors if available
            if "material_colors" in data:
                for label, color_name in data["material_colors"].items():
                    self.material_table.material_colors[label] = QColor(color_name)

            # Load arrays
            for array_id, definition in data["arrays"].items():
                self.array_table.add_array(definition)

            # Update counters
            material_count = self.material_table.rowCount()
            self.material_count_label.setText(f"{material_count}/100 materials defined")

            array_count = self.array_table.rowCount()
            self.array_count_label.setText(f"{array_count}/20 arrays defined")

            # Load filter
            self.filter_entry.setText(data["filter"])
            self.validate_filter()

            # Load calculation parameters
            calc = data["calculation"]
            self.wavelength_start.setValue(calc["wavelength_start"])
            self.wavelength_end.setValue(calc["wavelength_end"])
            self.wavelength_steps.setValue(calc["wavelength_steps"])
            self.incident_angle.setValue(calc["incident_angle"])
            self.default_thickness.setValue(calc["default_thickness"])

            # Load plot data if available
            if "plot_data" in data and data["plot_data"]:
                try:
                    import numpy as np

                    # Convert lists back to numpy arrays
                    wavelengths = np.array(data["plot_data"]["wavelengths"])
                    R_TM = np.array(data["plot_data"]["R_TM"])

                    # Store data for future use
                    self.last_calculation_data = {
                        'wavelengths': wavelengths,
                        'R_TM': R_TM
                    }

                    # Plot the data properly
                    self.tmm_plots.plot_results(wavelengths, None, R_TM)
                except Exception as plot_error:
                    print(f"Error restoring plot data: {plot_error}")

            # Add to recent files
            self.add_to_recent_files(file_path)

            # Show success message
            self.statusBar().showMessage(f"Filter loaded from {file_path}", 3000)

        except Exception as e:
            # Show error message
            QMessageBox.critical(self, "Load Error", f"Error loading filter: {str(e)}")

    def load_figure_from_image(self, figure_data):
        """Load figure from base64 encoded image data"""
        import base64
        from PIL import Image
        import numpy as np

        # Decode image
        img_data = base64.b64decode(figure_data)
        img = Image.open(io.BytesIO(img_data))

        # Clear current plot
        self.tmm_plots.ax.clear()

        # Display image with proper formatting
        self.tmm_plots.ax.imshow(np.array(img))
        self.tmm_plots.ax.axis('off')  # Turn off axes for image display
        self.tmm_plots.canvas.draw()

    def browse_filter(self):
        """Open a file dialog to browse for a filter file"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Open Filter", "", "Filter Files (*.filter);;All Files (*)"
        )

        if file_path:
            self.load_filter(file_path)

    def load_recent_files(self):
        """Load the list of recent files from a JSON file"""
        try:
            config_path = os.path.join(os.path.expanduser("~"), ".optical_filter_designer")
            if not os.path.exists(config_path):
                os.makedirs(config_path)

            recent_files_path = os.path.join(config_path, "recent_files.json")
            if os.path.exists(recent_files_path):
                with open(recent_files_path, "r") as f:
                    self.recent_files = json.load(f)
        except Exception as e:
            print(f"Error loading recent files: {e}")
            self.recent_files = []

    def save_recent_files(self):
        """Save the list of recent files to a JSON file"""
        try:
            config_path = os.path.join(os.path.expanduser("~"), ".optical_filter_designer")
            if not os.path.exists(config_path):
                os.makedirs(config_path)

            recent_files_path = os.path.join(config_path, "recent_files.json")
            with open(recent_files_path, "w") as f:
                json.dump(self.recent_files, f)
        except Exception as e:
            print(f"Error saving recent files: {e}")

    def update_recent_files_menu(self):
        """Update the recent files menu with current list"""
        for i, action in enumerate(self.recent_menu_actions):
            if i < len(self.recent_files):
                file_path = self.recent_files[i]
                # Show only filename in menu, not full path
                file_name = os.path.basename(file_path)
                action.setText(f"{i + 1}. {file_name}")
                action.setVisible(True)
            else:
                action.setText("")
                action.setVisible(False)

    def add_to_recent_files(self, file_path):
        """Add a file to the recent files list"""
        # Remove if already in list
        if file_path in self.recent_files:
            self.recent_files.remove(file_path)

        # Add to beginning of list
        self.recent_files.insert(0, file_path)

        # Keep only 8 most recent
        self.recent_files = self.recent_files[:8]

        # Update menu and save
        self.update_recent_files_menu()
        self.save_recent_files()

    def open_recent_file(self, index):
        """Open a file from the recent files list"""
        if index < len(self.recent_files):
            file_path = self.recent_files[index]
            if os.path.exists(file_path):
                self.load_filter(file_path)
            else:
                # File doesn't exist anymore
                from PyQt5.QtWidgets import QMessageBox
                QMessageBox.warning(self, "File Not Found",
                                    f"The file {file_path} no longer exists.")
                # Remove from recent files
                self.recent_files.pop(index)
                self.update_recent_files_menu()
                self.save_recent_files()

    def search_materials(self):
        """Search materials with cleaned display names"""
        query = self.search_field.text()
        all_results = self.material_api.search_materials(query)

        # Group by base material name only
        unique_materials = {}
        for material_id, material_name in all_results:
            # Clean up HTML tags
            clean_name = self.clean_material_name(material_name)

            # Extract just the base material name (e.g., "Ag (Silver)")
            base_name = None
            if "(" in clean_name and ")" in clean_name:
                # Find the first parenthesis pair
                open_pos = clean_name.find("(")
                close_pos = clean_name.find(")", open_pos)
                if close_pos > open_pos:
                    base_name = clean_name[:close_pos + 1].strip()

            # If we couldn't extract using parentheses, use first part
            if base_name is None:
                parts = clean_name.split(":")
                base_name = parts[0].strip()

            # Further clean up - remove any trailing details after the base name
            if ":" in base_name:
                base_name = base_name.split(":")[0].strip()

            # Remove any wavelength ranges or dates
            if "µm" in base_name or "nm" in base_name:
                # Find the material name without the range
                index = min(
                    base_name.find("µm") if "µm" in base_name else len(base_name),
                    base_name.find("nm") if "nm" in base_name else len(base_name),
                    base_name.find(":") if ":" in base_name else len(base_name)
                )
                base_name = base_name[:index].strip()

            # Make sure we have a properly formatted base name
            if base_name.strip() == "":
                base_name = clean_name  # Fallback to the cleaned full name

            # Store in our dictionary, grouping all variants under one base name
            if base_name not in unique_materials:
                unique_materials[base_name] = []
            unique_materials[base_name].append((material_id, clean_name))

        # Update dropdown with just the unique base names
        self.material_dropdown.clear()
        for base_name in sorted(unique_materials.keys()):
            self.material_dropdown.addItem(base_name)
            # Store full material details as item data
            index = self.material_dropdown.count() - 1
            self.material_dropdown.setItemData(index, unique_materials[base_name], Qt.UserRole)

    def clean_material_name(self, name):
        """Clean up HTML tags and format material names properly"""
        # Replace HTML subscript tags with proper subscript characters
        subscript_map = {
            '0': '₀', '1': '₁', '2': '₂', '3': '₃', '4': '₄',
            '5': '₅', '6': '₆', '7': '₇', '8': '₈', '9': '₉'
        }

        # Remove <sub> tags and replace numbers with subscripts
        result = name
        while "<sub>" in result and "</sub>" in result:
            start = result.find("<sub>")
            end = result.find("</sub>")
            if start < end:
                # Get the content between tags
                sub_content = result[start + 5:end]
                # Replace digits with subscript characters
                subscripted = ''.join([subscript_map.get(c, c) for c in sub_content])
                # Replace the entire tag and content
                result = result[:start] + subscripted + result[end + 6:]

        return result

    def add_material(self):
        """Add base material to the library without selecting a specific variant"""
        # Check if we've reached the maximum
        if self.material_table.rowCount() >= 100:
            QMessageBox.warning(self, "Maximum Reached", "Cannot add more than 100 materials.")
            return

        # Get values from inputs
        label = self.label_entry.text().strip()

        # Get selected material base name
        selected_index = self.material_dropdown.currentIndex()
        if selected_index < 0:
            QMessageBox.warning(self, "No Material", "Please select a material.")
            return

        base_name = self.material_dropdown.currentText()
        # Store all variants for later selection
        material_variants = self.material_dropdown.itemData(selected_index, Qt.UserRole)
        is_defect = self.defect_checkbox.isChecked()

        # Validate label
        if not label:
            QMessageBox.warning(self, "Invalid Label", "Please enter a label (max 3 characters).")
            return

        if not self.material_table.is_label_unique(label):
            QMessageBox.warning(self, "Duplicate Label", f"Label '{label}' is already in use.")
            return

        # Create a special format to store all variants
        variants_data = {
            "base_name": base_name,
            "variants": material_variants
        }

        # Store this data as JSON in the userData
        variants_json = json.dumps(variants_data)

        # Add to table with just the base name - use a placeholder ID temporarily
        self.material_table.add_material(label, base_name, variants_json, is_defect)

        # Update the count label
        count = self.material_table.rowCount()
        self.material_count_label.setText(f"{count}/100 materials defined")

        # Clear inputs
        self.label_entry.clear()
        self.defect_checkbox.setChecked(False)

    def filter_by_wavelength_compatibility(self):
        """Filter dropdown items based on wavelength compatibility"""
        # Get current wavelength range from TMM calculation section
        start = self.wavelength_start.value()
        end = self.wavelength_end.value()

        # Store currently selected item
        current_text = self.material_dropdown.currentText()

        # Clear and repopulate dropdown with only compatible materials
        compatible_materials = []

        for i in range(self.material_dropdown.count()):
            base_name = self.material_dropdown.itemText(i)
            materials_list = self.material_dropdown.itemData(i, Qt.UserRole)

            # Check if any version of this material is compatible
            compatible_versions = []
            for material_id, full_name in materials_list:
                min_range, max_range = self.material_api.get_wavelength_range(material_id)

                if min_range <= end and max_range >= start:
                    compatible_versions.append((material_id, full_name))

            if compatible_versions:
                compatible_materials.append((base_name, compatible_versions))

        # Rebuild dropdown with only compatible materials
        self.material_dropdown.clear()
        for base_name, versions in compatible_materials:
            self.material_dropdown.addItem(base_name)
            item_index = self.material_dropdown.count() - 1
            self.material_dropdown.setItemData(item_index, versions, Qt.UserRole)

        # Try to restore previous selection
        index = self.material_dropdown.findText(current_text)
        if index >= 0:
            self.material_dropdown.setCurrentIndex(index)

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
        """Calculate and display TMM results with compatibility checking and material selection"""

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

        # Check material compatibility before calculation
        incompatible_materials = self.check_materials_compatibility()

        # If we have incompatible materials, show a warning dialog
        if incompatible_materials:
            message = "The following materials don't have data for the full wavelength range:\n\n"

            for material_id, range_tuple, best_variant in incompatible_materials:
                min_range, max_range = range_tuple

                if min_range == 0 and max_range == 0:
                    message += f"• {material_id}: No wavelength data available\n"
                else:
                    message += f"• {material_id}: Available range {min_range:.1f}-{max_range:.1f} nm\n"

            message += f"\nYour calculation range: {self.wavelength_start.value():.1f}-{self.wavelength_end.value():.1f} nm\n\n"
            message += "How would you like to proceed?"

            # Create custom dialog with "Calculate Anyway" and "Cancel" buttons
            from PyQt5.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QLabel

            dialog = QDialog(self)
            dialog.setWindowTitle("Wavelength Range Warning")

            layout = QVBoxLayout()
            layout.addWidget(QLabel(message))

            button_layout = QHBoxLayout()
            calculate_anyway_btn = QPushButton("Calculate Anyway")
            cancel_btn = QPushButton("Cancel")

            calculate_anyway_btn.clicked.connect(lambda: dialog.done(QDialog.Accepted))
            cancel_btn.clicked.connect(lambda: dialog.done(QDialog.Rejected))

            button_layout.addWidget(calculate_anyway_btn)
            button_layout.addWidget(cancel_btn)
            layout.addLayout(button_layout)

            dialog.setLayout(layout)

            # Show dialog and proceed based on response
            result = dialog.exec_()

            if result != QDialog.Accepted:
                # User cancelled the calculation
                return

        # Continue with calculation (user either accepted the warning or there were no issues)
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

            # Build the layer structure - use the dedicated calculation method that fully expands all repetitions
            expanded_filter = self.visualization_window.filter_visualizer.expand_filter_for_calculation(filter_def)

            # Show layer count in status
            self.status_bar.showMessage(f"Processing {len(expanded_filter)} layers...")

            # Get material data
            materials_dict = self.material_table.get_materials()

            # *** OPTIMIZATION: Select best variant for each unique material once ***
            unique_materials = set(expanded_filter)
            selected_variants = {}

            for material_id in unique_materials:
                if material_id in materials_dict:
                    # Parse stored variants data
                    _, variants_json, _ = materials_dict[material_id]

                    try:
                        # Parse variants data
                        variants_data = json.loads(variants_json)
                        variants = variants_data.get("variants", [])

                        # Select best variant for current wavelength range
                        best_variant = None
                        best_coverage = 0

                        for variant_id, _ in variants:
                            min_range, max_range = self.material_api.get_wavelength_range(variant_id)

                            # Skip invalid ranges
                            if min_range == 0 and max_range == 0:
                                continue

                            # Calculate overlap
                            overlap_start = max(start, min_range)
                            overlap_end = min(end, max_range)
                            coverage = max(0, overlap_end - overlap_start)

                            if coverage > best_coverage:
                                best_coverage = coverage
                                best_variant = variant_id

                        if best_variant:
                            selected_variants[material_id] = best_variant
                            print(f"Selected variant {best_variant} for material {material_id}")
                        else:
                            # No suitable variant found, use a default value
                            print(f"Warning: No suitable variant found for {material_id}, using default")
                            selected_variants[material_id] = 1.5  # Default to glass-like

                    except Exception as e:
                        # If we can't parse the variants data, use a default
                        print(f"Error processing material {material_id}: {str(e)}")
                        selected_variants[material_id] = 1.5
                else:
                    # Material not found, use default
                    print(f"Warning: Material {material_id} not found in library, using default")
                    selected_variants[material_id] = 1.5

            # Convert to layer structure for TMM
            stack = []

            # Add incident medium (air)
            stack.append((1.0, 0))  # n=1.0, d=0 (semi-infinite)

            # Add each layer from the filter with pre-selected material variant
            for material_id in expanded_filter:
                if material_id in selected_variants:
                    stack.append((selected_variants[material_id], default_thickness))
                else:
                    # Fallback (shouldn't happen with the design above)
                    stack.append((1.5, default_thickness))

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

    def check_materials_compatibility(self):
        """Check if all materials in the filter are compatible with the wavelength range"""
        # Get wavelength range
        start_wavelength = self.wavelength_start.value()
        end_wavelength = self.wavelength_end.value()

        # Get filter definition
        filter_def = self.filter_entry.text().strip()

        # Expand filter to get individual materials
        expanded_filter = self.visualization_window.filter_visualizer.expand_filter(filter_def)

        # Remove any "..." from the expanded definition
        expanded_filter = [layer for layer in expanded_filter if layer != "..."]

        # Get material data
        materials_dict = self.material_table.get_materials()

        # Track incompatible materials
        incompatible_materials = []

        # Check each material in the filter
        for material_id in expanded_filter:
            if material_id in materials_dict:
                # Extract stored variants data
                _, variants_json, _ = materials_dict[material_id]

                try:
                    # Parse variants data
                    variants_data = json.loads(variants_json)
                    variants = variants_data.get("variants", [])

                    # Check if any variant is fully compatible
                    is_compatible = False
                    for variant_id, _ in variants:
                        min_range, max_range = self.material_api.get_wavelength_range(variant_id)

                        # Skip invalid ranges
                        if min_range == 0 and max_range == 0:
                            continue

                        # Check if wavelength is fully within range
                        if min_range <= start_wavelength and max_range >= end_wavelength:
                            is_compatible = True
                            break

                    if not is_compatible:
                        # Find the best partial-coverage variant
                        best_variant = None
                        best_coverage = 0
                        best_range = (0, 0)

                        for variant_id, _ in variants:
                            min_range, max_range = self.material_api.get_wavelength_range(variant_id)

                            # Skip invalid ranges
                            if min_range == 0 and max_range == 0:
                                continue

                            # Calculate overlap
                            overlap_start = max(start_wavelength, min_range)
                            overlap_end = min(end_wavelength, max_range)
                            coverage = max(0, overlap_end - overlap_start)

                            if coverage > best_coverage:
                                best_coverage = coverage
                                best_variant = variant_id
                                best_range = (min_range, max_range)

                        if best_variant:
                            # Material has partial coverage
                            incompatible_materials.append((material_id, best_range, best_variant))
                        else:
                            # Material has no coverage at all
                            incompatible_materials.append((material_id, (0, 0), None))

                except Exception as e:
                    # If we can't parse the variants data, assume incompatible
                    print(f"Error checking compatibility for {material_id}: {str(e)}")
                    incompatible_materials.append((material_id, (0, 0), None))

        return incompatible_materials

    def calculation_finished(self, wavelengths, R_TM, problematic):
        """Handle the completion of TMM calculation"""
        # Store the calculation data for saving
        self.last_calculation_data = {
            'wavelengths': wavelengths,
            'R_TM': R_TM
        }

        # Update plots with only TM data
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


# Run the application
if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = OpticalFilterApp()
    sys.exit(app.exec_())