"""tests de compiler/ir/label_manager.py: etiquetas unicas, deterministas y validadas."""
import pytest

from compiler.ir.label_manager import LabelManager


def test_etiquetas_de_control_usan_un_contador_global():
    labels = LabelManager()
    assert labels.new_label("if_else") == "L_if_else_0"
    assert labels.new_label("if_end") == "L_if_end_1"
    assert labels.new_label("if_else") == "L_if_else_2"


def test_misma_secuencia_da_las_mismas_etiquetas():
    def run():
        labels = LabelManager()
        return [labels.new_label("while_cond"), labels.function_label("f"), labels.new_label("while_end")]
    assert run() == run()


def test_dos_compilaciones_no_comparten_contador():
    assert LabelManager().new_label("x") == LabelManager().new_label("x") == "L_x_0"


def test_etiqueta_de_funcion_y_choque_de_rutas():
    labels = LabelManager()
    assert labels.function_label("factorial") == "fn::factorial"
    assert labels.function_label("f.g") == "fn::f.g"
    assert labels.function_label("f.g") == "fn::f.g#2"
    assert labels.function_label("f.g") == "fn::f.g#3"


@pytest.mark.parametrize("prefix", ["", "If", "if-else", "x1", "a b"])
def test_prefijo_invalido_se_rechaza(prefix):
    with pytest.raises(ValueError):
        LabelManager().new_label(prefix)


@pytest.mark.parametrize("path", ["", "1f", "f..g", "f.", "a-b"])
def test_ruta_invalida_se_rechaza(path):
    with pytest.raises(ValueError):
        LabelManager().function_label(path)


def test_owns_solo_reconoce_etiquetas_propias():
    labels = LabelManager()
    mine = labels.new_label("if_end")
    assert labels.owns(mine)
    assert not labels.owns("L_if_end_99")
    assert not LabelManager().owns(mine)
