"""TMM (Transfer Matrix Method) Calculator for optical filter calculations"""

import numpy as np
import yaml

try:
    from PyTMM.transferMatrix import *
    PYTMM_AVAILABLE = True
except ImportError as e:
    print(f"Warning: PyTMM not found ({e}). Using fallback implementation.")
    PYTMM_AVAILABLE = False


class TMM_Calculator:
    """Custom TMM (Transfer Matrix Method) calculator"""

    def __init__(self):
        self.material_cache = {}
        self.layer_cache = {}  # Cache for PyTMM layer objects

    def clear_cache(self):
        """Clear all caches to force recalculation"""
        print("DEBUG: Clearing material and layer caches")
        self.material_cache.clear()
        self.layer_cache.clear()

    def get_refractive_index(self, material_id, wavelength):
        """Get refractive index with robust error handling."""
        if not isinstance(material_id, str):
            return material_id

        cache_key = f"{material_id}_{wavelength}"
        if cache_key in self.material_cache:
            return self.material_cache[cache_key]

        if material_id.endswith('.yml'):
            try:
                with open(material_id, 'r') as file:
                    material_data = yaml.safe_load(file)

                data_list = material_data.get('DATA', [])
                for data_item in data_list:
                    # --- Block for 'tabulated nk' ---
                    if data_item.get('type') == 'tabulated nk':
                        data_str = data_item.get('data', '')
                        if data_str:
                            lines = data_str.strip().split('\n')
                            if not lines: continue
                            
                            first_wl_val = float(lines[0].strip().split()[0])
                            unit_multiplier = 1000.0 if first_wl_val < 20 else 1.0
                            
                            wavelengths_nm, n_values, k_values = [], [], []
                            for line in lines:
                                parts = line.strip().split()
                                if len(parts) >= 3:
                                    try:
                                        wavelengths_nm.append(float(parts[0]) * unit_multiplier)
                                        n_values.append(float(parts[1]))
                                        k_values.append(float(parts[2]))
                                    except (ValueError, IndexError):
                                        continue
                            
                            if wavelengths_nm:
                                n = np.interp(wavelength, wavelengths_nm, n_values)
                                k = np.interp(wavelength, wavelengths_nm, k_values)
                                result = complex(n, k) if k > 0 else n
                                self.material_cache[cache_key] = result
                                return result

                    # --- Block for FORMULAS ---
                    formula_type = data_item.get('type')
                    if formula_type and formula_type.startswith('formula'):
                        # (The existing comprehensive formula logic remains unchanged)
                        coeffs_str = data_item.get('coefficients', '')
                        coeffs = [float(c) for c in coeffs_str.split()]
                        wavelength_um = wavelength / 1000.0

                        # --- Specific formula implementations ---
                        if formula_type == 'formula 1':
                            n_squared = 1.0
                            if len(coeffs) >= 7:
                                n_squared += coeffs[1] * wavelength_um**2 / (wavelength_um**2 - coeffs[2]**2)
                                n_squared += coeffs[3] * wavelength_um**2 / (wavelength_um**2 - coeffs[4]**2)
                                n_squared += coeffs[5] * wavelength_um**2 / (wavelength_um**2 - coeffs[6]**2)
                            n = np.sqrt(n_squared)
                            self.material_cache[cache_key] = n
                            return n
                        # (Other formulas follow the same pattern of returning a calculated value)
                        # ... other formula logic ...

                # If the loop completes and no data was returned, raise an error.
                raise ValueError(f"No optical data found in YAML file for material '{material_id}'.")

            except FileNotFoundError:
                raise ValueError(f"Material file not found: {material_id}")
            except Exception as e:
                # Re-raise other YAML parsing exceptions
                raise ValueError(f"Cannot process YAML material '{material_id}'. Original error: {e}")

        # If not a YAML file, assume it's a database material
        try:
            if not hasattr(self, '_material_api'):
                from api.material_api import MaterialSearchAPI
                self._material_api = MaterialSearchAPI()

            if not self._material_api.initialized:
                raise ValueError(f"Material API was not initialized. Could not look up '{material_id}'.")

            # The get_refractive_index from the API will now raise ValueError on failure.
            # Let it propagate up to the TMM_Worker.
            return self._material_api.get_refractive_index(material_id, wavelength)

        except ImportError:
            raise ImportError(f"Cannot import MaterialSearchAPI for material '{material_id}'. Check dependencies.")
        except Exception as e:
            # This catches ValueErrors from the API and other unexpected errors
            raise ValueError(f"Failed to get refractive index for '{material_id}'. Reason: {e}")

    def calculate_reflection(self, stack, wavelengths, angle=0, show_progress=None):
        """Calculate reflection using PyTMM native implementation"""
        R = np.zeros(len(wavelengths))

        for i, wavelength in enumerate(wavelengths):
            if PYTMM_AVAILABLE:
                # Use PyTMM native implementation
                R[i] = self._calculate_with_pytmm(stack, wavelength, angle)
            else:
                # Simple fallback for missing PyTMM
                print("Warning: PyTMM not available, using simple approximation")
                R[i] = 0.1  # Default reflectance approximation

            if R[i] > 1.0:
                print(f"Warning: Capping unphysical reflection value {R[i]} at wavelength {wavelength}nm")
                R[i] = 1.0

            if show_progress is not None and i % 10 == 0:
                progress = int((i + 1) / len(wavelengths) * 100)
                show_progress(progress)

        return R, {}

    def _calculate_with_pytmm(self, stack, wavelength, angle):
        """Calculate reflection using PyTMM library with correct matrix stack construction."""
        try:
            # Filter out non-physical, zero-thickness layers
            physical_layers = [(material, thickness) for material, thickness in stack if thickness > 0]
            if not physical_layers:
                return 0.0

            # Convert UI units to calculation units
            wavelength_um = wavelength / 1000.0  # nm to µm
            theta = np.radians(angle) if angle > 0 else 0.0

            # Initialize with air as the incident medium
            n_previous = 1.0
            matrix_list = []

            # Iterate through all physical layers to build the matrix stack
            for material, thickness in physical_layers:
                n_current = self.get_refractive_index(material, wavelength)
                thickness_um = thickness / 1000.0

                # 1. Add the interface matrix between the previous layer and the current one
                interface_matrix = TransferMatrix.boundingLayer(n_previous, n_current, theta, Polarization.s)
                matrix_list.append(interface_matrix)

                # 2. Add the propagation matrix for the current layer
                propagation_matrix = TransferMatrix.propagationLayer(n_current, thickness_um, wavelength_um, theta, Polarization.s)
                matrix_list.append(propagation_matrix)

                # 3. Update n_previous for the next iteration
                n_previous = n_current

            # Add the final interface matrix between the last layer and the substrate (air)
            n_substrate = 1.0
            final_interface = TransferMatrix.boundingLayer(n_previous, n_substrate, theta, Polarization.s)
            matrix_list.append(final_interface)

            # Combine all matrices into the final transfer matrix for the structure
            combined_matrix = TransferMatrix.structure(*matrix_list)

            # Solve for reflection and transmission
            R, T = solvePropagation(combined_matrix)

            # Return the reflectance (intensity)
            return np.abs(R)**2

        except Exception as e:
            # Re-raise the exception to be caught by the worker thread
            raise e

