# tests/test_imports.py
import importlib
import pytest

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
]

@pytest.mark.parametrize("modname", MODULES)
def test_module_import(modname):
    importlib.import_module(modname)

def test_app_builds():
    mod = importlib.import_module("app.main")
    assert getattr(mod, "app", None) is not None
