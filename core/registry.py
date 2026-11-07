import importlib
import sys
import os
import glob

def get_available_engines():
    """
    Dynamically loads all profile engine modules from the engines/ package.
    Adding a new engine is as simple as dropping a .py file into engines/!
    Registers modules in sys.modules so multiprocessing (pickle) can serialize them cleanly across all platforms.
    """
    current_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(current_dir)
    if project_root not in sys.path:
        sys.path.insert(0, project_root)

    engines_dir = os.path.join(project_root, "engines")
    engine_files = sorted(glob.glob(os.path.join(engines_dir, "*.py")))
    engines = {}

    for fpath in engine_files:
        fname = os.path.basename(fpath)
        if fname.startswith("__"):
            continue
        mod_name = fname[:-3]
        pkg_mod_name = f"engines.{mod_name}"

        try:
            mod = importlib.import_module(pkg_mod_name)
        except Exception:
            # Fallback if standard import fails
            import importlib.util
            spec = importlib.util.spec_from_file_location(pkg_mod_name, fpath)
            mod = importlib.util.module_from_spec(spec)
            sys.modules[pkg_mod_name] = mod
            sys.modules[mod_name] = mod
            spec.loader.exec_module(mod)

        engines[mod_name] = {
            "id": mod_name,
            "name": getattr(mod, "NAME", mod_name),
            "description": getattr(mod, "DESCRIPTION", ""),
            "module": mod
        }

    return engines
