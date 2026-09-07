"""tests de compiler/function_rules.py: validacion de llamadas y de 'return'."""
from compiler.function_rules import ReturnTracker, check_call, check_return, finalize_return_type
from compiler.symbols import FunctionSymbol, VariableSymbol
from compiler.types import BOOLEAN, ERROR, INTEGER, STRING, VOID


def _function(name="f", params=None, return_type=None):
    return FunctionSymbol(name=name, line=1, column=1, params=params or [], return_type=return_type)


def _param(name, type_):
    return VariableSymbol(name=name, line=1, column=1, type=type_, is_param=True, initialized=True)


# ---------- check_call ----------

def test_llamada_con_aridad_correcta_y_tipos_compatibles():
    fn = _function(params=[_param("a", INTEGER)], return_type=INTEGER)
    result, code, detail = check_call("f", fn, [INTEGER])
    assert result == INTEGER
    assert code is None


def test_llamada_con_aridad_incorrecta_reporta_cps111():
    fn = _function(params=[_param("a", INTEGER)], return_type=INTEGER)
    result, code, detail = check_call("f", fn, [INTEGER, INTEGER])
    assert code == "CPS-111"
    assert result == ERROR


def test_llamada_con_tipo_de_argumento_incompatible_reporta_cps112():
    fn = _function(params=[_param("a", INTEGER)], return_type=INTEGER)
    result, code, detail = check_call("f", fn, [STRING])
    assert code == "CPS-112"


def test_llamada_con_argumento_error_no_cascadea():
    fn = _function(params=[_param("a", INTEGER)], return_type=INTEGER)
    result, code, detail = check_call("f", fn, [ERROR])
    assert code is None


def test_llamada_a_funcion_sin_tipo_de_retorno_inferido_da_error_sin_diagnostico():
    fn = _function(params=[], return_type=None)  # aun no se termino de inferir (recursion)
    result, code, detail = check_call("f", fn, [])
    assert result == ERROR
    assert code is None


def test_llamada_con_parametro_sin_anotacion_no_valida_su_tipo():
    fn = _function(params=[_param("a", None)], return_type=INTEGER)
    result, code, detail = check_call("f", fn, [STRING])
    assert code is None
    assert result == INTEGER


# ---------- check_return / finalize_return_type: funcion CON anotacion ----------

def test_return_compatible_con_tipo_declarado():
    fn = _function(return_type=INTEGER)
    tracker = ReturnTracker(function=fn, declared=INTEGER)
    assert check_return(tracker, INTEGER) is None


def test_return_incompatible_con_tipo_declarado_reporta_cps113():
    fn = _function(return_type=INTEGER)
    tracker = ReturnTracker(function=fn, declared=INTEGER)
    assert check_return(tracker, STRING) == "CPS-113"


def test_return_vacio_en_funcion_con_tipo_declarado_reporta_cps113():
    fn = _function(return_type=INTEGER)
    tracker = ReturnTracker(function=fn, declared=INTEGER)
    assert check_return(tracker, None) == "CPS-113"


def test_finalize_no_toca_una_funcion_con_anotacion():
    fn = _function(return_type=INTEGER)
    tracker = ReturnTracker(function=fn, declared=INTEGER)
    assert finalize_return_type(tracker) is None
    assert fn.return_type == INTEGER


# ---------- check_return / finalize_return_type: funcion SIN anotacion (se infiere) ----------

def test_sin_returns_infiere_void():
    fn = _function(return_type=None)
    tracker = ReturnTracker(function=fn, declared=None)
    assert finalize_return_type(tracker) is None
    assert fn.return_type == VOID


def test_returns_del_mismo_tipo_infiere_ese_tipo():
    fn = _function(return_type=None)
    tracker = ReturnTracker(function=fn, declared=None)
    check_return(tracker, INTEGER)
    check_return(tracker, INTEGER)
    assert finalize_return_type(tracker) is None
    assert fn.return_type == INTEGER


def test_returns_sin_tipo_comun_reporta_cps114():
    fn = _function(return_type=None)
    tracker = ReturnTracker(function=fn, declared=None)
    check_return(tracker, INTEGER)
    check_return(tracker, BOOLEAN)
    assert finalize_return_type(tracker) == "CPS-114"
    assert fn.return_type == ERROR
