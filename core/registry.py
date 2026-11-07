import importlib.util
import os
import glob

def get_available_engines():
    """
    Dynamically loads all profile engine modules from the engines/ folder.
    Adding a new engine is as simple as dropping a .py file into engines/!
    """
    current_dir = os.path.dirname(os.path.abspath(__file__))
    engines_dir = os.path.join(os.path.dirname(current_dir), "engines")
    
    engine_files = sorted(glob.glob(os.path.join(engines_dir, "*.py")))
    engines = {}

    for fpath in engine_files:
        fname = os.path.basename(fpath)
        if fname.startswith("__"):
            continue
        mod_name = fname[:-3]
        
        spec = importlib.util.spec_from_file_location(mod_name, fpath)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        
        engines[mod_name] = {
            "id": mod_name,
            "name": getattr(mod, "NAME", mod_name),
            "description": getattr(mod, "DESCRIPTION", ""),
            "module": mod
        }

    return engines
