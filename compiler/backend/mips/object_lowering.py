"""
lowering de NEW_OBJ, GET_FIELD, SET_FIELD y CALL_METHOD a mips (persona 3).

layout (abi.py): un objeto es un puntero al heap con [vtable][campo 0][campo 1]...; los
offsets salen del ClassLayout que ya armo runtime_layout (campos heredados primero), asi
que una subclase es compatible con su padre palabra por palabra y aca no se recalcula
ninguna jerarquia.

- vtables: una por clase instanciada, en .data: `vt_<Clase>: .word <metodo slot 0>, ...`
  en orden de method_slot (abi.vtable_entries). un override reusa el slot del padre y un
  metodo heredado apunta a la implementacion del ancestro; el constructor no esta en la
  tabla (se llama directo, el tac ya emite su CALL despues del NEW_OBJ).
- NEW_OBJ t, C: rt_alloc(4 + 4*campos) (memoria en cero) y la direccion de vt_C en la
  palabra 0. los inicializadores de campos y el constructor ya vienen como SET_FIELD y CALL.
- GET_FIELD / SET_FIELD: lw/sw en field_offset(slot) del objeto.
- CALL_METHOD: despacho dinamico. el emisor lee la vtable del receptor, toma la entrada del
  slot y hace jalr pasando el receptor como `this` (mismo abi que cualquier llamada).
- null: antes de leer o escribir un campo o de despachar se llama a rt_check_null, salvo que
  el objeto sea `this`, que nunca es null. el error va a error_target().

mixin del backend extendido. usa de la clase concreta: builder, allocator, emitter, layout,
assign, call_helper, error_target.
"""
from __future__ import annotations

from compiler.backend.mips.abi import OBJECT_VTABLE_OFFSET, object_size, vtable_entries
from compiler.backend.mips.operands import T, V0, LabelRef, Mem, vtable_label
from compiler.ir.model import Const, OperandValue, TACInstruction, Temp
from compiler.runtime.storage import StorageKind, StorageRef
from compiler.types import INTEGER

T8, T9 = T[8], T[9]
# `this` es palabra reservada: ningun StorageRef de usuario se llama asi. el propio llega
# como StorageKind.THIS y el de un metodo que encierra (funcion anidada) como NONLOCAL
_THIS = "this"


def new_object_problem(instr: TACInstruction, class_layouts) -> str | None:
    """por que un NEW_OBJ no se puede bajar, o None si se puede (lo usa validate())."""
    layout = class_layouts.get(instr.arg1.name)
    if layout is None:
        return f"NEW_OBJ de una clase sin layout: {instr.arg1.name}"
    if instr.meta("fields") != layout.size:
        return f"NEW_OBJ {instr.arg1.name} con fields={instr.meta('fields')} y el layout tiene {layout.size}"
    return None


class ObjectLowering:

    def emit_vtables(self, class_names) -> None:
        """una tabla de despacho por clase instanciada. una clase sin metodos lleva un 0 (.word no puede ir vacio)."""
        for name in sorted(class_names):
            entries = vtable_entries(self.layout.class_layouts[name])
            self.builder.add_data(vtable_label(name), "word", entries or (0,))

    def lower_new_obj(self, instr: TACInstruction) -> None:
        result = self._temp_result(instr, "un objeto nuevo")
        name = instr.arg1.name
        self.call_helper("rt_alloc", (Const(object_size(instr.meta("fields")), INTEGER),), result)
        obj = self.allocator.get_reg(result)
        self.builder.emit("la", T8, LabelRef(vtable_label(name)))
        self.builder.emit("sw", T8, Mem(OBJECT_VTABLE_OFFSET, obj), comment=f"vtable de {name}")

    def lower_get_field(self, instr: TACInstruction) -> None:
        obj, field = instr.arg1, instr.arg2
        self._check_not_null(obj)
        base = self.emitter.value_in_reg(obj, T8)
        self.assign(instr.result, lambda dest: self.emitter.load_field(dest, base, field.slot))

    def lower_set_field(self, instr: TACInstruction) -> None:
        obj, field, value = instr.result, instr.arg1, instr.arg2
        self._check_not_null(obj)
        base = self.emitter.value_in_reg(obj, T8)
        source = self.emitter.value_in_reg(value, T9)
        self.emitter.store_field(source, base, field.slot)

    def lower_call_method(self, instr: TACInstruction) -> None:
        receiver, method, result = instr.arg1, instr.arg2, instr.result
        self._check_not_null(receiver)
        self.emitter.emit_method_call(
            receiver, method.slot, instr.meta("argc"),
            result if isinstance(result, Temp) else None,
            on_error=self.error_target(),
        )
        if isinstance(result, StorageRef):
            # igual que CALL: el valor sigue en $v0 despues del chequeo de $v1
            self.emitter.store_storage(V0, result)

    def _check_not_null(self, obj: OperandValue) -> None:
        if isinstance(obj, StorageRef) and (obj.kind is StorageKind.THIS or obj.name == _THIS):
            return   # this (propio o de un frame que encierra) siempre apunta a un objeto
        self.call_helper("rt_check_null", (obj,), on_error=self.error_target())
