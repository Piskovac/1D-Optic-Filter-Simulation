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

class MaterialSearchAPI:
    """Class to handle interaction with refractiveindex.info database"""

    def __init__(self):
        """Initialize the Material Search API with database caching"""
        try:
            from refractiveindex import RefractiveIndexMaterial
            import refractiveindex.refractiveindex as ri
            self.RefractiveIndexMaterial = RefractiveIndexMaterial
            self.RefractiveIndex = ri.RefractiveIndex
            self.initialized = True
            self.material_cache = {}

            self.cache_dir = os.path.join(os.path.expanduser("~"), ".optical_filter_designer")
            self.db_cache_path = os.path.join(self.cache_dir, "refractive_index_db.pickle")

            if not os.path.exists(self.cache_dir):
                os.makedirs(self.cache_dir)

            if os.path.exists(self.db_cache_path):
                try:
                    with open(self.db_cache_path, 'rb') as f:
                        self.database = pickle.load(f)
                    print("Refractiveindex.info database loaded from cache!")
                except Exception as e:
                    print(f"Error loading cached database: {e}")
                    self._download_and_cache_database()
            else:
                self._download_and_cache_database()

        except ImportError:
            print("Error: refractiveindex package not found. Install with 'pip install refractiveindex'")
            self.initialized = False
            sys.exit(1)

    def _download_and_cache_database(self):
        """Download the database and save to cache"""
        print("Downloading refractiveindex.info database...")
        self.database = self.RefractiveIndex()

        try:
            with open(self.db_cache_path, 'wb') as f:
                pickle.dump(self.database, f)
            print("Refractiveindex.info database cached for future use!")
        except Exception as e:
            print(f"Warning: Could not cache database: {e}")

    def search_materials(self, query):
        """Search for materials matching the query in the database"""
        if not query or not self.initialized:
            return []

        results = []
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

                if query.lower() in book_id.lower() or query.lower() in book_name.lower():
                    for page in book.get('content', []):
                        if 'DIVIDER' in page:
                            continue

                        page_name = page.get('name', page.get('PAGE', ''))
                        page_id = page.get('PAGE', '')

                        if not page_id:
                            continue

                        material_id = f"{shelf_id}|{book_id}|{page_id}"
                        material_name = f"{book_name} - {page_name}"
                        results.append((material_id, material_name))

                else:
                    for page in book.get('content', []):
                        if 'DIVIDER' in page:
                            continue

                        page_name = page.get('name', page.get('PAGE', ''))
                        page_id = page.get('PAGE', '')

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

                if material.refractiveIndex:
                    range_min = material.refractiveIndex.rangeMin * 1000
                    range_max = material.refractiveIndex.rangeMax * 1000
                    return (range_min, range_max)

            return (0, 0)

        except Exception as e:
            print(f"Error getting wavelength range for {material_id}: {e}")
            return (0, 0)

    def get_refractive_index(self, material_id, wavelength):
        """Get refractive index for compatibility checking"""
        if not isinstance(material_id, str):
            return material_id

        cache_key = f"{material_id}_{wavelength}"
        if cache_key in self.material_cache:
            return self.material_cache[cache_key]

        if '|' not in material_id:
            raise ValueError(f"MaterialSearchAPI: Invalid material_id format: '{material_id}'")

        try:
            from refractiveindex import RefractiveIndexMaterial
            shelf, book, page = material_id.split('|')
            
            material_obj = RefractiveIndexMaterial(shelf=shelf, book=book, page=page)

            try:
                range_min = material_obj.material.refractiveIndex.rangeMin * 1000
                range_max = material_obj.material.refractiveIndex.rangeMax * 1000
            except AttributeError:
                # Try to get value anyway
                n = material_obj.get_refractive_index(wavelength)
                self.material_cache[cache_key] = n
                return n

            actual_wavelength = wavelength
            
            if wavelength < range_min:
                actual_wavelength = range_min
            elif wavelength > range_max:
                actual_wavelength = range_max

            n = material_obj.get_refractive_index(actual_wavelength)

            try:
                k = material_obj.get_extinction_coefficient(actual_wavelength)
                if k > 0:
                    n = complex(n, k)
            except:
                pass

            self.material_cache[cache_key] = n
            return n

        except Exception as e:
            raise ValueError(f"MaterialSearchAPI cannot process {material_id}: {e}")


class MaterialHandler:
    """Helper class to handle materials including selected database variants"""

    @staticmethod
    def serialize_material(material, selected_variant=None):
        """Convert material data to a serializable format for saving"""
        name, material_id, is_defect = material

        if isinstance(material_id, complex):
            return {
                "name": name,
                "type": "custom_complex",
                "n": float(material_id.real),
                "k": float(material_id.imag),
                "is_defect": is_defect
            }
        elif isinstance(material_id, (int, float)):
            return {
                "name": name,
                "type": "custom_real",
                "n": float(material_id),
                "k": 0.0,
                "is_defect": is_defect
            }
        elif isinstance(material_id, str) and material_id.endswith('.yml'):
            filename = os.path.basename(material_id)
            return {
                "name": name,
                "type": "browsed",
                "filename": filename,
                "original_path": material_id,
                "is_defect": is_defect
            }
        elif selected_variant and isinstance(selected_variant, str):
            return {
                "name": name,
                "type": "database",
                "id": material_id,
                "selected_variant": selected_variant,
                "is_defect": is_defect
            }
        else:
            return {
                "name": name,
                "type": "database",
                "id": material_id,
                "is_defect": is_defect
            }

    @staticmethod
    def deserialize_material(data, project_dir=None):
        """Convert saved data back to material format"""
        material_type = data.get("type", "database")

        if material_type == "custom_complex":
            n = data.get("n", 1.5)
            k = data.get("k", 0.0)
            return (data.get("name", "Custom"), complex(n, k), data.get("is_defect", False))

        elif material_type == "custom_real":
            n = data.get("n", 1.5)
            return (data.get("name", "Custom"), float(n), data.get("is_defect", False))

        elif material_type == "browsed":
            filename = data.get("filename", "")
            original_path = data.get("original_path", "")

            if project_dir and os.path.exists(os.path.join(project_dir, "materials", filename)):
                file_path = os.path.join(project_dir, "materials", filename)
            elif os.path.exists(original_path):
                file_path = original_path
            else:
                return (data.get("name", "Missing"), 1.5, data.get("is_defect", False))

            return (data.get("name", filename), file_path, data.get("is_defect", False))

        else:
            if "selected_variant" in data and data["selected_variant"]:
                return (data.get("name", "Unknown"), data["selected_variant"], data.get("is_defect", False))
            else:
                return (data.get("name", "Unknown"), data.get("id", ""), data.get("is_defect", False))


class TMM_Calculator:
    """Custom TMM (Transfer Matrix Method) calculator"""

    def __init__(self):
        self.material_cache = {}
        import numpy as np
        self.np = np

    def clear_cache(self):
        """Clear the material cache to force recalculation"""
        print("DEBUG: Clearing material cache")
        self.material_cache.clear()

    def get_refractive_index(self, material_id, wavelength):
        """Get refractive index with extrapolation ONLY - NO FALLBACKS"""
        if not isinstance(material_id, str):
            return material_id

        cache_key = f"{material_id}_{wavelength}"
        if cache_key in self.material_cache:
            return self.material_cache[cache_key]

        if material_id.endswith('.yml'):
            try:
                with open(material_id, 'r') as file:
                    material_data = yaml.safe_load(file)

                data_list = material_data.get('DATA', [])
                for data_item in data_list:
                    if data_item.get('type') == 'tabulated nk':
                        data_str = data_item.get('data', '')
                        if data_str:
                            lines = data_str.strip().split('\n')
                            wavelengths = []
                            n_values = []
                            k_values = []

                            for line in lines:
                                parts = line.strip().split()
                                if len(parts) >= 3:
                                    try:
                                        wl = float(parts[0]) * 1000
                                        n = float(parts[1])
                                        k = float(parts[2])
                                        wavelengths.append(wl)
                                        n_values.append(n)
                                        k_values.append(k)
                                    except (ValueError, IndexError):
                                        continue

                            if wavelengths:
                                import numpy as np
                                min_range = min(wavelengths)
                                max_range = max(wavelengths)

                                if wavelength < min_range:
                                    n = n_values[0]
                                    k = k_values[0]
                                    print(f"EXTRAPOLATION: YAML {material_id} at {wavelength}nm → using {min_range}nm value")
                                elif wavelength > max_range:
                                    n = n_values[-1]
                                    k = k_values[-1]
                                    print(f"EXTRAPOLATION: YAML {material_id} at {wavelength}nm → using {max_range}nm value")
                                else:
                                    n = np.interp(wavelength, wavelengths, n_values)
                                    k = np.interp(wavelength, wavelengths, k_values)

                                result = complex(n, k) if k > 0 else n
                                self.material_cache[cache_key] = result
                                return result

                raise ValueError(f"No optical data found in YAML file: {material_id}")

            except Exception as e:
                raise ValueError(f"Cannot load YAML material {material_id}: {e}")

        try:
            from refractiveindex import RefractiveIndexMaterial
            shelf, book, page = material_id.split('|')
            material_obj = RefractiveIndexMaterial(shelf=shelf, book=book, page=page)

            try:
                range_min = material_obj.material.refractiveIndex.rangeMin * 1000
                range_max = material_obj.material.refractiveIndex.rangeMax * 1000
            except AttributeError:
                n = material_obj.get_refractive_index(wavelength)
                
                try:
                    k = material_obj.get_extinction_coefficient(wavelength)
                    if k > 0:
                        n = complex(n, k)
                except:
                    pass
                    
                self.material_cache[cache_key] = n
                return n

            actual_wavelength = wavelength
            
            if wavelength < range_min:
                actual_wavelength = range_min
                print(f"EXTRAPOLATION: {material_id} at {wavelength}nm → using {range_min}nm value (below range)")
            elif wavelength > range_max:
                actual_wavelength = range_max
                print(f"EXTRAPOLATION: {material_id} at {wavelength}nm → using {range_max}nm value (above range)")

            n = material_obj.get_refractive_index(actual_wavelength)

            try:
                k = material_obj.get_extinction_coefficient(actual_wavelength)
                if k > 0:
                    n = complex(n, k)
            except:
                pass

            self.material_cache[cache_key] = n
            return n

        except Exception as e:
            raise ValueError(f"Cannot get refractive index for {material_id}: {e}")

    def calculate_reflection(self, stack, wavelengths, angle=0, show_progress=None):
        """Calculate reflection using custom TMM implementation"""
        import numpy as np

        R = np.zeros(len(wavelengths))

        for i, wavelength in enumerate(wavelengths):
            indices = []
            thicknesses = []

            for material, thickness in stack:
                n = self.get_refractive_index(material, wavelength)
                indices.append(n)
                thicknesses.append(thickness)

            r, t = self._calculate_tmm_matrices(indices, thicknesses, wavelength, angle)

            R[i] = np.abs(r) ** 2

            if R[i] > 1.0:
                print(f"Warning: Capping unphysical reflection value {R[i]} at wavelength {wavelength}nm")
                R[i] = 1.0

            if show_progress is not None and i % 10 == 0:
                progress = int((i + 1) / len(wavelengths) * 100)
                show_progress(progress)

        return R, {}

    def _calculate_tmm_matrices(self, indices, thicknesses, wavelength, angle):
        """Calculate reflection and transmission coefficients using TMM"""
        np = self.np
        wavelength_nm = wavelength

        num_layers = len(indices)
        M = np.eye(2, dtype=complex)

        for j in range(num_layers - 1):
            n1 = indices[j]
            n2 = indices[j + 1]
            d = thicknesses[j]

            if j == 0 and d == 0:
                continue

            if angle > 0:
                if isinstance(n1, complex) or isinstance(n2, complex):
                    theta1 = angle if j == 0 else np.arcsin((indices[0].real / n1.real) * np.sin(angle))
                    theta2 = np.arcsin((n1.real / n2.real) * np.sin(theta1))
                else:
                    theta1 = angle if j == 0 else np.arcsin((indices[0] / n1) * np.sin(angle))
                    theta2 = np.arcsin((n1 / n2) * np.sin(theta1))
            else:
                theta1 = 0
                theta2 = 0

            if np.abs(angle) > 0:
                r12 = (n2 * np.cos(theta1) - n1 * np.cos(theta2)) / (n2 * np.cos(theta1) + n1 * np.cos(theta2))
                t12 = (2 * n1 * np.cos(theta1)) / (n2 * np.cos(theta1) + n1 * np.cos(theta2))
            else:
                r12 = (n2 - n1) / (n2 + n1)
                t12 = 2 * n1 / (n2 + n1)

            I = (1 / t12) * np.array([[1, r12], [r12, 1]], dtype=complex)

            if j < num_layers - 2:
                thickness = thicknesses[j + 1]
                if thickness > 0:
                    if isinstance(n2, complex) or angle > 0:
                        k0 = 2 * np.pi / wavelength_nm
                        kz = n2 * k0 * np.cos(theta2)
                        phase = kz * thickness
                    else:
                        phase = 2 * np.pi * n2 * thickness / wavelength_nm

                    P = np.array([
                        [np.exp(-1j * phase), 0],
                        [0, np.exp(1j * phase)]
                    ], dtype=complex)

                    M = M @ I @ P
                else:
                    M = M @ I
            else:
                M = M @ I

        r = M[1, 0] / M[0, 0]
        t = 1 / M[0, 0]

        return r, t


class CustomMaterialDialog(QDialog):
    """Dialog for creating a custom material with refractive index values"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Add Custom Material")
        self.setup_ui()

    def setup_ui(self):
        """Setup the dialog UI"""
        layout = QVBoxLayout(self)

        form = QFormLayout()

        self.name_edit = QLineEdit()
        form.addRow("Material Name:", self.name_edit)

        self.id_edit = QLineEdit()
        self.id_edit.setMaxLength(3)
        form.addRow("Material ID (max 3 chars):", self.id_edit)

        self.n_spin = QDoubleSpinBox()
        self.n_spin.setRange(0.1, 10.0)
        self.n_spin.setValue(1.5)
        self.n_spin.setDecimals(6)
        self.n_spin.setSingleStep(0.1)
        form.addRow("Refractive Index (n):", self.n_spin)

        self.k_spin = QDoubleSpinBox()
        self.k_spin.setRange(0.0, 10.0)
        self.k_spin.setValue(0.0)
        self.k_spin.setDecimals(6)
        self.k_spin.setSingleStep(0.01)
        form.addRow("Extinction Coefficient (k):", self.k_spin)

        suggestion_layout = QHBoxLayout()

        glass_btn = QPushButton("Glass (n=1.5)")
        glass_btn.clicked.connect(lambda: self.apply_suggestion(1.5, 0.0))
        suggestion_layout.addWidget(glass_btn)

        water_btn = QPushButton("Water (n=1.33)")
        water_btn.clicked.connect(lambda: self.apply_suggestion(1.33, 0.0))
        suggestion_layout.addWidget(water_btn)

        gold_btn = QPushButton("Gold (n=0.3, k=3.0)")
        gold_btn.clicked.connect(lambda: self.apply_suggestion(0.3, 3.0))
        suggestion_layout.addWidget(gold_btn)

        form.addRow("Quick Select:", suggestion_layout)

        self.defect_checkbox = QCheckBox("Mark as defect material")
        form.addRow("", self.defect_checkbox)

        layout.addLayout(form)

        note = QLabel("Note: Custom materials have fixed refractive index values\n"
                      "that don't vary with wavelength.")
        note.setStyleSheet("color: gray; font-style: italic;")
        layout.addWidget(note)

        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.accepted.connect(self.validate)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

        self.setMinimumWidth(400)

    def apply_suggestion(self, n, k):
        """Apply a suggested material to the input fields"""
        self.n_spin.setValue(n)
        self.k_spin.setValue(k)

    def validate(self):
        """Validate the form before accepting"""
        if not self.name_edit.text().strip():
            QMessageBox.warning(self, "Invalid Input", "Please enter a material name.")
            return

        id_text = self.id_edit.text().strip()
        if not id_text:
            QMessageBox.warning(self, "Invalid Input", "Please enter a material ID (max 3 characters).")
            return
        
        if len(id_text) > 3:
            QMessageBox.warning(self, "Invalid Input", "Material ID cannot exceed 3 characters.")
            return
            
        if not id_text.isalnum():
            QMessageBox.warning(self, "Invalid Input", "Material ID can only contain letters and numbers.")
            return

        self.accept()


class MaterialTable(QTableWidget):
    """Table widget for displaying the list of materials"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setColumnCount(4)
        self.setHorizontalHeaderLabels(["ID", "Material", "Defect", "Remove"])

        self.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)

        self.setSelectionBehavior(QTableWidget.SelectRows)
        self.material_colors = {}

    def add_material(self, label, material_name, material_id, is_defect=False):
        """Add a material to the table with clean display"""
        row = self.rowCount()
        self.insertRow(row)

        label_item = QTableWidgetItem(label)
        label_item.setFlags(label_item.flags() & ~Qt.ItemIsEditable)
        self.setItem(row, 0, label_item)

        material_item = QTableWidgetItem(material_name)
        material_item.setFlags(material_item.flags() & ~Qt.ItemIsEditable)
        material_item.setData(Qt.UserRole, material_id)
        self.setItem(row, 1, material_item)

        defect_item = QTableWidgetItem("Yes" if is_defect else "No")
        defect_item.setFlags(defect_item.flags() & ~Qt.ItemIsEditable)
        self.setItem(row, 2, defect_item)

        remove_btn = QPushButton("×")
        remove_btn.setMaximumWidth(30)
        remove_btn.clicked.connect(lambda: self.removeRow(self.indexAt(remove_btn.pos()).row()))
        self.setCellWidget(row, 3, remove_btn)

        if label not in self.material_colors:
            color = QColor(random.randint(20, 240), random.randint(20, 240), random.randint(20, 240))
            self.material_colors[label] = color

        return row

    def get_materials(self):
        """Return a dictionary of all materials"""
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

    def update_material_variant(self, label, variant_id):
        """Update a material's variant after selection - FIXED"""
        print(f"DEBUG: Updating material {label} with variant {variant_id}")
        
        for row in range(self.rowCount()):
            if self.item(row, 0).text() == label:
                material_item = self.item(row, 1)
                material_item.setData(Qt.UserRole, variant_id)
                
                print(f"SUCCESS: Material {label} updated to variant: {variant_id}")
                print(f"DEBUG: Stored data is now: {material_item.data(Qt.UserRole)}")
                return True
        
        print(f"ERROR: Material {label} not found in table")
        return False


class ArrayTable(QTableWidget):
    """Table widget for displaying arrays of materials"""

    def __init__(self, material_table, parent=None):
        super().__init__(parent)
        self.setColumnCount(4)
        self.setHorizontalHeaderLabels(["ID", "Definition", "Layers", "Remove"])

        self.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)

        self.setSelectionBehavior(QTableWidget.SelectRows)
        self.material_table = material_table

    def add_array(self, definition):
        """Add an array to the table"""
        row = self.rowCount()
        self.insertRow(row)

        array_id = f"M{row + 1}"

        id_item = QTableWidgetItem(array_id)
        id_item.setFlags(id_item.flags() & ~Qt.ItemIsEditable)
        self.setItem(row, 0, id_item)

        def_item = QTableWidgetItem(definition)
        def_item.setFlags(def_item.flags() & ~Qt.ItemIsEditable)
        self.setItem(row, 1, def_item)

        layers = definition.split("*")
        layers_item = QTableWidgetItem(str(len(layers)))
        layers_item.setFlags(layers_item.flags() & ~Qt.ItemIsEditable)
        self.setItem(row, 2, layers_item)

        remove_btn = QPushButton("×")
        remove_btn.setMaximumWidth(30)
        remove_btn.clicked.connect(lambda: self.removeRow(self.indexAt(remove_btn.pos()).row()))
        self.setCellWidget(row, 3, remove_btn)

        return row

    def get_arrays(self):
        """Return a dictionary of all arrays"""
        arrays = {}
        for row in range(self.rowCount()):
            array_id = self.item(row, 0).text()
            definition = self.item(row, 1).text()
            arrays[array_id] = definition
        return arrays

    def validate_definition(self, definition):
        """Validate an array definition against existing materials"""
        materials = self.material_table.get_materials()

        parts = definition.split("*")

        for part in parts:
            part = part.strip()
            if part not in materials:
                return False, f"Material '{part}' not found"

            if materials[part][2]:
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
                y_center = (y_min + y_max) / 2
                y_min = y_center - 5
                y_max = y_center + 5

            y_range = y_max - y_min
            self.ax.set_ylim(y_min - 0.1 * y_range, y_max + 0.1 * y_range)

        self.ax.grid(True, linestyle='--', alpha=0.7)
        self.figure.tight_layout()
        self.canvas.draw()


class ThicknessEditDialog(QDialog):
    """Dialog for editing layer thicknesses in an array"""

    def __init__(self, array_definition, array_thicknesses, default_thickness, parent=None):
        super().__init__(parent)
        self.array_definition = array_definition
        self.array_thicknesses = array_thicknesses.copy() if array_thicknesses else {}
        self.default_thickness = default_thickness
        self.setWindowTitle(f"Edit Thicknesses - {array_definition}")
        self.setMinimumSize(400, 300)
        self.setup_ui()

    def setup_ui(self):
        """Setup the dialog UI"""
        layout = QVBoxLayout(self)

        # Info label
        info_label = QLabel(f"Array Definition: {self.array_definition}")
        info_label.setStyleSheet("font-weight: bold; margin-bottom: 10px;")
        layout.addWidget(info_label)

        # Parse layers from definition
        layers = self.array_definition.split("*")

        # Create table for thickness editing
        self.thickness_table = QTableWidget()
        self.thickness_table.setColumnCount(3)
        self.thickness_table.setHorizontalHeaderLabels(["Layer", "Material", "Thickness (nm)"])
        self.thickness_table.setRowCount(len(layers))

        # Configure table
        self.thickness_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.thickness_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.thickness_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)

        # Store widgets for easy access
        self.thickness_widgets = []

        # Populate table
        for i, layer in enumerate(layers):
            layer = layer.strip()
            layer_key = f"layer_{i}"  # Position-based key instead of material name

            # Layer number
            layer_item = QTableWidgetItem(f"Layer {i + 1}")
            layer_item.setFlags(layer_item.flags() & ~Qt.ItemIsEditable)
            self.thickness_table.setItem(i, 0, layer_item)

            # Material name
            material_item = QTableWidgetItem(layer)
            material_item.setFlags(material_item.flags() & ~Qt.ItemIsEditable)
            self.thickness_table.setItem(i, 1, material_item)

            # Thickness input
            thickness_widget = QWidget()
            thickness_layout = QHBoxLayout(thickness_widget)
            thickness_layout.setContentsMargins(5, 2, 5, 2)

            thickness_spinbox = QDoubleSpinBox()
            thickness_spinbox.setRange(1, 10000)
            thickness_spinbox.setDecimals(1)
            thickness_spinbox.setSingleStep(10.0)
            thickness_spinbox.setSuffix(" nm")

            # Set current value or default using position-based key
            current_thickness = self.array_thicknesses.get(layer_key, None)
            if current_thickness is not None:
                thickness_spinbox.setValue(current_thickness)
            else:
                thickness_spinbox.setValue(self.default_thickness)

            # Add default checkbox
            default_checkbox = QCheckBox("Default")
            if current_thickness is None:
                default_checkbox.setChecked(True)
                thickness_spinbox.setEnabled(False)

            # Store widget references
            widget_info = {
                'spinbox': thickness_spinbox,
                'checkbox': default_checkbox,
                'layer_key': layer_key,
                'material_name': layer
            }
            self.thickness_widgets.append(widget_info)

            def make_toggle_function(widgets):
                def toggle_default(checked):
                    widgets['spinbox'].setEnabled(not checked)
                    if checked:
                        widgets['spinbox'].setValue(self.default_thickness)

                return toggle_default

            default_checkbox.toggled.connect(make_toggle_function(widget_info))

            thickness_layout.addWidget(thickness_spinbox)
            thickness_layout.addWidget(default_checkbox)

            self.thickness_table.setCellWidget(i, 2, thickness_widget)

        layout.addWidget(self.thickness_table)

        # Add buttons for bulk operations
        bulk_layout = QHBoxLayout()

        set_all_btn = QPushButton("Set All to Default")
        set_all_btn.clicked.connect(self.set_all_default)
        bulk_layout.addWidget(set_all_btn)

        bulk_layout.addStretch()

        layout.addLayout(bulk_layout)

        # Dialog buttons
        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

    def set_all_default(self):
        """Set all layers to use default thickness"""
        for widget_info in self.thickness_widgets:
            widget_info['checkbox'].setChecked(True)

    def get_thicknesses(self):
        """Get the thickness values from the dialog using position-based keys"""
        thicknesses = {}
        for widget_info in self.thickness_widgets:
            layer_key = widget_info['layer_key']
            checkbox = widget_info['checkbox']
            spinbox = widget_info['spinbox']

            if not checkbox.isChecked():
                thicknesses[layer_key] = spinbox.value()
            # If checkbox is checked, we don't store the thickness (use default)

        return thicknesses


class TMM_Worker(QThread):
    """Worker thread for TMM calculations"""

    finished = pyqtSignal(object, object, object)
    error = pyqtSignal(str)
    progress = pyqtSignal(int)

    def __init__(self, stack, wavelengths, angle, parent=None):
        super().__init__(parent)
        self.stack = stack
        self.wavelengths = wavelengths
        self.angle = angle

    def run(self):
        try:
            calculator = TMM_Calculator()

            def update_progress(percent):
                self.progress.emit(percent)

            R_TM, problematic = calculator.calculate_reflection(
                self.stack, self.wavelengths, self.angle, update_progress
            )

            self.finished.emit(self.wavelengths, R_TM, problematic)

        except Exception as e:
            error_msg = f"Error: {str(e)}\n{traceback.format_exc()}"
            self.error.emit(error_msg)


class ArrayTable(QTableWidget):
    """Enhanced table widget for displaying arrays with thickness editing"""

    def __init__(self, material_table, parent=None):
        super().__init__(parent)
        self.setColumnCount(5)  # Added Edit column
        self.setHorizontalHeaderLabels(["ID", "Definition", "Layers", "Edit", "Remove"])

        self.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeToContents)

        self.setSelectionBehavior(QTableWidget.SelectRows)
        self.material_table = material_table

        # Store thickness data for each array
        self.array_thicknesses = {}  # {array_id: {layer_id: thickness}}

    def add_array(self, definition):
        """Add an array to the table"""
        row = self.rowCount()
        self.insertRow(row)

        array_id = f"M{row + 1}"

        id_item = QTableWidgetItem(array_id)
        id_item.setFlags(id_item.flags() & ~Qt.ItemIsEditable)
        self.setItem(row, 0, id_item)

        def_item = QTableWidgetItem(definition)
        def_item.setFlags(def_item.flags() & ~Qt.ItemIsEditable)
        self.setItem(row, 1, def_item)

        layers = definition.split("*")
        layers_item = QTableWidgetItem(str(len(layers)))
        layers_item.setFlags(layers_item.flags() & ~Qt.ItemIsEditable)
        self.setItem(row, 2, layers_item)

        # Edit button
        edit_btn = QPushButton("Edit Thickness")
        edit_btn.clicked.connect(lambda: self.edit_array_thickness(row))
        self.setCellWidget(row, 3, edit_btn)

        # Remove button
        remove_btn = QPushButton("×")
        remove_btn.setMaximumWidth(30)
        remove_btn.clicked.connect(lambda: self.remove_array(row))
        self.setCellWidget(row, 4, remove_btn)

        # Initialize empty thickness data for this array
        self.array_thicknesses[array_id] = {}

        return row

    def remove_array(self, row):
        """Remove an array and clean up its thickness data"""
        if row < self.rowCount():
            array_id = self.item(row, 0).text()
            if array_id in self.array_thicknesses:
                del self.array_thicknesses[array_id]
            self.removeRow(row)

            # Update array IDs for remaining rows
            for r in range(self.rowCount()):
                new_id = f"M{r + 1}"
                self.item(r, 0).setText(new_id)

    def edit_array_thickness(self, row):
        """Open thickness editing dialog for an array"""
        array_id = self.item(row, 0).text()
        definition = self.item(row, 1).text()

        # Get default thickness from parent (main window)
        default_thickness = 100  # Default fallback
        if hasattr(self.parent(), 'default_thickness'):
            default_thickness = self.parent().default_thickness.value()
        elif hasattr(self.parent(), 'parent') and hasattr(self.parent().parent(), 'default_thickness'):
            default_thickness = self.parent().parent().default_thickness.value()

        current_thicknesses = self.array_thicknesses.get(array_id, {})

        dialog = ThicknessEditDialog(definition, current_thicknesses, default_thickness, self)

        if dialog.exec_() == QDialog.Accepted:
            # Update stored thicknesses
            self.array_thicknesses[array_id] = dialog.get_thicknesses()
            print(f"Updated thicknesses for {array_id}: {self.array_thicknesses[array_id]}")

    def get_arrays(self):
        """Return a dictionary of all arrays"""
        arrays = {}
        for row in range(self.rowCount()):
            array_id = self.item(row, 0).text()
            definition = self.item(row, 1).text()
            arrays[array_id] = definition
        return arrays

    def get_array_thicknesses(self):
        """Return thickness data for all arrays"""
        return self.array_thicknesses.copy()

    def set_array_thicknesses(self, thicknesses_data):
        """Set thickness data (used when loading projects)"""
        self.array_thicknesses = thicknesses_data.copy()

    def validate_definition(self, definition):
        """Validate an array definition against existing materials"""
        materials = self.material_table.get_materials()

        parts = definition.split("*")

        for part in parts:
            part = part.strip()
            if part not in materials:
                return False, f"Material '{part}' not found"

            if materials[part][2]:
                return False, f"Cannot use defect material '{part}' in array definition"

        return True, ""


class OpticalFilterApp(QMainWindow):
    """Main application window"""

    def __init__(self):
        super().__init__()

        self.material_api = MaterialSearchAPI()
        self.recent_files = []
        self.load_recent_files()

        self.setup_menu_bar()
        self.setup_ui()

        self.setWindowTitle("Optical Filter Designer & TMM Calculator")
        self.setMinimumSize(900, 700)
        self.setStatusBar(self.statusBar())

        self.show()

    def setup_menu_bar(self):
        """Setup the application menu bar"""
        self.menu_bar = QMenuBar(self)
        self.setMenuBar(self.menu_bar)

        self.file_menu = QMenu("File", self)
        self.menu_bar.addMenu(self.file_menu)

        save_action = QAction("Save Filter", self)
        save_action.setShortcut("Ctrl+S")
        save_action.triggered.connect(self.save_filter)
        self.file_menu.addAction(save_action)

        self.file_menu.addSeparator()
        self.recent_menu_actions = []

        for i in range(8):
            action = QAction("", self)
            action.setVisible(False)
            action.setData(i)
            action.triggered.connect(self.open_recent_file_from_action)
            self.recent_menu_actions.append(action)
            self.file_menu.addAction(action)

        self.update_recent_files_menu()

        self.file_menu.addSeparator()
        browse_action = QAction("Browse...", self)
        browse_action.setShortcut("Ctrl+O")
        browse_action.triggered.connect(self.browse_filter)
        self.file_menu.addAction(browse_action)

        self.database_menu = QMenu("Database", self)
        self.menu_bar.addMenu(self.database_menu)

        refresh_action = QAction("Update Materials Database", self)
        refresh_action.triggered.connect(self.refresh_database)
        self.database_menu.addAction(refresh_action)

    def _check_bracket_matching(self, text):
        """Check if brackets are properly matched"""
        stack = []
        pairs = {'(': ')', '[': ']', '{': '}'}
        
        for char in text:
            if char in pairs:
                stack.append(char)
            elif char in pairs.values():
                if not stack:
                    return False
                if pairs[stack.pop()] != char:
                    return False
        
        return len(stack) == 0

    def refresh_database(self):
        """Force refresh the refractiveindex.info database"""
        reply = QMessageBox.question(self, "Refresh Database",
                                     "Are you sure you want to update the materials database? This may take a few minutes.",
                                     QMessageBox.Yes | QMessageBox.No, QMessageBox.No)

        if reply == QMessageBox.Yes:
            self.statusBar().showMessage("Updating materials database...")

            if os.path.exists(self.material_api.db_cache_path):
                os.remove(self.material_api.db_cache_path)

            self.material_api._download_and_cache_database()
            self.search_materials()
            self.statusBar().showMessage("Materials database updated successfully!", 3000)

    def browse_material(self):
        """Open a file dialog to browse for a material file"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Select Material File", "", "YAML Files (*.yml);;All Files (*)"
        )

        if not file_path:
            return

        try:
            with open(file_path, 'r') as file:
                material_data = yaml.safe_load(file)

            material_name = os.path.basename(file_path).replace('.yml', '')

            if 'DATA' not in material_data:
                raise ValueError("Material file does not contain DATA section")

            data_type = None
            for data_item in material_data['DATA']:
                if 'type' in data_item:
                    data_type = data_item['type']

            if not data_type:
                raise ValueError("Material file does not specify data type")

            dialog = QDialog(self)
            dialog.setWindowTitle("Material Details")
            layout = QVBoxLayout(dialog)

            form = QFormLayout()

            name_edit = QLineEdit(material_name)
            form.addRow("Material Name:", name_edit)

            default_id = material_name[:3].upper() if len(material_name) >= 3 else material_name.upper()
            id_edit = QLineEdit(default_id)
            id_edit.setMaxLength(3)
            form.addRow("Material ID:", id_edit)

            defect_checkbox = QCheckBox("Mark as defect material")
            form.addRow("", defect_checkbox)

            form.addRow("File:", QLabel(os.path.basename(file_path)))
            form.addRow("Type:", QLabel(data_type))

            layout.addLayout(form)

            button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
            button_box.accepted.connect(dialog.accept)
            button_box.rejected.connect(dialog.reject)
            layout.addWidget(button_box)

            if dialog.exec_() == QDialog.Accepted:
                material_name = name_edit.text()
                material_id = id_edit.text()
                is_defect = defect_checkbox.isChecked()

                if not self.material_table.is_label_unique(material_id):
                    QMessageBox.warning(self, "Duplicate ID", f"Material ID '{material_id}' is already in use.")
                    return

                self.material_table.add_material(material_id, material_name, file_path, is_defect)

                count = self.material_table.rowCount()
                self.material_count_label.setText(f"{count}/100 materials defined")

                self.statusBar().showMessage(f"Material '{material_name}' added from {os.path.basename(file_path)}", 3000)

        except Exception as e:
            QMessageBox.critical(self, "Error Loading Material", f"Failed to load material: {str(e)}")

    def add_custom_material(self):
        """Open a dialog to create a custom material"""
        if self.material_table.rowCount() >= 100:
            QMessageBox.warning(self, "Maximum Reached", "Cannot add more than 100 materials.")
            return

        dialog = CustomMaterialDialog(self)

        if dialog.exec_() == QDialog.Accepted:
            material_name = dialog.name_edit.text()
            material_id = dialog.id_edit.text()
            is_defect = dialog.defect_checkbox.isChecked()
            n_value = dialog.n_spin.value()
            k_value = dialog.k_spin.value()

            if not self.material_table.is_label_unique(material_id):
                QMessageBox.warning(self, "Duplicate ID", f"Material ID '{material_id}' is already in use.")
                return

            refractive_index = complex(n_value, k_value) if k_value > 0 else n_value
            self.material_table.add_material(material_id, material_name, refractive_index, is_defect)

            count = self.material_table.rowCount()
            self.material_count_label.setText(f"{count}/100 materials defined")

            self.statusBar().showMessage(f"Custom material '{material_name}' added", 3000)

    def open_recent_file_from_action(self):
        """Open a file from the recent files list using the sender's data"""
        action = self.sender()
        if action:
            index = action.data()
            self.open_recent_file(index)

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
        self.browse_material_btn.clicked.connect(self.browse_material)
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
        self.calculate_btn.clicked.connect(self.calculate_tmm)
        params_layout.addWidget(self.calculate_btn)

        self.save_btn = QPushButton("Save Filter")
        self.save_btn.setStyleSheet("padding: 8px;")
        self.save_btn.clicked.connect(self.save_filter)
        params_layout.addWidget(self.save_btn)

        params_layout.addStretch()

        self.tmm_plots = TMM_Plots()

        layout.addWidget(params_widget, 1)
        layout.addWidget(self.tmm_plots, 2)

        parent_layout.addWidget(group_box)

    def save_filter(self):
        """Save the current filter configuration with thickness data"""
        base_dir = QFileDialog.getExistingDirectory(
            self, "Select Folder to Save Project", "", QFileDialog.ShowDirsOnly
        )

        if not base_dir:
            return

        from PyQt5.QtWidgets import QInputDialog
        project_name, ok = QInputDialog.getText(
            self, "Project Name", "Enter a name for your filter project:"
        )

        if not ok or not project_name:
            return

        project_dir = os.path.join(base_dir, project_name)

        try:
            if os.path.exists(project_dir):
                reply = QMessageBox.question(
                    self, "Directory Exists",
                    f"Directory '{project_name}' already exists. Overwrite?",
                    QMessageBox.Yes | QMessageBox.No, QMessageBox.No
                )
                if reply != QMessageBox.Yes:
                    return

            os.makedirs(project_dir, exist_ok=True)

            materials_dir = os.path.join(project_dir, "materials")
            os.makedirs(materials_dir, exist_ok=True)

            materials_data = {}
            for label, material in self.material_table.get_materials().items():
                try:
                    materials_data[label] = MaterialHandler.serialize_material(material)

                    _, material_id, _ = material
                    if isinstance(material_id, str) and material_id.endswith('.yml'):
                        original_file = material_id
                        if os.path.exists(original_file):
                            target_file = os.path.join(materials_dir, os.path.basename(original_file))
                            try:
                                with open(original_file, 'r') as src, open(target_file, 'w') as dst:
                                    dst.write(src.read())
                            except Exception as e:
                                print(f"Warning: Could not copy material file {original_file}: {e}")
                except Exception as e:
                    print(f"Error processing material {label}: {e}")

            filter_data = {
                "materials": materials_data,
                "arrays": self.array_table.get_arrays(),
                "array_thicknesses": self.array_table.get_array_thicknesses(),  # NEW: Save thickness data
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
                }
            }

            filter_file = os.path.join(project_dir, "filter_config.json")
            with open(filter_file, "w") as f:
                json.dump(filter_data, f, indent=2)

            if hasattr(self, 'last_calculation_data'):
                wavelengths = self.last_calculation_data['wavelengths']
                r_tm = self.last_calculation_data['R_TM']

                csv_file = os.path.join(project_dir, "reflection_data.csv")
                with open(csv_file, "w") as f:
                    f.write("Wavelength (nm),Reflection\n")
                    for i in range(len(wavelengths)):
                        f.write(f"{wavelengths[i]},{r_tm[i]}\n")

            self.add_to_recent_files(project_dir)
            self.statusBar().showMessage(f"Filter project saved to {project_name}", 3000)

        except Exception as e:
            error_msg = f"Error saving filter: {str(e)}\n{traceback.format_exc()}"
            QMessageBox.critical(self, "Save Error", error_msg)

    def load_filter(self, project_path):
        """Load a filter configuration from a project directory with thickness data"""
        try:
            if os.path.isdir(project_path):
                filter_file = os.path.join(project_path, "filter_config.json")
                if not os.path.exists(filter_file):
                    raise FileNotFoundError(f"Filter configuration file not found in {project_path}")

                with open(filter_file, "r") as f:
                    data = json.load(f)
            else:
                with open(project_path, "r") as f:
                    data = json.load(f)

            self.material_table.setRowCount(0)
            self.array_table.setRowCount(0)

            for label, material_data in data["materials"].items():
                try:
                    material = MaterialHandler.deserialize_material(material_data, project_path)
                    name, material_id, is_defect = material
                    self.material_table.add_material(label, name, material_id, is_defect)
                except Exception as e:
                    print(f"Error loading material {label}: {e}")

            if "material_colors" in data:
                for label, color_name in data["material_colors"].items():
                    self.material_table.material_colors[label] = QColor(color_name)

            for array_id, definition in data["arrays"].items():
                self.array_table.add_array(definition)

            # Load thickness data if available
            if "array_thicknesses" in data:
                self.array_table.set_array_thicknesses(data["array_thicknesses"])

            material_count = self.material_table.rowCount()
            self.material_count_label.setText(f"{material_count}/100 materials defined")

            array_count = self.array_table.rowCount()
            self.array_count_label.setText(f"{array_count}/20 arrays defined")

            self.filter_entry.setText(data["filter"])
            self.validate_filter()

            calc = data["calculation"]
            self.wavelength_start.setValue(calc["wavelength_start"])
            self.wavelength_end.setValue(calc["wavelength_end"])
            self.wavelength_steps.setValue(calc["wavelength_steps"])
            self.incident_angle.setValue(calc["incident_angle"])
            self.default_thickness.setValue(calc["default_thickness"])

            try:
                csv_file = os.path.join(project_path, "reflection_data.csv")
                if os.path.exists(csv_file):
                    wavelengths = []
                    r_tm = []

                    with open(csv_file, "r") as f:
                        next(f)
                        for line in f:
                            parts = line.strip().split(',')
                            if len(parts) >= 2:
                                wavelengths.append(float(parts[0]))
                                r_tm.append(float(parts[1]))

                    if wavelengths and r_tm:
                        wavelengths = np.array(wavelengths)
                        r_tm = np.array(r_tm)

                        self.last_calculation_data = {
                            'wavelengths': wavelengths,
                            'R_TM': r_tm
                        }

                        self.tmm_plots.plot_results(wavelengths, None, r_tm)
            except Exception as plot_error:
                print(f"Error loading plot data: {plot_error}")

            self.add_to_recent_files(project_path)
            self.statusBar().showMessage(f"Filter loaded from {os.path.basename(project_path)}", 3000)

        except Exception as e:
            QMessageBox.critical(self, "Load Error", f"Error loading filter: {str(e)}")

    def browse_filter(self):
        """Open a file dialog to browse for a filter file or project"""
        from PyQt5.QtWidgets import QDialog, QVBoxLayout, QPushButton, QLabel

        dialog = QDialog(self)
        dialog.setWindowTitle("Load Filter")
        layout = QVBoxLayout(dialog)

        layout.addWidget(QLabel("What type of filter would you like to load?"))

        project_btn = QPushButton("Load Project Folder")
        project_btn.clicked.connect(lambda: dialog.done(1))
        layout.addWidget(project_btn)

        file_btn = QPushButton("Load Single File (Legacy)")
        file_btn.clicked.connect(lambda: dialog.done(2))
        layout.addWidget(file_btn)

        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(lambda: dialog.done(0))
        layout.addWidget(cancel_btn)

        result = dialog.exec_()

        if result == 1:
            project_dir = QFileDialog.getExistingDirectory(
                self, "Select Filter Project Directory", "", QFileDialog.ShowDirsOnly
            )
            if project_dir:
                self.load_filter(project_dir)
        elif result == 2:
            file_path, _ = QFileDialog.getOpenFileName(
                self, "Open Filter File", "", "Filter Files (*.filter);;All Files (*)"
            )
            if file_path:
                self.load_filter(file_path)

    def open_recent_file(self, index):
        """Open a file from the recent files list"""
        if index < len(self.recent_files):
            path = self.recent_files[index]
            if os.path.exists(path):
                self.load_filter(path)
            else:
                QMessageBox.warning(self, "Not Found",
                                    f"The file or directory {path} no longer exists.")
                self.recent_files.pop(index)
                self.update_recent_files_menu()
                self.save_recent_files()

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
                file_name = os.path.basename(file_path)
                action.setText(f"{i + 1}. {file_name}")
                action.setVisible(True)
            else:
                action.setText("")
                action.setVisible(False)

    def add_to_recent_files(self, file_path):
        """Add a file to the recent files list"""
        if file_path in self.recent_files:
            self.recent_files.remove(file_path)

        self.recent_files.insert(0, file_path)
        self.recent_files = self.recent_files[:8]

        self.update_recent_files_menu()
        self.save_recent_files()

    def search_materials(self):
        """Search materials with cleaned display names"""
        query = self.search_field.text()
        all_results = self.material_api.search_materials(query)

        unique_materials = {}
        for material_id, material_name in all_results:
            clean_name = self.clean_material_name(material_name)

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

            if "µm" in base_name or "nm" in base_name:
                index = min(
                    base_name.find("µm") if "µm" in base_name else len(base_name),
                    base_name.find("nm") if "nm" in base_name else len(base_name),
                    base_name.find(":") if ":" in base_name else len(base_name)
                )
                base_name = base_name[:index].strip()

            if base_name.strip() == "":
                base_name = clean_name

            if base_name not in unique_materials:
                unique_materials[base_name] = []
            unique_materials[base_name].append((material_id, clean_name))

        self.material_dropdown.clear()
        for base_name in sorted(unique_materials.keys()):
            self.material_dropdown.addItem(base_name)
            index = self.material_dropdown.count() - 1
            self.material_dropdown.setItemData(index, unique_materials[base_name], Qt.UserRole)

    def clean_material_name(self, name):
        """Clean up HTML tags and format material names properly"""
        subscript_map = {
            '0': '₀', '1': '₁', '2': '₂', '3': '₃', '4': '₄',
            '5': '₅', '6': '₆', '7': '₇', '8': '₈', '9': '₉'
        }

        result = name
        while "<sub>" in result and "</sub>" in result:
            start = result.find("<sub>")
            end = result.find("</sub>")
            if start < end:
                sub_content = result[start + 5:end]
                subscripted = ''.join([subscript_map.get(c, c) for c in sub_content])
                result = result[:start] + subscripted + result[end + 6:]

        return result

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
        material_variants = self.material_dropdown.itemData(selected_index, Qt.UserRole)
        is_defect = self.defect_checkbox.isChecked()

        if not label:
            QMessageBox.warning(self, "Invalid Label", "Please enter a label (max 3 characters).")
            return

        if not self.material_table.is_label_unique(label):
            QMessageBox.warning(self, "Duplicate Label", f"Label '{label}' is already in use.")
            return

        variants_data = {
            "base_name": base_name,
            "variants": material_variants
        }

        variants_json = json.dumps(variants_data)
        self.material_table.add_material(label, base_name, variants_json, is_defect)

        count = self.material_table.rowCount()
        self.material_count_label.setText(f"{count}/100 materials defined")

        self.label_entry.clear()
        self.defect_checkbox.setChecked(False)

    def add_array(self):
        """Add an array to the definitions"""
        if self.array_table.rowCount() >= 20:
            QMessageBox.warning(self, "Maximum Reached", "Cannot add more than 20 arrays.")
            return

        definition = self.array_def_entry.text().strip()

        if not definition:
            QMessageBox.warning(self, "Empty Definition", "Please enter an array definition.")
            return

        valid, message = self.array_table.validate_definition(definition)
        if not valid:
            self.array_warning_label.setText(message)
            return

        self.array_warning_label.setText("")
        self.array_table.add_array(definition)

        count = self.array_table.rowCount()
        self.array_count_label.setText(f"{count}/20 arrays defined")

        self.array_def_entry.clear()

    def validate_filter(self):
        """Validate the optical filter definition - ENHANCED"""
        filter_def = self.filter_entry.text().strip()

        if not filter_def:
            self.filter_status_label.setText("Please enter a filter definition.")
            self.filter_status_label.setStyleSheet("color: red;")
            return False

        if not self._check_bracket_matching(filter_def):
            self.filter_status_label.setText("Mismatched brackets in filter definition.")
            self.filter_status_label.setStyleSheet("color: red;")
            return False
        
        valid_chars = set('ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789()^*[]')
        if not set(filter_def).issubset(valid_chars):
            invalid_chars = set(filter_def) - valid_chars
            self.filter_status_label.setText(f"Invalid characters: {', '.join(invalid_chars)}")
            self.filter_status_label.setStyleSheet("color: red;")
            return False

        arrays = self.array_table.get_arrays()
        materials = self.material_table.get_materials()
        valid_syntax = True

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

        if not filter_def:
            QMessageBox.warning(self, "No Filter", "Please define a filter first.")
            return

        if not self.validate_filter():
            QMessageBox.warning(self, "Invalid Filter", "Please correct the filter definition first.")
            return

        self.visualization_window.set_filter(filter_def)
        self.visualization_window.show()
        self.visualization_window.activateWindow()

    def calculate_tmm(self):
        """Calculate TMM with custom thickness values"""
        filter_def = self.filter_entry.text().strip()

        if not filter_def:
            QMessageBox.warning(self, "No Filter", "Please define an optical filter first.")
            return

        if not self.validate_filter():
            QMessageBox.warning(self, "Invalid Filter", "Please fix the filter definition errors first.")
            return

        start = self.wavelength_start.value()
        end = self.wavelength_end.value()
        steps = self.wavelength_steps.value()

        if start >= end:
            QMessageBox.warning(self, "Invalid Range", "Start wavelength must be less than end wavelength.")
            return

        if steps <= 10:
            QMessageBox.warning(self, "Invalid Steps", "Number of steps must be at least 10.")
            return

        # Clear cache before material compatibility check
        if hasattr(self, 'tmm_calculator'):
            self.tmm_calculator.clear_cache()

        incompatible_materials = self.check_materials_compatibility()

        if incompatible_materials:
            message = "⚠️  WAVELENGTH RANGE WARNING\n\n"
            message += f"Your calculation range: {start:.1f} - {end:.1f} nm\n\n"
            message += "The following materials need extrapolation:\n\n"

            for material_id, range_tuple in incompatible_materials:
                min_range, max_range = range_tuple

                if min_range == 0 and max_range == 0:
                    message += f"• {material_id}: No wavelength data available\n"
                else:
                    message += f"• {material_id}: Available {min_range:.1f} - {max_range:.1f} nm\n"

                    if start < min_range:
                        message += f"  → Below range: {start:.1f} nm will use {min_range:.1f} nm value\n"

                    if end > max_range:
                        message += f"  → Above range: {end:.1f} nm will use {max_range:.1f} nm value\n"

                    message += "\n"

            message += "\n🤔 How would you like to proceed?\n\n"
            message += "✅ Continue: Use extrapolated values (recommended for small ranges)\n"
            message += "❌ Cancel: Adjust wavelength range or materials"

            from PyQt5.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QTextEdit

            dialog = QDialog(self)
            dialog.setWindowTitle("Wavelength Extrapolation Required")
            dialog.setMinimumSize(600, 400)

            layout = QVBoxLayout()

            text_area = QTextEdit()
            text_area.setPlainText(message)
            text_area.setReadOnly(True)
            layout.addWidget(text_area)

            button_layout = QHBoxLayout()
            continue_btn = QPushButton("✅ Continue with Extrapolation")
            cancel_btn = QPushButton("❌ Cancel Calculation")

            continue_btn.clicked.connect(lambda: dialog.done(QDialog.Accepted))
            cancel_btn.clicked.connect(lambda: dialog.done(QDialog.Rejected))

            button_layout.addWidget(continue_btn)
            button_layout.addWidget(cancel_btn)
            layout.addLayout(button_layout)

            dialog.setLayout(layout)

            result = dialog.exec_()

            if result != QDialog.Accepted:
                return
            else:
                print("User accepted wavelength extrapolation. Proceeding with calculation...")

        wavelengths = np.linspace(start, end, steps)
        angle = self.incident_angle.value() * np.pi / 180
        default_thickness = self.default_thickness.value()

        try:
            expanded_filter = self.visualization_window.filter_visualizer.expand_filter_for_calculation(filter_def)
            expanded_filter = [layer for layer in expanded_filter if layer != "..."]

            materials_dict = self.material_table.get_materials()
            arrays_dict = self.array_table.get_arrays()
            array_thicknesses = self.array_table.get_array_thicknesses()

            print("\n" + "=" * 50)
            print("MATERIALS BEING USED IN CALCULATION:")
            print("=" * 50)
            for label, (name, material_data, is_defect) in materials_dict.items():
                print(f"  {label}: {name} → material_data: {material_data}")
                print(f"       Type: {type(material_data)}, Defect: {is_defect}")
            print("=" * 50)

            stack = []
            stack.append((1.0, 0))  # Air substrate

            print("\nBUILDING STACK WITH THICKNESS:")

            # Track original filter for array mapping
            original_filter_pattern = filter_def
            array_usage_map = {}  # Track which expanded layers belong to which arrays

            # First, map expanded layers to their source arrays
            temp_expanded = filter_def
            pattern = r'\(([^)]+)\)\^(\d+)'

            while re.search(pattern, temp_expanded):
                match = re.search(pattern, temp_expanded)
                array_id = match.group(1)
                repetitions = int(match.group(2))

                if array_id in arrays_dict:
                    array_def = arrays_dict[array_id]
                    array_layers = array_def.split("*")

                    # For each repetition, map the layers
                    for rep in range(repetitions):
                        for layer_pos, layer_name in enumerate(array_layers):
                            expanded_index = len(array_usage_map)
                            array_usage_map[expanded_index] = {
                                'array_id': array_id,
                                'layer_position': layer_pos,
                                'material': layer_name.strip()
                            }

                    replacement = "*".join([array_id] * repetitions)
                    temp_expanded = temp_expanded[:match.start()] + replacement + temp_expanded[match.end():]

            # Handle remaining arrays (not in ^repetition format)
            final_components = temp_expanded.split("*")
            current_expanded_index = 0

            for component in final_components:
                component = component.strip()
                if component in arrays_dict:
                    array_def = arrays_dict[component]
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
                    # Direct material, not from array
                    if current_expanded_index not in array_usage_map:
                        array_usage_map[current_expanded_index] = {
                            'array_id': None,
                            'layer_position': None,
                            'material': component
                        }
                    current_expanded_index += 1

            # Now build the stack with correct thickness mapping
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
                            print(
                                f"  Found thickness mapping: Array {array_id}, Position {layer_pos} → {layer_thickness}nm")

                    print(f"  Layer {i + 1}: {layer_material} → {material_data} (thickness: {layer_thickness} nm)")

                    if isinstance(material_data, str) and material_data.startswith('{'):
                        print(f"  WARNING: {layer_material} still has JSON data, not variant!")
                        try:
                            import json
                            variants_data = json.loads(material_data)
                            variants = variants_data.get("variants", [])
                            if variants:
                                first_variant = variants[0][0]
                                print(f"  FALLBACK: Using first variant {first_variant}")
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
            print("Stack building complete!")
            print("=" * 50)

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


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = OpticalFilterApp()
    sys.exit(app.exec_())