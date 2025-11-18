# Optical Filter Designer - Refactored Version

Bu proje, optik filtre tasarımı için geliştirilmiş bir uygulamanın düzenlenmiş ve modüler hale getirilmiş versiyonudur.

## Yapılan Değişiklikler

### 🔧 Kod Organizasyonu
- **2500+ satırlık tek dosya** → **Modüler yapı**
- Tüm işlevsellik korundu, sadece organizasyon iyileştirildi
- GUI layout'a dokunulmadı

### 📁 Yeni Klasör Yapısı
```
src/
├── api/
│   └── material_api.py          # Material arama ve yönetimi
├── calculations/
│   ├── tmm_calculator.py        # TMM hesaplamaları
│   └── tmm_worker.py           # Background hesaplama
├── ui/
│   ├── dialogs.py              # Dialog pencereleri
│   └── tables.py               # Tablo bileşenleri
├── utils/
│   └── __init__.py
└── main.py                     # Ana uygulama
```

### ✅ Ayrılan Bileşenler
1. **MaterialSearchAPI** → `src/api/material_api.py`
2. **TMM Calculator** → `src/calculations/tmm_calculator.py`
3. **TMM Worker** → `src/calculations/tmm_worker.py`
4. **UI Dialogs** → `src/ui/dialogs.py`
5. **UI Tables** → `src/ui/tables.py`

## Çalıştırma

### Yöntem 1: Ana Script
```bash
python run_refactored.py
```

### Yöntem 2: Doğrudan
```bash
cd src
python main.py
```

### Virtual Environment ile
```bash
.venv/Scripts/python.exe run_refactored.py
```

## Özellikler

- ✅ Tüm orijinal işlevler korundu
- ✅ GUI aynı kaldı
- ✅ Materyal arama ve yönetimi
- ✅ TMM hesaplamaları
- ✅ Proje kaydetme/yükleme
- ✅ Sonuç dışa aktarma
- ✅ Array kalınlık düzenleme

## Avantajlar

1. **Daha iyi organizasyon** - Her bileşen kendi dosyasında
2. **Kolay bakım** - Kodun belirli bölümlerini bulmak kolay
3. **Modüler yapı** - Bileşenler bağımsız çalışabilir
4. **Temiz import'lar** - Gereksiz bağımlılıklar temizlendi
5. **Gelecek geliştirmeler** - Yeni özellik eklemek daha kolay

## Orijinal Dosya

Orijinal `optic_filter_design_v5.py` dosyası korundu. Yeni yapı tamamen ayrı çalışır.

## Gereksinimler

- Python 3.7+
- PyQt5
- NumPy
- Matplotlib
- PyYAML
- refractiveindex paketi

Herhangi bir sorun yaşarsanız orijinal dosyayı kullanmaya devam edebilirsiniz.