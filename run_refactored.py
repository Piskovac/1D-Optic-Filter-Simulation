"""
Run script for the refactored optical filter designer.
This script adds the src directory to the Python path and runs the application.
"""

import sys
import os

# Add the src directory to Python path
current_dir = os.path.dirname(os.path.abspath(__file__))
src_dir = os.path.join(current_dir, 'src')
sys.path.insert(0, src_dir)

# Run the application
if __name__ == "__main__":
    try:
        from main import OpticalFilterApp
        from PyQt5.QtWidgets import QApplication

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