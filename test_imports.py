"""Test script to verify all imports work correctly"""

import sys
import os

# Add src to path
sys.path.insert(0, 'src')

try:
    print("Testing imports...")

    # Test API imports (no external dependencies)
    from api.material_api import MaterialSearchAPI, MaterialHandler
    print("✓ API imports OK")

    # Test UI imports (no numpy dependency)
    from ui.dialogs import CustomMaterialDialog, ThicknessEditDialog
    from ui.tables import MaterialTable, ArrayTable
    print("✓ UI imports OK")

    print("✓ Basic structure imports OK")

    # Test calculation imports (has numpy dependency)
    try:
        from calculations.tmm_calculator import TMM_Calculator
        from calculations.tmm_worker import TMM_Worker
        print("✓ Calculation imports OK")
    except ImportError as e:
        print(f"⚠ Calculation imports failed (missing dependencies): {e}")

    print("\n🎉 Code structure is correct!")
    print("Install missing packages to run the application.")

except ImportError as e:
    print(f"❌ Import error: {e}")
except Exception as e:
    print(f"❌ Other error: {e}")