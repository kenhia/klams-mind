"""Bootstrap smoke test — the package imports and versions itself."""

import klams_mind


def test_package_imports_and_has_version() -> None:
    assert klams_mind.__version__ == "0.1.0"
