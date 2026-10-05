"""
lowering de control de flujo core: if/else, while, do-while, for, switch, break y continue.
las formas exactas estan en docs/INTERMEDIATE_CODE.md §10.

break/continue usan dos pilas de destinos: cada bucle apila su salida y su punto de
continue; switch solo apila su salida (un continue adentro de un switch sigue yendo al
bucle que lo encierra). cada funcion arranca con pilas vacias.

el recorrido respeta los scopes que abrio symbol_collector (ver ScopedVisitor): la
condicion de while/do-while y el sujeto del switch van FUERA de su scope; la cabecera
del for va DENTRO.

mixin de CoreTacGenerator. usa de la clase concreta: builder, enter(nodo), visit,
lower_value, lower_effect y release.
"""
from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator

from compiler.ast_nodes import (
    BreakStatement, ContinueStatement, DoWhileStatement, Expr, ForStatement, IfStatement,
    SwitchStatement, WhileStatement,
)
from compiler.ir.model import Label, Temp
from compiler.ir.opcodes import Opcode
from compiler.types import BOOLEAN


class ControlFlowLowering:

    def init_jump_targets(self) -> None:
        self._break_targets: list[Label] = []
        self._continue_targets: list[Label] = []

    @contextmanager
    def jump_targets(self, break_to: Label, continue_to: Label | None = None) -> Iterator[None]:
        """destinos de break (y de continue, si es un bucle) mientras se baja un cuerpo."""
        self._break_targets.append(break_to)
        if continue_to is not None:
            self._continue_targets.append(continue_to)
        try:
            yield
        finally:
            self._break_targets.pop()
            if continue_to is not None:
                self._continue_targets.pop()

    @contextmanager
    def isolated_jump_targets(self) -> Iterator[None]:
        """el cuerpo de una funcion no puede saltar a un bucle de la funcion que la encierra."""
        saved = self._break_targets, self._continue_targets
        self.init_jump_targets()
        try:
            yield
        finally:
            self._break_targets, self._continue_targets = saved

    def _jump_if_false(self, condition: Expr, target: Label) -> None:
        value = self.lower_value(condition)
        self.builder.emit(Opcode.IF_FALSE, None, value, target)
        self.release(value)

    # ------------------------------------------------------------------
    # sentencias
    # ------------------------------------------------------------------

    def visit_IfStatement(self, node: IfStatement) -> None:
        else_label = self.builder.new_label("if_else") if node.else_block is not None else None
        end_label = self.builder.new_label("if_end")
        self._jump_if_false(node.condition, else_label or end_label)
        self.visit(node.then_block)
        if node.else_block is not None:
            self.builder.emit(Opcode.GOTO, arg1=end_label)
            self.builder.mark_label(else_label)
            self.visit(node.else_block)
        self.builder.mark_label(end_label)

    def visit_WhileStatement(self, node: WhileStatement) -> None:
        cond_label, end_label = self.builder.new_label("while_cond"), self.builder.new_label("while_end")
        self.builder.mark_label(cond_label)
        self._jump_if_false(node.condition, end_label)
        with self.enter(node), self.jump_targets(end_label, cond_label):
            self.visit(node.body)
        self.builder.emit(Opcode.GOTO, arg1=cond_label)
        self.builder.mark_label(end_label)

    def visit_DoWhileStatement(self, node: DoWhileStatement) -> None:
        body_label = self.builder.new_label("do_body")
        cond_label, end_label = self.builder.new_label("do_cond"), self.builder.new_label("do_end")
        self.builder.mark_label(body_label)
        with self.enter(node), self.jump_targets(end_label, cond_label):
            self.visit(node.body)
        self.builder.mark_label(cond_label)
        value = self.lower_value(node.condition)
        self.builder.emit(Opcode.IF_TRUE, None, value, body_label)
        self.release(value)
        self.builder.mark_label(end_label)

    def visit_ForStatement(self, node: ForStatement) -> None:
        cond_label = self.builder.new_label("for_cond")
        step_label, end_label = self.builder.new_label("for_step"), self.builder.new_label("for_end")
        with self.enter(node):
            if isinstance(node.init, Expr):
                self.lower_effect(node.init)
            elif node.init is not None:
                self.visit(node.init)
            self.builder.mark_label(cond_label)
            if node.condition is not None:
                self._jump_if_false(node.condition, end_label)
            with self.jump_targets(end_label, step_label):
                self.visit(node.body)
            self.builder.mark_label(step_label)
            if node.update is not None:
                self.lower_effect(node.update)
            self.builder.emit(Opcode.GOTO, arg1=cond_label)
            self.builder.mark_label(end_label)

    def visit_SwitchStatement(self, node: SwitchStatement) -> None:
        """
        sin fallthrough: el sujeto se evalua una vez en un temporal, se compara contra cada
        case en orden y se salta a la primera rama que coincide. cada rama termina en
        GOTO L_switch_end.
        """
        case_labels = [self.builder.new_label("switch_case") for _ in node.cases]
        has_default = node.default_statements is not None
        default_label = self.builder.new_label("switch_default") if has_default else None
        end_label = self.builder.new_label("switch_end")

        subject = self.lower_value(node.subject)
        if not isinstance(subject, Temp):
            value, subject = subject, self.new_temp_for(node.subject)
            self.builder.emit(Opcode.MOV, subject, value)
        with self.enter(node):
            for case, label in zip(node.cases, case_labels):
                value = self.lower_value(case.value)
                matches = self.builder.new_temp(BOOLEAN)
                self.builder.emit(Opcode.BIN, matches, subject, value, op="==")
                self.release(value)
                self.builder.emit(Opcode.IF_TRUE, None, matches, label)
                self.release(matches)
            self.release(subject)
            self.builder.emit(Opcode.GOTO, arg1=default_label or end_label)

            branches = list(zip(case_labels, (case.statements for case in node.cases)))
            if has_default:
                branches.append((default_label, node.default_statements))
            with self.jump_targets(end_label):
                for label, statements in branches:
                    self.builder.mark_label(label)
                    for statement in statements:
                        self.visit(statement)
                    self.builder.emit(Opcode.GOTO, arg1=end_label)
        self.builder.mark_label(end_label)

    def visit_BreakStatement(self, node: BreakStatement) -> None:
        self.builder.emit(Opcode.GOTO, arg1=self._break_targets[-1])

    def visit_ContinueStatement(self, node: ContinueStatement) -> None:
        self.builder.emit(Opcode.GOTO, arg1=self._continue_targets[-1])
