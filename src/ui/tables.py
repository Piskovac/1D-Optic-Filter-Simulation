"""Table widgets for materials and arrays management"""

import random
from PyQt5.QtWidgets import (
    QTableWidget, QTableWidgetItem, QPushButton, QHeaderView,
    QDialog, QMessageBox
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor
from .dialogs import ThicknessEditDialog


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
    """Enhanced table widget for displaying arrays with thickness editing"""

    def __init__(self, material_table, parent=None):
        super().__init__(parent)
        self.setColumnCount(5)
        self.setHorizontalHeaderLabels(["ID", "Definition", "Layers", "Edit", "Remove"])

        self.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeToContents)

        self.setSelectionBehavior(QTableWidget.SelectRows)
        self.material_table = material_table

        # Store thickness data for each array
        self.array_thicknesses = {}

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
                return False, f"Material '{part}' is marked as defect and cannot be used in arrays"

        return True, "Valid"

    def is_id_unique(self, array_id):
        """Check if an array ID is already used"""
        for row in range(self.rowCount()):
            if self.item(row, 0).text() == array_id:
                return False
        return True