"""Dialog classes for the optical filter designer"""

from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QLineEdit, QDoubleSpinBox,
    QPushButton, QCheckBox, QLabel, QDialogButtonBox, QMessageBox, QSpinBox
)
from PyQt5.QtCore import Qt


class CustomMaterialDialog(QDialog):
    """Dialog for creating a custom material with refractive index values"""

    def __init__(self, parent=None, hide_id=False):
        super().__init__(parent)
        self.hide_id = hide_id
        self.setWindowTitle("Add Custom Material")
        self.setup_ui()

    def setup_ui(self):
        """Setup the dialog UI"""
        layout = QVBoxLayout(self)

        form = QFormLayout()

        self.name_edit = QLineEdit()
        form.addRow("Material Name:", self.name_edit)

        self.id_edit = QLineEdit()
        if not self.hide_id:
            form.addRow("Material ID:", self.id_edit)

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

        if not self.hide_id:
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

        if not self.hide_id:
            id_text = self.id_edit.text().strip()
            if not id_text:
                QMessageBox.warning(self, "Invalid Input", "Please enter a material ID.")
                return

            if not id_text.isalnum():
                QMessageBox.warning(self, "Invalid Input", "Material ID can only contain letters and numbers.")
                return

        self.accept()


class ThicknessEditDialog(QDialog):
    """Dialog for editing thickness values of array layers"""

    def __init__(self, array_definition, current_thicknesses, default_thickness, parent=None):
        super().__init__(parent)
        self.array_definition = array_definition
        self.current_thicknesses = current_thicknesses
        self.default_thickness = default_thickness
        self.thickness_spinboxes = {}

        self.setWindowTitle("Edit Layer Thicknesses")
        self.setup_ui()

    def setup_ui(self):
        """Setup the thickness editing UI"""
        layout = QVBoxLayout(self)

        info_label = QLabel(f"Array Definition: {self.array_definition}")
        info_label.setStyleSheet("font-weight: bold; margin-bottom: 10px;")
        layout.addWidget(info_label)

        form = QFormLayout()

        layers = self.array_definition.split("*")
        for i, layer in enumerate(layers):
            layer = layer.strip()
            layer_key = f"layer_{i}"

            current_value = self.current_thicknesses.get(layer_key, self.default_thickness)

            thickness_spin = QSpinBox()
            thickness_spin.setRange(1, 10000)
            thickness_spin.setValue(int(current_value))
            thickness_spin.setSuffix(" nm")

            self.thickness_spinboxes[layer_key] = thickness_spin
            form.addRow(f"Layer {i+1} ({layer}):", thickness_spin)

        layout.addLayout(form)

        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

        self.setMinimumWidth(350)

    def get_thicknesses(self):
        """Get the thickness values from the dialog"""
        thicknesses = {}
        for layer_key, spinbox in self.thickness_spinboxes.items():
            thicknesses[layer_key] = spinbox.value()
        return thicknesses


class DefectThicknessDialog(QDialog):
    """Dialog for editing the thickness of a defect layer"""

    def __init__(self, material_label, current_thickness, parent=None):
        super().__init__(parent)
        self.material_label = material_label
        self.current_thickness = current_thickness
        self.setWindowTitle(f"Edit Thickness: {material_label}")
        self.setup_ui()

    def setup_ui(self):
        """Setup the thickness editing UI"""
        layout = QVBoxLayout(self)

        info_label = QLabel(f"Set thickness for defect layer '{self.material_label}'")
        layout.addWidget(info_label)

        form = QFormLayout()

        self.thickness_spin = QDoubleSpinBox()
        self.thickness_spin.setRange(0.0, 100000.0)
        self.thickness_spin.setValue(float(self.current_thickness))
        self.thickness_spin.setSuffix(" nm")
        self.thickness_spin.setDecimals(2)
        
        form.addRow("Thickness:", self.thickness_spin)
        layout.addLayout(form)

        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

        self.setMinimumWidth(300)

    def get_thickness(self):
        """Get the thickness value"""
        return self.thickness_spin.value()

    