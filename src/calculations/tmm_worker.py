"""TMM Worker Thread for background calculations"""

import traceback
from PyQt5.QtCore import QThread, pyqtSignal
from .tmm_calculator import TMM_Calculator


class TMM_Worker(QThread):
    """Worker thread for TMM calculations"""

    # Updated signal: (wavelengths, R, T, A, problematic)
    finished = pyqtSignal(object, object, object, object, object)
    error = pyqtSignal(str)
    progress = pyqtSignal(int)

    def __init__(self, stack, wavelengths, angle, parent=None):
        super().__init__(parent)
        self.stack = stack
        self.wavelengths = wavelengths
        self.angle = angle

    def run(self):
        try:
            calculator = TMM_Calculator()

            def update_progress(percent):
                self.progress.emit(percent)

            # calculator.calculate_reflection now returns ((R, T, A), problematic)
            (R, T, A), problematic = calculator.calculate_reflection(
                self.stack, self.wavelengths, self.angle, update_progress
            )

            self.finished.emit(self.wavelengths, R, T, A, problematic)

        except Exception as e:
            error_msg = f"Error: {str(e)}\n{traceback.format_exc()}"
            self.error.emit(error_msg)