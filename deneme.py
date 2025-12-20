import numpy as np

# yardımcı: fiziksel kz hesapı (branch düzeltme)
def compute_kz(n, k0, kx):
    kz = np.sqrt((k0*n)**2 - kx**2)
    if np.imag(kz) < 0:
        kz = -kz
    return kz

# örnek parametreler (kendi değerlerinle değiştir)
wavelength = 1.0
k0 = 2*np.pi / wavelength
theta0 = 0.3  # incident angle in radians
n1 = 1.0 + 0.0j
n2 = 2.0 + 0.1j

kx = k0 * n1 * np.sin(theta0)
kz1 = compute_kz(n1, k0, kx)
kz2 = compute_kz(n2, k0, kx)

# klasik Fresnel (kz-temelli)
r_te = (kz1 - kz2) / (kz1 + kz2)
t_te = 2*kz1 / (kz1 + kz2)

r_tm = (n2**2 * kz1 - n1**2 * kz2) / (n2**2 * kz1 + n1**2 * kz2)
t_tm = 2 * n1 * n2 * kz1 / (n2**2 * kz1 + n1**2 * kz2)

print("Fresnel TE r,t:", r_te, t_te)
print("Fresnel TM r,t:", r_tm, t_tm)

# şimdi senin boundingLayer matrisinden r,t çıkarma testini yap
# örnek: eğer boundary = 1/(2*a21*_n2) * [[_n1+_n2, _n2-_n1],[...]],
# ve senin konvansiyon [E_plus_left; E_minus_left] = boundary @ [E_plus_right; E_minus_right]
# ise r = boundary[1,0]/boundary[0,0]  ve  t = 1/boundary[0,0]   (konvansiyona bağlı)
# (test etmek için boundary matrisini oluşturup bu ifadeyle karşılaştır)

# --- build boundary according to your formula to compare ---
theta2 = np.arcsin((n1/n2)*np.sin(theta0))  # only for test; in practice use kz->cos
_n1_te = n1 * np.cos(theta0)
_n2_te = n2 * np.cos(theta2)
a21_te = 1.0

boundary_te = 1/(2*a21_te*_n2_te) * np.array([[_n1_te + _n2_te, _n2_te - _n1_te],
                                             [_n2_te - _n1_te, _n1_te + _n2_te]], dtype=complex)

r_from_boundary_te = boundary_te[1,0] / boundary_te[0,0]
t_from_boundary_te = 1.0 / boundary_te[0,0]

print("boundary TE r,t:", r_from_boundary_te, t_from_boundary_te)

# TM case using your code's formulæ
_n1_tm = n1 / np.cos(theta0)
_n2_tm = n2 / np.cos(theta2)
a21_tm = np.cos(theta2) / np.cos(theta0)

boundary_tm = 1/(2*a21_tm*_n2_tm) * np.array([[_n1_tm + _n2_tm, _n2_tm - _n1_tm],
                                             [_n2_tm - _n1_tm, _n1_tm + _n2_tm]], dtype=complex)

r_from_boundary_tm = boundary_tm[1,0] / boundary_tm[0,0]
t_from_boundary_tm = 1.0 / boundary_tm[0,0]

print("boundary TM r,t:", r_from_boundary_tm, t_from_boundary_tm)
