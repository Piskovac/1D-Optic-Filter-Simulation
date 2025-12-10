"""Material Search API for interacting with refractiveindex.info database"""

import os
import pickle
import sys
import numpy as np
import yaml

try:
    from PyTMM.refractiveIndex import *
    REFRACTIVE_INDEX_AVAILABLE = True
except ImportError as e:
    print(f"Warning: PyTMM refractiveIndex not found ({e}).")
    REFRACTIVE_INDEX_AVAILABLE = False


class MaterialSearchAPI:
    """Class to handle interaction with refractiveindex.info database"""

    def __init__(self):
        """Initialize the Material Search API with database caching"""
        self.initialized = False
        self.catalog = None
        self.ri_instance = None  # PyTMM RefractiveIndex instance
        self.material_cache = {}
        self.error_message = None

        try:
            from PyTMM.refractiveIndex import RefractiveIndex

            # Use %appdata% for Windows or proper cache dir for other OS
            if os.name == 'nt':  # Windows
                appdata = os.environ.get('APPDATA', os.path.expanduser("~"))
                self.cache_dir = os.path.join(appdata, "optical_filter_designer")
            else:
                self.cache_dir = os.path.join(os.path.expanduser("~"), ".optical_filter_designer")

            self.db_cache_path = os.path.join(self.cache_dir, "refractive_index_catalog.pickle")
            # Database should be in appdata, not cache subfolder
            self.database_path = self.cache_dir

            if not os.path.exists(self.cache_dir):
                os.makedirs(self.cache_dir)

            if os.path.exists(self.db_cache_path):
                try:
                    with open(self.db_cache_path, 'rb') as f:
                        self.ri_instance = pickle.load(f)
                        self.catalog = self.ri_instance.catalog
                    print("RefractiveIndex catalog loaded from cache!")
                except Exception as e:
                    print(f"Error loading cached catalog: {e}")
                    self._download_and_cache_catalog()
            else:
                self._download_and_cache_catalog()

            self.initialized = True

        except ImportError as e:
            self.error_message = "PyTMM package not found. Install with 'pip install PyTMM'"
            print(f"Warning: {self.error_message}")
        except Exception as e:
            self.error_message = f"Error initializing material catalog: {str(e)}"
            print(f"Warning: {self.error_message}")

    def _download_and_cache_catalog(self):
        """Download the catalog and save to cache"""
        try:
            from PyTMM.refractiveIndex import RefractiveIndex
            print("Downloading RefractiveIndex catalog...")

            # Use default path - PyTMM will auto-download to ~/refractiveindex.info-database
            # Let PyTMM handle the database location
            self.ri_instance = RefractiveIndex(auto_download=True)
            self.catalog = self.ri_instance.catalog

            try:
                with open(self.db_cache_path, 'wb') as f:
                    pickle.dump(self.ri_instance, f)
                print("RefractiveIndex catalog cached for future use!")
            except Exception as e:
                print(f"Warning: Could not cache catalog: {e}")
        except Exception as e:
            print(f"Error downloading catalog: {e}")
            self.ri_instance = None
            self.catalog = None

    def search_materials(self, query):
        """Search for materials matching the query in the catalog"""
        if not query or not self.initialized or not self.catalog:
            return []

        results = []
        try:
            for shelf in self.catalog:
                if 'DIVIDER' in shelf:
                    continue

                shelf_name = shelf.get('name', '')
                shelf_id = shelf.get('SHELF', '')

                for book in shelf.get('content', []):
                    if 'DIVIDER' in book:
                        continue

                    book_name = book.get('name', '')
                    book_id = book.get('BOOK', '')

                    if query.lower() in book_id.lower() or query.lower() in book_name.lower():
                        for page in book.get('content', []):
                            if 'DIVIDER' in page:
                                continue

                            page_name = page.get('name', '')
                            page_id = page.get('PAGE', '')

                            if not page_id:
                                continue

                            material_id = f"{shelf_id}|{book_id}|{page_id}"
                            material_name = f"{book_name} - {page_name}"
                            results.append((material_id, material_name))

                    else:
                        for page in book.get('content', []):
                            if 'DIVIDER' in page:
                                continue

                            page_name = page.get('name', '')
                            page_id = page.get('PAGE', '')

                            if not page_id:
                                continue

                            if query.lower() in page_id.lower() or query.lower() in page_name.lower():
                                material_id = f"{shelf_id}|{book_id}|{page_id}"
                                material_name = f"{book_name} - {page_name}"
                                results.append((material_id, material_name))

        except Exception as e:
            print(f"Error searching materials: {e}")
            return []

        return results

    def get_material_details(self, material_id):
        """Get shelf, book, page from material_id"""
        if not material_id or not self.initialized:
            return None, None, None

        parts = material_id.split('|')
        if len(parts) == 3:
            return parts[0], parts[1], parts[2]
        return None, None, None

    def get_wavelength_range(self, material_id):
        """Get the valid wavelength range for a material"""
        if not material_id or not self.initialized or not self.catalog:
            return (0, 0)

        try:
            shelf, book, page = self.get_material_details(material_id)
            print(f"DEBUG: material_id={material_id}, shelf={shelf}, book={book}, page={page}")

            if shelf and book and page and self.ri_instance:
                # Debug catalog structure
                print(f"DEBUG: catalog first item keys: {list(self.catalog[0].keys()) if self.catalog else 'None'}")

                material = self.ri_instance.getMaterial(shelf, book, page)

                if hasattr(material, 'refractiveIndex') and material.refractiveIndex:
                    db_range_min_um = material.refractiveIndex.rangeMin
                    db_range_max_um = material.refractiveIndex.rangeMax

                    if db_range_min_um > 1: # Heuristic: if stored µm value is large, treat it as nm
                        range_min_nm = db_range_min_um
                        range_max_nm = db_range_max_um
                    else: # Else, it's a true µm value, convert to nm
                        range_min_nm = db_range_min_um * 1000
                        range_max_nm = db_range_max_um * 1000
                    return (range_min_nm, range_max_nm)

            return (0, 0)

        except Exception as e:
            print(f"Error getting wavelength range for {material_id}: {e}")
            return (0, 0)


    def get_refractive_index(self, material_id, wavelength):
        """Get refractive index using proper catalog API"""
        if not isinstance(material_id, str):
            return material_id

        cache_key = f"{material_id}_{wavelength}"
        if cache_key in self.material_cache:
            return self.material_cache[cache_key]

        if '|' not in material_id:
            print(f"Warning: Invalid material_id format: '{material_id}'")
            return 1.5

        if not self.ri_instance:
            print(f"Warning: RefractiveIndex instance not available for {material_id}")
            return 1.5

        try:
            shelf, book, page = material_id.split('|')
            material = self.ri_instance.getMaterial(shelf, book, page)

            range_min = None
            range_max = None   

            try:
                if material.refractiveIndex.rangeMin > 10: 
                    range_min = material.refractiveIndex.rangeMin  # nm
                    range_max = material.refractiveIndex.rangeMax
                    wavelength *= 1000 # nm
                else: 
                   range_min = material.refractiveIndex.rangeMin * 1000  # µm to nm
                   range_max = material.refractiveIndex.rangeMax * 1000  # µm to nm
            except AttributeError:
                n = material.getRefractiveIndex(wavelength)
                self.material_cache[cache_key] = n
                return n
            
            if wavelength < range_min:
                wavelength = range_min
            elif wavelength > range_max:
                wavelength = range_max

            n = material.getRefractiveIndex(wavelength)

            try:
                k = material.getExtinctionCoefficient(wavelength)
                if k > 0:
                    n = complex(n, k)
            except:
                pass

            self.material_cache[cache_key] = n
            return n

        except Exception as e:
            
            print(f"Warning: MaterialSearchAPI cannot process {material_id}: {e}")
            return 1.5

class MaterialHandler:
    """Helper class to handle materials including selected database variants"""

    @staticmethod
    def serialize_material(material, selected_variant=None):
        """Convert material data to a serializable format for saving"""
        name, material_id, is_defect = material

        if isinstance(material_id, complex):
            return {
                "name": name,
                "type": "custom_complex",
                "n": float(material_id.real),
                "k": float(material_id.imag),
                "is_defect": is_defect
            }
        elif isinstance(material_id, (int, float)):
            return {
                "name": name,
                "type": "custom_real",
                "n": float(material_id),
                "is_defect": is_defect
            }
        elif isinstance(material_id, str) and material_id.endswith('.yml'):
            return {
                "name": name,
                "type": "browsed",
                "file_path": material_id,
                "is_defect": is_defect
            }
        elif isinstance(material_id, str) and '{' in material_id:
            return {
                "name": name,
                "type": "database_variants",
                "variants_json": material_id,
                "selected_variant": selected_variant,
                "is_defect": is_defect
            }
        elif isinstance(material_id, str) and '|' in material_id:
            return {
                "name": name,
                "type": "database_selected",
                "variant_id": material_id,
                "is_defect": is_defect
            }
        else:
            return {
                "name": name,
                "type": "unknown",
                "data": str(material_id),
                "is_defect": is_defect
            }

    @staticmethod
    def deserialize_material(data):
        """Convert serialized data back to material format"""
        name = data["name"]
        is_defect = data.get("is_defect", False)
        material_type = data["type"]

        if material_type == "custom_complex":
            material_id = complex(data["n"], data["k"])
        elif material_type == "custom_real":
            material_id = data["n"]
        elif material_type == "browsed":
            material_id = data["file_path"]
        elif material_type == "database_variants":
            material_id = data["variants_json"]
        elif material_type == "database_selected":
            material_id = data["variant_id"]
        else:
            material_id = data["data"]

        return (name, material_id, is_defect)