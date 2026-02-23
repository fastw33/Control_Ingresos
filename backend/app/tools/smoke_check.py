# tools/smoke_check.py
import importlib, sys, traceback

OK = "✅"
ERR = "❌"

MODULES = [
    "app.core.db",
    "app.models",
    "app.core.logger",
    "app.core.errors",
    "app.security.cors",
    "app.security.security_headers",
    "app.security.rate_limit",
    "app.personal.controller",
    "app.vectores.controller",
    "app.marcacion.controller",
    "app.solicitud.controller",
    "app.main",  # debe poder importar la app
]

def try_import(name: str) -> bool:
    try:
        importlib.import_module(name)
        print(f"{OK} import {name}")
        return True
    except Exception:
        print(f"{ERR} import {name}")
        traceback.print_exc()
        return False

def main():
    print("=== Smoke check: imports ===")
    all_ok = True
    for m in MODULES:
        all_ok &= try_import(m)

    # Carga la instancia FastAPI para detectar errores de wiring
    if all_ok:
        try:
            mod = importlib.import_module("app.main")
            app = getattr(mod, "app", None)
            assert app is not None, "app.main no expone 'app'"
            print(f"{OK} FastAPI app encontrada en app.main:app")
        except Exception:
            print(f"{ERR} FastAPI app no se pudo construir")
            traceback.print_exc()
            all_ok = False

    print("\nResultado:", OK if all_ok else ERR)
    sys.exit(0 if all_ok else 1)

if __name__ == "__main__":
    main()
