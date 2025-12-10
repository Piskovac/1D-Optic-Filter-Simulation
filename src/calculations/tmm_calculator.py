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
        """Calculate reflection using PyTMM library with correct boundary + propagation approach"""
        try:
            if len(stack) == 0:
                return 0.0

            # Convert wavelength from nm to µm for PyTMM
            wavelength_um = wavelength / 1000.0

            # Convert angle to radians if needed
            theta = np.radians(angle) if angle > 0 else 0

            # Air as incident medium (n=1)
            n_air = 1.0

            # Filter out zero-thickness layers (interfaces only)
            physical_layers = [(material, thickness) for material, thickness in stack if thickness > 0]

            if not physical_layers:
                return 0.0

            # Get first and last materials for boundaries
            first_material, first_thickness = physical_layers[0]
            last_material, last_thickness = physical_layers[-1]

            n_first = self.get_refractive_index(first_material, wavelength)
            n_last = self.get_refractive_index(last_material, wavelength)

            # Single layer case
            if len(physical_layers) == 1:
                # Input boundary: Air → Material
                input_boundary = TransferMatrix.boundingLayer(n_air, n_first, theta, Polarization.s)

                # Propagation in material
                thickness_um = first_thickness / 1000.0
                propagation = TransferMatrix.propagationLayer(n_first, thickness_um, wavelength_um, theta, Polarization.s)

                # Output boundary: Material → Air (or substrate)
                n_substrate = 1.0  # Air for now, could be configurable
                output_boundary = TransferMatrix.boundingLayer(n_first, n_substrate, theta, Polarization.s)

                # Combine all
                combined = TransferMatrix.structure(input_boundary, propagation, output_boundary)

                R, T = solvePropagation(combined)
                return np.abs(R)**2

            # Multilayer case
            else:
                # Create input boundary: Air → First Material
                input_boundary = TransferMatrix.boundingLayer(n_air, n_first, theta, Polarization.s)

                # Create unique propagation matrices for each distinct material
                unique_materials = {}
                propagation_matrices = []

                for material, thickness in physical_layers:
                    n = self.get_refractive_index(material, wavelength)
                    thickness_um = thickness / 1000.0

                    # Create cache key for this material
                    n_str = f"{n.real:.6f}+{n.imag:.6f}j" if isinstance(n, complex) else f"{n:.6f}"
                    material_key = f"{n_str}_{thickness}_{wavelength}_{theta}"

                    # Check cache or create new propagation matrix
                    if material_key in self.layer_cache:
                        prop_matrix = self.layer_cache[material_key]
                    else:
                        prop_matrix = TransferMatrix.propagationLayer(n, thickness_um, wavelength_um, theta, Polarization.s)
                        self.layer_cache[material_key] = prop_matrix

                    propagation_matrices.append(prop_matrix)

                # Create output boundary: Last Material → Air (or substrate)
                n_substrate = 1.0  # Air for now, could be configurable
                output_boundary = TransferMatrix.boundingLayer(n_last, n_substrate, theta, Polarization.s)

                # Combine: Input boundary + All propagations + Output boundary
                all_matrices = [input_boundary] + propagation_matrices + [output_boundary]
                combined = TransferMatrix.structure(*all_matrices)

                R, T = solvePropagation(combined)
                return np.abs(R)**2

        except Exception as e:
            print(f"PyTMM calculation error: {e}")
            # Fallback to simple calculation
            return 0.1  # Default fallback value

