"""Regresiones de la correccion acotada del analizador semantico."""
from __future__ import annotations

from compiler.compiler_service import compile_source
from compiler.core_semantics import analyze as analyze_core
from compiler.extended_semantics import analyze as analyze_extended
from compiler.frontend import MAX_SOURCE_BYTES, analyze_source
from compiler.types import ArrayType, ClassType, INTEGER
from ide.app import JSON_ENVELOPE_BYTES, app


def analyze_full(source: str):
    return analyze_extended(analyze_core(analyze_source(source)))


def codes(source: str) -> set[str]:
    return {diag.code for diag in analyze_full(source).diagnostics}


def test_return_de_new_incompatible_no_se_acepta():
    assert "CPS-113" in codes("class A {} function f(): integer { return new A(); }")


def test_condicion_con_indice_no_booleano_no_se_acepta():
    assert "CPS-109" in codes("let a: integer[] = [1]; if (a[0]) { print(1); }")


def test_condicion_con_propiedad_no_booleana_no_se_acepta():
    source = "class A { let n: integer; } let a: A = new A(); if (a.n) { print(1); }"
    assert "CPS-109" in codes(source)


def test_argumento_new_incompatible_no_se_acepta():
    source = "class A {} function f(x: integer): integer { return x; } f(new A());"
    assert "CPS-112" in codes(source)


def test_funcion_no_se_puede_usar_como_valor_directo():
    source = "function f(): integer { return 1; } let x = f;"
    assert "CPS-119" in codes(source)


def test_funcion_no_se_puede_usar_en_operacion():
    source = "function f(): integer { return 1; } let x = f * 2;"
    result_codes = codes(source)
    assert "CPS-119" in result_codes
    assert "CPS-104" not in result_codes


def test_funcion_no_se_puede_usar_como_condicion():
    source = "function f(): integer { return 1; } if (f) { print(1); }"
    result_codes = codes(source)
    assert "CPS-119" in result_codes
    assert "CPS-109" not in result_codes


def test_funcion_no_se_puede_pasar_como_argumento():
    source = "function f(): integer { return 1; } function g(x: integer) {} g(f);"
    result_codes = codes(source)
    assert "CPS-119" in result_codes
    assert "CPS-112" not in result_codes


def test_clase_no_se_puede_usar_como_valor_sin_new():
    assert "CPS-119" in codes("class A {} let x = A;")


def test_metodo_no_se_puede_leer_sin_invocarlo():
    source = "class A { function m(): integer { return 1; } } let a: A = new A(); let x = a.m;"
    assert "CPS-215" in codes(source)


def test_llamadas_de_funcion_y_metodo_siguen_siendo_validas():
    source = """
    function f(): integer { return 1; }
    class A { function m(): integer { return f(); } }
    let a: A = new A();
    let x: integer = a.m();
    """
    assert analyze_full(source).ok


def test_foreach_requiere_arreglo_y_rechaza_integer():
    assert "CPS-120" in codes("foreach (x in 1) { print(x); }")


def test_foreach_requiere_arreglo_y_rechaza_otros_primitivos():
    source = 'foreach (x in true) { print(x); } foreach (y in "texto") { print(y); }'
    assert "CPS-120" in codes(source)


def test_foreach_rechaza_instancia_de_clase_despues_de_revalidar():
    source = "class A {} foreach (x in new A()) { print(x); }"
    assert "CPS-120" in codes(source)


def test_foreach_con_identificador_no_declarado_no_cascadea():
    result_codes = codes("foreach (x in desconocido) { print(x); }")
    assert result_codes == {"CPS-103"}


def test_foreach_con_arreglo_vacio_sin_elemento_inferible_es_error():
    assert "CPS-120" in codes("foreach (x in []) { print(x); }")


def test_foreach_con_arreglo_inferido_asigna_el_tipo_del_elemento():
    result = analyze_full("let numeros = [1, 2]; foreach (n in numeros) { print(n); }")
    iterator = next(
        symbol for scope in result.symbols.all_scopes() for symbol in scope.symbols.values()
        if getattr(symbol, "is_iteration_var", False)
    )
    assert result.ok
    assert iterator.type == INTEGER


def test_foreach_con_atributo_arreglo_asigna_el_tipo_del_elemento():
    source = "class A { let valores: integer[]; } let a: A = new A(); foreach (n in a.valores) { print(n); }"
    result = analyze_full(source)
    iterator = next(
        symbol for scope in result.symbols.all_scopes() for symbol in scope.symbols.values()
        if getattr(symbol, "is_iteration_var", False)
    )
    assert result.ok
    assert iterator.type == INTEGER


def test_operacion_con_indice_extendido_no_se_acepta():
    source = 'let a: integer[] = [1]; let x: string = a[0] + "y";'
    assert "CPS-104" in codes(source)


def test_inferencia_encadenada_de_arreglos_actualiza_simbolos():
    result = analyze_full("let xs = [1]; let y = xs[0];")
    assert result.ok
    assert result.symbols.global_scope.symbols["xs"].type == ArrayType(INTEGER)
    assert result.symbols.global_scope.symbols["y"].type == INTEGER


def test_funcion_anidada_se_puede_invocar():
    source = "function outer(): integer { function inner(): integer { return 1; } return inner(); }"
    assert "CPS-103" not in codes(source)


def test_closure_captura_variable_previa():
    source = "function outer(): integer { let x: integer = 1; function inner(): integer { return x; } return inner(); }"
    assert codes(source) == set()


def test_retorno_anidado_no_contamina_funcion_exterior():
    source = 'function outer() { function inner() { return "x"; } return 1; }'
    assert "CPS-114" not in codes(source)


def test_closure_no_captura_variable_posterior():
    source = "function outer(): integer { function inner(): integer { return x; } let x: integer = 1; return inner(); }"
    assert "CPS-103" in codes(source)


def test_for_solo_actualizacion_no_es_condicion():
    source = "let i: integer = 0; for (;; i = i + 1) { break; }"
    result = analyze_full(source)
    loop = result.ast.statements[1]
    assert loop.condition is None
    assert loop.update is not None
    assert "CPS-109" not in {diag.code for diag in result.diagnostics}


def test_atributo_const_no_se_puede_reasignar():
    source = "class A { const x: integer = 1; } let a: A = new A(); a.x = 2;"
    assert "CPS-102" in codes(source)


def test_campo_y_metodo_no_comparten_nombre():
    source = "class A { let x: integer; function x(): integer { return 1; } }"
    assert "CPS-021" in codes(source)


def test_metodo_y_campo_no_comparten_nombre():
    source = "class A { function x(): integer { return 1; } let x: integer; }"
    assert "CPS-021" in codes(source)


def test_return_vacio_y_con_valor_no_infieren_integer():
    source = "function f() { if (true) { return; } return 1; }"
    assert "CPS-114" in codes(source)


def test_hermanos_infiere_ancestro_comun_en_arreglo():
    source = "class Animal {} class Perro : Animal {} class Gato : Animal {} let a = [new Perro(), new Gato()];"
    result = analyze_full(source)
    assert result.ok
    assert result.ast.statements[-1].initializer.inferred_type == ArrayType(ClassType("Animal"))


def test_null_solo_es_asignable_a_referencias():
    valid = "class A {} let a: A = null; let xs: integer[] = null;"
    invalid = "let i: integer = null; let s: string = null; let b: boolean = null;"
    assert analyze_full(valid).ok
    assert "CPS-100" in codes(invalid)


def test_arreglo_vacio_sin_contexto_es_error():
    assert "CPS-214" in codes("let xs = [];" )


def test_arreglo_vacio_con_contexto_es_valido():
    assert analyze_full("let xs: integer[] = [];").ok


def test_subclase_sin_constructor_solo_acepta_cero_argumentos():
    source = "class A { function constructor(x: integer) {} } class B : A {} let b: B = new B(1);"
    assert "CPS-210" in codes(source)
    assert analyze_full("class A { function constructor(x: integer) {} } class B : A {} let b: B = new B();").ok


def test_svg_escape_texto_del_usuario():
    result = compile_source('let x: string = "<script>alert(1)</script>";')
    assert result.ast_svg is not None
    assert "<script>" not in result.ast_svg


def test_cliente_no_inserta_mensaje_de_diagnostico_con_innerhtml():
    javascript = (app.root_path + "/static/app.js")
    with open(javascript, encoding="utf-8") as source:
        contents = source.read()
    assert "${diag.message}" not in contents


def test_errores_http_tienen_esquema_uniforme():
    app.config.update(TESTING=True)
    client = app.test_client()
    response = client.post("/api/compile", json={"source": 123})
    assert response.status_code == 400
    assert set(response.get_json()) == {"success", "diagnostics", "ast_svg", "symbols", "error"}


def test_json_malformado_tiene_esquema_uniforme():
    app.config.update(TESTING=True)
    client = app.test_client()
    response = client.post("/api/compile", data="{", content_type="application/json")
    assert response.status_code == 400
    assert set(response.get_json()) == {"success", "diagnostics", "ast_svg", "symbols", "error"}


def test_request_demasiado_grande_se_rechaza_antes_de_compilar():
    app.config.update(TESTING=True)
    client = app.test_client()
    response = client.post(
        "/api/compile",
        json={"source": "x" * (MAX_SOURCE_BYTES + JSON_ENVELOPE_BYTES + 1)},
    )
    assert response.status_code == 413
    assert set(response.get_json()) == {"success", "diagnostics", "ast_svg", "symbols", "error"}


def test_architecture_documentada_y_referenciada():
    with open("ARCHITECTURE.md", encoding="utf-8") as document:
        assert "frontend" in document.read().lower()
