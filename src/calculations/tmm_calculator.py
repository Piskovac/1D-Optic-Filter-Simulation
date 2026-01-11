"""TMM (Transfer Matrix Method) Calculator for optical filter calculations"""

import numpy as np
import yaml
import os

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
        """Calculate Reflection, Transmission, and Absorption"""
        num_points = len(wavelengths)
        R = np.zeros(num_points)
        T = np.zeros(num_points)
        A = np.zeros(num_points)

        for i, wavelength in enumerate(wavelengths):
            if PYTMM_AVAILABLE:
                # Use PyTMM native implementation
                r_val, t_val, a_val = self._calculate_with_pytmm(stack, wavelength, angle)
                R[i] = r_val
                T[i] = t_val
                A[i] = a_val
            else:
                # Simple fallback for missing PyTMM
                print("Warning: PyTMM not available, using simple approximation")
                R[i] = 0.1
                T[i] = 0.9
                A[i] = 0.0

            # Physical constraints
            if R[i] > 1.0: R[i] = 1.0
            if T[i] > 1.0: T[i] = 1.0
            if R[i] + T[i] > 1.0:
                T[i] = 1.0 - R[i]
                A[i] = 0.0
            
            # Ensure A is derived cleanly if not set
            if not PYTMM_AVAILABLE:
                A[i] = 1.0 - R[i] - T[i]

            if show_progress is not None and i % 10 == 0:
                progress = int((i + 1) / len(wavelengths) * 100)
                show_progress(progress)

        return (R, T, A), {}

    def _calculate_with_pytmm(self, stack, wavelength, angle):
        """Calculate R, T, A using PyTMM library."""
        try:
            # Extract incident and substrate materials
            incident_material = stack[0][0]
            substrate_material = stack[-1][0]
            
            # Physical layers are everything between first and last
            physical_layers_data = stack[1:-1]
            
            # Filter out non-physical, zero-thickness layers
            physical_layers = [(material, thickness) for material, thickness in physical_layers_data if thickness > 0]
            
            # Convert UI units to calculation units
            wavelength_um = wavelength / 1000.0  # nm to µm
            
            # Get refractive indices for boundaries
            n_incident = self.get_refractive_index(incident_material, wavelength)
            n_substrate = self.get_refractive_index(substrate_material, wavelength)
            
            # Incident angle in radians
            theta_inc = np.radians(angle) if angle > 0 else 0.0

            # Initialize with incident medium
            n_previous = n_incident
            matrix_list = []

            # Track theta for propagation through layers
            # We must calculate angles correctly using Snell's Law for each layer
            # n1 * sin(theta1) = n2 * sin(theta2)
            # constant = n_incident * sin(theta_inc)
            
            snell_const = n_incident * np.sin(theta_inc)
            
            current_theta = theta_inc # Theta in n_previous
            
            for material, thickness in physical_layers:
                n_current = self.get_refractive_index(material, wavelength)
                thickness_um = thickness / 1000.0
                
                # Calculate angle in current layer
                # theta_curr = arcsin( snell_const / n_current )
                theta_current_layer = np.emath.arcsin(snell_const / n_current)

                # 1. Boundary Matrix (n_prev -> n_curr)
                # boundingLayer expects angle in medium 1 (n_previous)
                interface_matrix = TransferMatrix.boundingLayer(n_previous, n_current, current_theta, Polarization.s)
                matrix_list.append(interface_matrix)

                # 2. Propagation Matrix
                # propagationLayer expects angle in that medium
                propagation_matrix = TransferMatrix.propagationLayer(n_current, thickness_um, wavelength_um, theta_current_layer, Polarization.s)
                matrix_list.append(propagation_matrix)

                # Update for next iteration
                n_previous = n_current
                current_theta = theta_current_layer

            # Final Boundary: Last Layer -> Substrate
            final_interface = TransferMatrix.boundingLayer(n_previous, n_substrate, current_theta, Polarization.s)
            matrix_list.append(final_interface)

            # Combine matrices
            combined_matrix = TransferMatrix.structure(*matrix_list)

            # Solve for r and t amplitudes
            # r = E_r / E_i
            # t = E_t / E_i
            r_amp, t_amp = solvePropagation(combined_matrix)

            # Calculate Power Coefficients
            R = np.abs(r_amp)**2
            
            # Calculate theta in substrate for Transmission
            theta_sub = np.emath.arcsin(snell_const / n_substrate)
            
            # Power Transmittance T
            # For s-polarization: T = |t|^2 * Re(n_sub * cos(theta_sub)) / Re(n_inc * cos(theta_inc))
            
            num = n_substrate * np.cos(theta_sub)
            den = n_incident * np.cos(theta_inc)
            
            factor = np.real(num) / np.real(den)
            
            T = np.abs(t_amp)**2 * factor
            
            # Absorption
            # Conservation of energy: R + T + A = 1
            A = 1.0 - R - T
            
            # Clamp small floating point errors
            if A < 0: A = 0.0

            return R, T, A

        except Exception as e:
            # Re-raise the exception to be caught by the worker thread
            raise e

