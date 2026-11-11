"""
api congelada de la base del backend: la consumen los lowerers. si alguien cambia un
nombre o una firma publica, este test se rompe antes que el codigo de los demas.
"""
import inspect

import pytest

from compiler.backend.mips import abi, activation, builder, frame_planner, operands, register_allocator
from compiler.backend.mips.activation import ActivationEmitter
from compiler.backend.mips.builder import MipsBuilder
from compiler.backend.mips.frame_planner import FramePlan, FramePlanner
from compiler.backend.mips.register_allocator import RegisterAllocator


def params(fn):
    return list(inspect.signature(fn).parameters)


@pytest.mark.parametrize("fn, expected", [
    (MipsBuilder.__init__, ["self", "entry_label"]),
    (MipsBuilder.emit, ["self", "opcode", "operands", "comment"]),
    (MipsBuilder.emit_branch, ["self", "opcode", "operands", "comment"]),
    (MipsBuilder.mark, ["self", "label"]),
    (MipsBuilder.add_data, ["self", "label", "directive", "value"]),
    (MipsBuilder.add_string, ["self", "text"]),
    (MipsBuilder.build, ["self"]),
    (MipsBuilder.render, ["self"]),
    (FramePlanner.plan, ["function", "layout"]),
    (FramePlanner.plan_entry, ["fragment", "label"]),
    (frame_planner.plan_program, ["program", "layout"]),
    (frame_planner.max_pending_args, ["instructions"]),
    (FramePlan.offset_of, ["self", "kind", "slot"]),
    (FramePlan.slot_offset, ["self", "slot"]),
    (FramePlan.temp_offset, ["self", "index"]),
    (RegisterAllocator.__init__, ["self", "builder", "plan"]),
    (RegisterAllocator.get_reg, ["self", "temp", "load"]),
    (RegisterAllocator.mark_dirty, ["self", "temp"]),
    (RegisterAllocator.release, ["self", "temp"]),
    (RegisterAllocator.flush_live, ["self"]),
    (RegisterAllocator.invalidate_caller_saved, ["self"]),
    (RegisterAllocator.reset, ["self", "plan"]),
    (RegisterAllocator.instruction, ["self"]),
    (ActivationEmitter.__init__, ["self", "builder", "allocator", "layout", "plans"]),
    (ActivationEmitter.begin_entry, ["self"]),
    (ActivationEmitter.end_entry, ["self"]),
    (ActivationEmitter.begin_function, ["self", "function"]),
    (ActivationEmitter.end_function, ["self"]),
    (ActivationEmitter.mark_label, ["self", "label"]),
    (ActivationEmitter.emit_branch, ["self", "opcode", "operands"]),
    (ActivationEmitter.error_target, ["self"]),
    (ActivationEmitter.emit_error_check, ["self", "target"]),
    (ActivationEmitter.value_in_reg, ["self", "operand", "scratch"]),
    (ActivationEmitter.load_value, ["self", "operand", "into"]),
    (ActivationEmitter.store_storage, ["self", "src", "ref", "via"]),
    (ActivationEmitter.load_field, ["self", "into", "obj", "slot"]),
    (ActivationEmitter.store_field, ["self", "src", "obj", "slot"]),
    (ActivationEmitter.emit_arg, ["self", "operand"]),
    (ActivationEmitter.emit_call, ["self", "callee_label", "argc", "link_hops", "result", "on_error"]),
    (ActivationEmitter.emit_method_call, ["self", "receiver", "slot", "argc", "result", "on_error"]),
    (ActivationEmitter.emit_helper_call, ["self", "name", "args", "result", "on_error"]),
    (ActivationEmitter.emit_return, ["self", "value"]),
    (operands.mangle_label, ["ir_label"]),
    (abi.vtable_entries, ["class_layout"]),
    (abi.field_offset, ["slot"]),
])
def test_firmas_publicas(fn, expected):
    assert params(fn) == expected


def test_campos_del_frame_plan():
    assert [f for f in FramePlan.__dataclass_fields__] == [
        "label", "size", "static_link", "receiver", "param_offsets", "local_offsets", "temp_offsets",
        "arg_stash", "incoming_bytes",
    ]


def test_modulos_exponen_sus_piezas():
    assert builder.MipsBuilder and register_allocator.RegisterAllocator and activation.ActivationEmitter
    assert operands.GLOBALS_LABEL == "__globals" and frame_planner.ENTRY_LABEL == "main"
