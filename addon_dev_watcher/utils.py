import sys

from types import ModuleType

from .paths import ADDON_PATH


def register(mods: list[ModuleType]) -> None:
    for mod in mods:
        mod.register()


def unregister(mods: list[ModuleType]) -> None:
    for mod in mods:
        mod.unregister()

    for mod in sorted(m for m in sys.modules if m.startswith(ADDON_PATH.name)):
        del sys.modules[mod]
