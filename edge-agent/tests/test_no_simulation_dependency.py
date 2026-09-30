"""Production code must never depend on simulation code (simulation/ -> aivms_sim)."""

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _imports(path: Path) -> set[str]:
    names: set[str] = set()
    for node in ast.walk(ast.parse(path.read_text())):
        if isinstance(node, ast.Import):
            names.update(a.name for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module)
    return names


def test_production_packages_do_not_import_simulation():
    offenders = []
    for package in (ROOT / "edge-agent" / "agent", ROOT / "backend" / "app", ROOT / "shared" / "python"):
        for path in package.rglob("*.py"):
            if any(name == "aivms_sim" or name.startswith("aivms_sim.") for name in _imports(path)):
                offenders.append(str(path.relative_to(ROOT)))
    assert offenders == []


def test_production_images_do_not_install_simulation():
    for dockerfile in ("edge-agent/Dockerfile", "backend/Dockerfile", "frontend/Dockerfile"):
        assert "simulation" not in (ROOT / dockerfile).read_text(), dockerfile
