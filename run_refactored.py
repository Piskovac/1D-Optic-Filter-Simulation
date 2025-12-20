"""
Run script for the refactored optical filter designer.
This script runs the application.
pyinstaller command to create executable:
python -m PyInstaller --noconfirm --onefile --windowed --icon "logo.png" --name "OpticalFilterDesigner" --paths "src" --add-data "src;src" --add-data "PyTMM;PyTMM" --add-data "refractive_index_db.pickle;." --hidden-import "numpy" --hidden-import "matplotlib" --hidden-import "PyQt5" --hidden-import "PyQt5.QtCore" --hidden-import "PyQt5.QtWidgets" --hidden-import "PyQt5.QtGui" --hidden-import "yaml" --hidden-import "src.main" run_refactored.py
"""

import sys
import os

# Add the src directory to Python path
current_dir = os.path.dirname(os.path.abspath(__file__))
src_dir = os.path.join(current_dir, 'src')
if src_dir not in sys.path:
    sys.path.insert(0, src_dir)

# Import using importlib for better compatibility
import importlib.util
from PyQt5.QtWidgets import QApplication

# Load main module directly
main_path = os.path.join(src_dir, 'main.py')
spec = importlib.util.spec_from_file_location("main", main_path)
main_module = importlib.util.module_from_spec(spec)
sys.modules["main"] = main_module
spec.loader.exec_module(main_module)

# Get the class
OpticalFilterApp = main_module.OpticalFilterApp


# Run the application
if __name__ == "__main__":
    try:
        app = QApplication(sys.argv)
        window = OpticalFilterApp()
        window.show()
        sys.exit(app.exec_())
    except ImportError as e:
        print(f"Import error: {e}")
        print("Make sure all required packages are installed:")
        print("- PyQt5")
        print("- numpy")
        print("- matplotlib")
        print("- pyyaml")
        print("- refractiveindex")
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()