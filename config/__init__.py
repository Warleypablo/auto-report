"""
Expose the project settings as a local package and avoid pulling the external
`config` library that may be installed in the environment.

Carregamos settings.py do disco via importlib.util para garantir que mesmo
em ambientes onde outro pacote `config` foi instalado (ex: PyPI), o nosso
submódulo seja resolvido a partir deste diretório.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_SETTINGS_PATH = _HERE / "settings.py"

_spec = importlib.util.spec_from_file_location(
    __name__ + ".settings",
    str(_SETTINGS_PATH),
)
if _spec is None or _spec.loader is None:
    raise ImportError(f"Não foi possível localizar {_SETTINGS_PATH}")

settings = importlib.util.module_from_spec(_spec)
sys.modules[__name__ + ".settings"] = settings
_spec.loader.exec_module(settings)

__all__ = ["settings"]
