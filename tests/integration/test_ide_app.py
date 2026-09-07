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
