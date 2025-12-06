import numpy
import matplotlib.pyplot as plt

from PyTMM.transferMatrix import *
from PyTMM.refractiveIndex import *
import os
# Database path - PyTMM will auto-download if not found
#database_path = os.path.join(os.path.expanduser("~"), "refractiveindex.info-database")
database_path = "C:/Users/acer/Desktop/Bölüm Dersleri/Electro Optics/database"
catalog = RefractiveIndex(database_path, auto_download=True)

sio2 = catalog.getMaterial('main', 'SrF2', 'Bosomworth-300K')

ran = range(400000, 800000, 1000)
reflectance = []

for i in ran:
    a = TransferMatrix.boundingLayer(1, sio2.getRefractiveIndex(i))
    R, T = solvePropagation(a)
    reflectance.append(numpy.abs(R**2))
    
plt.plot(ran, reflectance)
plt.xlabel("wavelength, nm")
plt.ylabel("reflectance")
plt.title("Reflectance of single SiO2 Boundary")
plt.show(block=True)