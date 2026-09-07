"""
tests de ide/app.py con el test client de flask: contrato http, no logica semantica
(esa la prueban compiler_service/extended_semantics/etc por su cuenta). confirma
tambien que el ide no reimplementa nada -- solo delega a compiler_service.compile_source.
"""
import pytest

from compiler.frontend import MAX_SOURCE_BYTES
from ide.app import app


@pytest.fixture
def client():
    app.config.update(TESTING=True)
    return app.test_client()


def test_index_sirve_la_pantalla_principal(client):
    response = client.get("/")
    assert response.status_code == 200
    assert b"Compiscript" in response.data


def test_index_ofrece_selector_de_archivos_cps(client):
    response = client.get("/")
    assert b'type="file"' in response.data
    assert b'accept=".cps"' in response.data


def test_index_comparte_el_limite_de_fuente_con_el_cliente(client):
    response = client.get("/")
    assert f'data-max-source-bytes="{MAX_SOURCE_BYTES}"'.encode() in response.data


def test_cliente_lee_archivos_con_filereader_y_maneja_error():
    source = (app.root_path + "/static/app.js")
    with open(source, encoding="utf-8") as javascript:
        contents = javascript.read()
    assert "new FileReader()" in contents
    assert "readAsText(file" in contents
    assert "reader.onerror" in contents


def test_cliente_valida_extension_y_tamano_antes_de_cargar_archivo():
    source = (app.root_path + "/static/app.js")
    with open(source, encoding="utf-8") as javascript:
        contents = javascript.read()
    assert 'endsWith(".cps")' in contents
    assert "file.size > maxSourceBytes" in contents


def test_index_ofrece_editor_resaltado_accesible_y_numeros_de_linea(client):
    response = client.get("/")
    assert b'id="editor-shell"' in response.data
    assert b'id="line-numbers"' in response.data
    assert b'id="highlight-layer"' in response.data
    assert b'aria-hidden="true"' in response.data
    assert b'<label for="source"' in response.data


def test_index_ofrece_acciones_de_diagnosticos_y_ast(client):
    response = client.get("/")
    for identifier in (
        b"diagnostic-filters",
        b"copy-diagnostics-btn",
        b"ast-zoom-in",
        b"ast-zoom-out",
        b"ast-reset",
        b"ast-fit",
        b"ast-download",
    ):
        assert identifier in response.data


def test_cliente_tiene_resaltado_seguro_y_navegacion_de_diagnosticos():
    source = (app.root_path + "/static/app.js")
    with open(source, encoding="utf-8") as javascript:
        contents = javascript.read()
    assert "requestAnimationFrame" in contents
    assert "highlightCodeEl.replaceChildren" in contents
    assert "token.textContent" in contents
    assert "setSelectionRange" in contents
    assert "diagnostic-jump" in contents


def test_cliente_ofrece_atajo_filtros_copia_y_controles_ast():
    source = (app.root_path + "/static/app.js")
    with open(source, encoding="utf-8") as javascript:
        contents = javascript.read()
    assert "event.ctrlKey || event.metaKey" in contents
    assert "navigator.clipboard.writeText" in contents
    assert "URL.createObjectURL" in contents
    assert "astScale" in contents
    assert "loadedSource" in contents


def test_compile_programa_valido_devuelve_success_true(client):
    response = client.post("/api/compile", json={"source": "let x: integer = 1;\nprint(x);"})
    assert response.status_code == 200
    body = response.get_json()
    assert body["success"] is True
    assert body["diagnostics"] == []


def test_compile_programa_con_errores_devuelve_diagnosticos(client):
    source = "class A {}\nlet a: A = new A();\nprint(a.inexistente);"
    response = client.post("/api/compile", json={"source": source})
    body = response.get_json()
    assert body["success"] is False
    codes = {d["code"] for d in body["diagnostics"]}
    assert "CPS-200" in codes
    for diag in body["diagnostics"]:
        assert set(diag) == {"code", "message", "line", "column", "severity"}


def test_compile_sin_source_no_revienta(client):
    response = client.post("/api/compile", json={})
    assert response.status_code == 200
    body = response.get_json()
    assert isinstance(body["diagnostics"], list)


def test_compile_con_source_no_string_da_400(client):
    response = client.post("/api/compile", json={"source": 123})
    assert response.status_code == 400
