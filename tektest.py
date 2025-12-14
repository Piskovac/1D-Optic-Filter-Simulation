import numpy
import matplotlib.pyplot as plt

from PyTMM.transferMatrix import *
from PyTMM.refractiveIndex import *
import os

# --- Configuration ---
# Use the refractiveindex.info database
database_path = "C:/Users/acer/Desktop/Bölüm Dersleri/Electro Optics/database"
catalog = RefractiveIndex(database_path, auto_download=False)

# Get the specified material
material_key = ('main', 'Ag', 'Ciesielski') # Using Ag from user's earlier test
material = catalog.getMaterial(*material_key)
material_name_for_log = material_key[1] # Use 'Ag' for filename

# Define calculation parameters
wavelengths_nm = numpy.linspace(400, 800, 401)  # 400 to 800 nm
layer_thickness_nm = 100  # A 100 nm thick layer

# Lists to store results from both methods
reflectance_layer_func_db = []
reflectance_manual_stack_db = []

# --- Debug Logging Setup ---
log_filename = f"tek_debug_{material_name_for_log}.txt"
if os.path.exists(log_filename):
    os.remove(log_filename)  # Clear old log file for a fresh run

# --- Calculation Loop ---
for wl_nm in wavelengths_nm:
    # Get n and k separately, as required by the PyTMM library
    n = material.getRefractiveIndex(wl_nm)
    try:
        k = material.getExtinctionCoefficient(wl_nm)
    except NoExtinctionCoefficient:
        k = 0.0  # Material is not absorbing at this wavelength
    
    # Combine into a complex refractive index
    n_current = complex(n, k) if k > 0 else n

    with open(log_filename, 'a') as f:
        f.write(f"Wavelength(nm): {wl_nm}\tn: {n_current.real}\tk: {n_current.imag}\n")
    # --- Bitis ---

    # Use the combined complex n for the rest of the calculations
    
    # Convert units to µm for matrix calculations, as required by PyTMM's transferMatrix module
    wl_um = wl_nm / 1000.0
    layer_thickness_um = layer_thickness_nm / 1000.0
    
    # --- Method 1: Using the convenience 'layer' function ---
    layer_matrix = TransferMatrix.layer(n_current, layer_thickness_um, wl_um)
    R_layer, _ = solvePropagation(layer_matrix)
    reflectance_layer_func_db.append(10 * numpy.log10(numpy.abs(R_layer)**2 + 1e-9))

    # --- Method 2: Manually building the same stack from fundamental components ---
    # This replicates what the 'layer' function does internally
    bottom_boundary = TransferMatrix.boundingLayer(1, n_current)  # Air to Layer
    propagation = TransferMatrix.propagationLayer(n_current, layer_thickness_um, wl_um) # Propagation through layer
    top_boundary = TransferMatrix.boundingLayer(n_current, 1)    # Layer to Air
    
    manual_matrix = TransferMatrix.structure(bottom_boundary, propagation, top_boundary)

    with open(log_filename, 'a') as f:
        f.write(f"  Matrix[0,0]: {manual_matrix.matrix[0,0]}\n")
        f.write(f"  Matrix[0,1]: {manual_matrix.matrix[0,1]}\n")
        f.write(f"  Matrix[1,0]: {manual_matrix.matrix[1,0]}\n")
        f.write(f"  Matrix[1,1]: {manual_matrix.matrix[1,1]}\n")
        f.write("-" * 20 + "\n") # Add a separator for the next wavelength
    # --- Bitis ---

    R_manual, _ = solvePropagation(manual_matrix)
    reflectance_manual_stack_db.append(10 * numpy.log10(numpy.abs(R_manual**2) + 1e-9))

# --- Plotting ---
plt.plot(wavelengths_nm, reflectance_layer_func_db, label="'layer' function (convenience)", linewidth=4, linestyle=':')
plt.plot(wavelengths_nm, reflectance_manual_stack_db, label="Manual Stack (fundamental)", linestyle='--')
plt.xlabel("Wavelength (nm)")
plt.ylabel("Reflectance (dB)")
plt.title(f"Verification: 'layer' function vs. Manual Stack for {material_name_for_log}")
plt.legend()
plt.grid(True)
plt.show(block=True)