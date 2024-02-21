import shutil
import subprocess
import sys
import venv

from importlib import invalidate_caches

from .paths import ADDON_PATH

REQUIREMENTS_PATH = ADDON_PATH / "requirements.txt"
DEPENDENCIES_PATH = ADDON_PATH / "dependencies"
LABEL = f"{ADDON_PATH.name}::ensure_dependencies()::{{}}"
PYTHON_VERSION = f"Python{sys.version_info.major}.{sys.version_info.minor}"


def ensure_dependencies() -> None:
    ensure_dependencies_venv_check()
    ensure_dependencies_venv_create()
    ensure_dependencies_pip_install()
    print()


def ensure_dependencies_venv_check() -> None:
    message = ["", LABEL.format("venv-check")]
    pyvenv_version = read_pyvenv_cfg_version()
    if sys.version_info[:2] != pyvenv_version:
        shutil.rmtree(DEPENDENCIES_PATH)
        message = [*message, f"REMOVE::Incompattible virtual environment for {PYTHON_VERSION}."]
    else:
        message = [*message, f"SKIP::Cmpatible virtual environment for {PYTHON_VERSION}. Nothing to do."]
    print("\n".join(message))


def ensure_dependencies_venv_create() -> None:
    message = ["", LABEL.format("venv-create")]
    if not DEPENDENCIES_PATH.exists():
        venv.create(env_dir=DEPENDENCIES_PATH, symlinks=True, with_pip=True)
        message.append(f"CREATE::Virtual environment in {DEPENDENCIES_PATH}.")
    else:
        message.append(f"SKIP::Virtual environment already exists in {DEPENDENCIES_PATH}. Nothing to do.")
    print("\n".join(message))


def ensure_dependencies_pip_install() -> None:
    message = ["", LABEL.format("pip")]
    exec = [
        DEPENDENCIES_PATH / "bin" / "pip",
        *["--no-input", "--disable-pip-version-check"],
        *["install", "--requirement", REQUIREMENTS_PATH],
    ]
    try:
        output = subprocess.check_output(exec).decode("utf8").splitlines()
        message = [*message, *output]
        invalidate_caches()

        site_path = DEPENDENCIES_PATH / "lib" / PYTHON_VERSION.lower() / "site-packages"
        sys.path.insert(0, str(site_path))
    except subprocess.CalledProcessError as error:
        error_message = f"ERROR({error.returncode})::Couldn't install Python packages!"
        error_output = error.output.decode("utf8").splitlines()
        message = [*message, error_message, *error_output]
    print("\n".join(message))


def read_pyvenv_cfg_version() -> tuple[int, int]:
    result = (0, 0)
    try:
        with open(DEPENDENCIES_PATH / "pyvenv.cfg") as pyenv_cfg:
            for line in (ln for ln in pyenv_cfg.readlines() if ln.startswith("version")):
                for version in line.split("=")[1:]:
                    result = tuple(int(v.strip()) for v in version.split(".")[:2])
    except FileNotFoundError:
        pass
    return result
