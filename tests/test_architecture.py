"""Guards the main design rule: the decision logic never touches hardware or the model.

config, signs, autopilot and driving decide what the car does. They must stay
plain Python, so they run (and are tested) on any computer, without a camera,
GPIO pins, a gamepad or the 2 GB of PyTorch. If this test fails, someone mixed
hardware code into the car's brain.
"""

import ast
from pathlib import Path

import pytest

PACKAGE_DIR = Path(__file__).parent.parent / "src" / "signcar"
PURE_MODULES = ["config", "signs", "autopilot", "driving"]

# Libraries that need hardware, a screen or the model, and the modules that wrap them.
FORBIDDEN_PREFIXES = (
    "cv2",
    "numpy",
    "torch",
    "ultralytics",
    "gpiozero",
    "lgpio",
    "picamera2",
    "pygame",
    "signcar.app",
    "signcar.camera",
    "signcar.detector",
    "signcar.gamepad",
    "signcar.hud",
    "signcar.motors",
)


def imported_modules(path: Path) -> set[str]:
    """Return the full name of every module imported by a Python file."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    modules = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules.add(node.module)
    return modules


@pytest.mark.parametrize("module", PURE_MODULES)
def test_decision_logic_stays_pure(module):
    path = PACKAGE_DIR / f"{module}.py"
    for imported in imported_modules(path):
        assert not imported.startswith(FORBIDDEN_PREFIXES), (
            f"{module}.py imports {imported}; the decision logic must stay plain Python"
        )


def test_config_imports_nothing_from_the_package():
    """config.py is the bottom layer: every module may import it, so it imports none."""
    for imported in imported_modules(PACKAGE_DIR / "config.py"):
        assert not imported.startswith("signcar"), f"config.py imports {imported}"
