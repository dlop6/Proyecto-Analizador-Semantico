"""
los ejemplos de objetos y de arreglos/try-catch de docs/INTERMEDIATE_CODE.md §13 salen,
caracter por caracter, del generador extendido real (no solo del builder armado a mano).
"""
from pathlib import Path

import pytest

from .conftest import tac_for

DOC = Path(__file__).resolve().parents[2] / "docs" / "INTERMEDIATE_CODE.md"

EXAMPLES = {
    "**Objetos, constructor y método.**": """
class Animal {
  let nombre: string;
  function constructor(n: string) { this.nombre = n; }
  function hablar(): string { return this.nombre; }
}
let a: Animal = new Animal("Rex");
print(a.hablar());
""",
    "**Arreglo y try/catch.**": """
let arr: integer[] = [1, 2];
try {
  print(arr[5]);
} catch (err) {
  print(err);
}
""",
}


def _doc_block(title: str) -> str:
    text = DOC.read_text(encoding="utf-8")
    start = text.index("```text", text.index(title)) + len("```text\n")
    return text[start:text.index("```", start)]


@pytest.mark.parametrize("title", EXAMPLES)
def test_ejemplo_del_documento_sale_del_generador_extendido(title):
    assert tac_for(EXAMPLES[title]).strip("\n") == _doc_block(title).strip("\n")
