import re
import subprocess
import sys

from importlib import import_module, invalidate_caches

from .paths import ADDON_PATH


def ensure_dependencies() -> None:
    requirements_path = str(ADDON_PATH / "requirements.txt")
    dependencies_path = ADDON_PATH / "dependencies"
    site_path = (
        dependencies_path
        / "lib"
        / "python{major}.{minor}".format(major=sys.version_info.major, minor=sys.version_info.minor)
        / "site-packages"
    )
    sys.path.insert(0, str(site_path))

    try:
        import_dependencies(requirements_path)
    except ModuleNotFoundError:
        exec = [sys.executable, "-m", "pip", "--no-input", "--disable-pip-version-check"]
        exec += ["install", "--prefix", str(dependencies_path), "--upgrade", "--requirement", requirements_path]
        out = [
            "",
            "{name}::ensure_dependencies()".format(name=ADDON_PATH.name),
            *subprocess.check_output(exec).decode("utf8").splitlines(),
            "",
        ]
        print("\n".join(out))
        invalidate_caches()


def import_dependencies(requirements_path: str) -> None:
    with open(requirements_path) as r:
        for line in r.readlines():
            if (m := re.match(r"^\w*", line)) is not None:
                import_module(m.group(0))
