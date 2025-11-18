import numpy as np
import matplotlib.pyplot as plt

# --- Part 1: Create vector ---
N = 10**6
# np.random.rand(N, 1) MATLAB'daki rand(N, 1) ile aynı
vec = np.random.rand(N, 1)

# --- Part 2 & 3: Histogram, PDF (Aynı figürde) ---
# 2 satır, 1 sütunluk bir subplot figürü oluştur
fig1, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 10))

# --- Part 2: Histogram ---
# ax1, ilk subplot'tur
# Makul bir bölme (bin) sayısı belirleyelim, örn: 100
ax1.hist(vec, bins=100)
ax1.set_title(f'Part 2: Standard Histogram of rand({N}, 1)')
ax1.set_xlabel('Value')
ax1.set_ylabel('Frequency')
ax1.grid(True)

# --- Part 3: PDF ---
# ax2, ikinci subplot'tur
# 'density=True' histogramın alanını 1'e normalize eder (PDF)
ax2.hist(vec, bins=100, density=True, label='Empirical PDF')
ax2.set_title('Part 3: PDF from Histogram')
ax2.set_xlabel('Value')
ax2.set_ylabel('Density (f_X(x))')
ax2.set_ylim([0, 1.2])
ax2.grid(True)
# Plot theoretical pdf
ax2.plot([0, 1], [1, 1], 'r--', linewidth=2, label='Theoretical PDF (f(x)=1)')
ax2.legend()

# Subplot'ların üst üste binmesini engelle
fig1.tight_layout()

# --- Part 3: CDF (Ayrı bir figürde) ---
fig2, ax_cdf = plt.subplots(figsize=(10, 6))

# 'cumulative=True' kümülatif histogramı oluşturur
# 'density=True' y eksenini 1'e normalize eder
# 'histtype='step'' çizimi çizgi şeklinde yapar (daha net görünür)
ax_cdf.hist(vec, bins=1000, density=True, cumulative=True,
            histtype='step', linewidth=2, label='Empirical CDF')

ax_cdf.set_title('Part 3: CDF from Histogram')
ax_cdf.set_xlabel('Value')
ax_cdf.set_ylabel('Cumulative Probability (F_X(x))')
ax_cdf.grid(True)
# Plot theoretical cdf
ax_cdf.plot([0, 1], [0, 1], 'r--', linewidth=2, label='Theoretical CDF (F(x)=x)')
ax_cdf.legend(loc='lower right') # Legend için daha iyi bir yer

# --- Part 4: Mean and Variance ---
sample_mean = np.mean(vec)
# np.var varsayılan olarak N'e böler. ddof=1, MATLAB'daki gibi (N-1)'e böler.
sample_var = np.var(vec, ddof=1)

theoretical_mean = 0.5
theoretical_var = 1/12

# Display results (f-string kullanarak)
print('--- Part 4: Comparison ---')
print(f'Sample Mean:     {sample_mean:f}')
print(f'Theoretical Mean:     {theoretical_mean:f}')
print(f'Sample Variance: {sample_var:f}')
print(f'Theoretical Variance: {theoretical_var:f} (1/12)')

# Tüm figürleri göster
plt.show()