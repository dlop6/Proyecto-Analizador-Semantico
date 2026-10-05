"""
tests de los campos de runtime agregados a compiler/symbols.py: arrancan en None, no
rompen la igualdad de los simbolos y no meten recursion en el repr.
"""
from compiler.runtime.activation_records import ActivationRecord, FrameSlot
from compiler.runtime.storage import StorageKind
from compiler.symbols import ClassSymbol, FunctionSymbol, VariableSymbol


def test_campos_de_runtime_arrancan_en_none():
    v = VariableSymbol(name="x", line=1, column=1)
    f = FunctionSymbol(name="f", line=1, column=1)
    c = ClassSymbol(name="C", line=1, column=1)
    assert (v.storage_kind, v.slot, v.owner) == (None, None, None)
    assert (f.label, f.method_slot, f.activation_record) == (None, None, None)
    assert c.layout is None


def test_campos_de_runtime_no_afectan_la_igualdad():
    a = VariableSymbol(name="x", line=1, column=1)
    b = VariableSymbol(name="x", line=1, column=1)
    b.storage_kind, b.slot, b.owner = StorageKind.GLOBAL, 0, None
    assert a == b


def test_repr_no_recursa_con_un_registro_de_activacion_cargado():
    param = VariableSymbol(name="n", line=1, column=1, is_param=True)
    fn = FunctionSymbol(name="f", line=1, column=1, params=[param])
    fn.activation_record = ActivationRecord(
        label="fn::f", lexical_depth=0, static_link=False, is_method=False, owner_class=None,
        slots=(FrameSlot(0, "n", StorageKind.PARAM),),
    )
    text = repr(fn)
    assert "activation_record" not in text
    assert "fn::f" not in text
