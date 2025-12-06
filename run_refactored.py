"""
Run script for the refactored optical filter designer.
This script runs the application.
"""

import sys
import os

# Add the src directory to Python path
current_dir = os.path.dirname(os.path.abspath(__file__))
src_dir = os.path.join(current_dir, 'src')
if src_dir not in sys.path:
    sys.path.insert(0, src_dir)

from PyQt5.QtWidgets import QApplication
from main import OpticalFilterApp


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