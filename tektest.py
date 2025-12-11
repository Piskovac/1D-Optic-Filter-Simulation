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
material = catalog.getMaterial('main', 'Ag', 'Ciesielski')

# Define calculation parameters
wavelengths_nm = numpy.linspace(400, 800, 401)  # 400 to 800 nm
layer_thickness_nm = 100  # A 100 nm thick layer

# Lists to store results from both methods
reflectance_layer_func_db = []
reflectance_manual_stack_db = []

# --- Calculation Loop ---
for wl_nm in wavelengths_nm:
    # Get refractive index at the given wavelength (PyTMM's n,k methods expect nm)
    n = material.getRefractiveIndex(wl_nm)
    
    # Convert units to µm for matrix calculations, as required by PyTMM's transferMatrix module
    wl_um = wl_nm / 1000.0
    layer_thickness_um = layer_thickness_nm / 1000.0
    
    # --- Method 1: Using the convenience 'layer' function ---
    layer_matrix = TransferMatrix.layer(n, layer_thickness_um, wl_um)
    R_layer, _ = solvePropagation(layer_matrix)
    reflectance_layer_func_db.append(10 * numpy.log10(numpy.abs(R_layer**2) + 1e-9))

    # --- Method 2: Manually building the same stack from fundamental components ---
    # This replicates what the 'layer' function does internally
    bottom_boundary = TransferMatrix.boundingLayer(1, n)  # Air to Layer
    propagation = TransferMatrix.propagationLayer(n, layer_thickness_um, wl_um) # Propagation through layer
    top_boundary = TransferMatrix.boundingLayer(n, 1)    # Layer to Air
    
    manual_matrix = TransferMatrix.structure(bottom_boundary, propagation, top_boundary)
    R_manual, _ = solvePropagation(manual_matrix)
    reflectance_manual_stack_db.append(10 * numpy.log10(numpy.abs(R_manual**2) + 1e-9))

# --- Plotting ---
plt.plot(wavelengths_nm, reflectance_layer_func_db, label="'layer' function (convenience)", linewidth=4, linestyle=':')
plt.plot(wavelengths_nm, reflectance_manual_stack_db, label="Manual Stack (fundamental)", linestyle='--')
plt.xlabel("Wavelength (nm)")
plt.ylabel("Reflectance (dB)")
plt.title("Verification: 'layer' function vs. Manual Stack")
plt.legend()
plt.grid(True)
plt.show(block=True)