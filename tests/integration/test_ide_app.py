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


def test_cliente_intercepta_tab_para_indentar_el_editor():
    source = (app.root_path + "/static/app.js")
    with open(source, encoding="utf-8") as javascript:
        contents = javascript.read()
    assert 'event.key === "Tab"' in contents
    assert 'sourceEl.setRangeText("    ", start, end, "end")' in contents


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


# ---------- codigo intermedio (tac) en la gui ----------

def _client_script() -> str:
    with open(app.root_path + "/static/app.js", encoding="utf-8") as javascript:
        return javascript.read()


def test_index_ofrece_la_pestana_y_el_panel_del_tac(client):
    html = client.get("/").data
    assert b'data-view="tac"' in html
    assert b'id="tac-container"' in html
    assert b'id="tac-code"' in html
    assert b'id="tac-copy"' in html


def test_compile_programa_valido_devuelve_el_tac_serializado(client):
    response = client.post("/api/compile", json={"source": "let x: integer = 1 + 2;\nprint(x);"})
    body = response.get_json()
    assert body["success"] is True
    assert body["tac_text"].splitlines() == ["  t0 = BIN +, 1, 2", "  MOV x@global[0], t0", "  PRINT x@global[0]"]


@pytest.mark.parametrize("source", [
    "@ let x: integer = 1;",                 # lexico
    "let x: integer = ;",                    # sintactico
    "let x: integer = \"texto\";",           # semantico
])
def test_compile_con_cualquier_error_no_devuelve_tac(client, source):
    body = client.post("/api/compile", json={"source": source}).get_json()
    assert body["success"] is False
    assert body["tac_text"] is None


def test_cliente_limpia_el_tac_y_muestra_estado_explicito_si_hay_errores():
    contents = _client_script()
    assert "No generado por errores" in contents
    assert "renderTac(data.success ? data.tac_text : null, TAC_NOT_GENERATED)" in contents
    assert "tacCodeEl.replaceChildren()" in contents


def test_cliente_pinta_el_tac_solo_con_textcontent():
    contents = _client_script()
    render = contents[contents.index("function renderTac"):contents.index("async function copyTac")]
    assert "innerHTML" not in render
    assert "createTextNode" in render


def test_la_tabla_de_simbolos_expone_la_informacion_de_runtime(client):
    source = "class A { let v: integer = 1; function m(): integer { return this.v; } }\nlet a: A = new A();"
    body = client.post("/api/compile", json={"source": source}).get_json()
    runtime = {s["name"]: s["runtime"] for s in body["symbols"]["symbols"]}
    assert runtime["a"] == "global[0]"
    assert runtime["A"] == "fields=1 metodos=1"
    method = body["symbols"]["symbols"][0]["methods"][0]
    assert method["runtime"] == "fn::A.m frame=1 slot=0"


def test_sin_ir_la_tabla_de_simbolos_no_inventa_informacion_de_runtime(client):
    body = client.post("/api/compile", json={"source": "let x: integer = \"a\";"}).get_json()
    assert all(s["runtime"] is None for s in body["symbols"]["symbols"])
