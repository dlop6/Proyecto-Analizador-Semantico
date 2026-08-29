"""fixtures y helpers compartidos para los tests del frontend."""
from pathlib import Path

import pytest

FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def cps_fixture():
    """lee un .cps de fixtures/valid o fixtures/invalid por nombre relativo, ej 'valid/minimal.cps'."""
    def _read(relative_path: str) -> str:
        path = FIXTURES_DIR / relative_path
        return path.read_text(encoding="utf-8")
    return _read


def assert_codes(diagnostics, expected_codes: list[str]) -> None:
    """compara el conjunto de codigos de una lista de diagnosticos contra lo esperado."""
    actual = {d.code for d in diagnostics}
    assert actual == set(expected_codes), f"esperaba {set(expected_codes)}, obtuvo {actual}"
