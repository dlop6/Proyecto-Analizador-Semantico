"""
lowering de clases y objetos a tac: declaracion de clase, new, this, lectura y escritura
de atributos y llamadas a metodo. las formas exactas estan en docs/INTERMEDIATE_CODE.md §9.

  class C {...}     no emite codigo propio: sus metodos y su constructor salen como
                    funciones fn::C.metodo con `this` en el slot 0 del frame
  new C(args)       t = NEW_OBJ C, fields=n ; SET_FIELD t, ... (inicializadores de
                    atributos, heredados primero) ; ARG t ; ARG args ; CALL fn::C.constructor
  obj.f             t = GET_FIELD obj, f@field[k]
  obj.f = v         SET_FIELD obj, f@field[k], v
  obj.m(args)       ARG args ; CALL_METHOD [t,] obj, m[slot], argc=n

herencia: todo sale del ClassLayout ya aplanado por runtime_layout (campos heredados
primero, override reutiliza el slot del padre). este modulo NO recorre la jerarquia de
clases: busca campos y metodos en el layout del tipo estatico del receptor.

mixin del generador extendido. usa de la clase concreta: builder, layout, enter(nodo),
visit, lower_value, release, new_temp_for, variable_ref, emit_arguments, _may_overwrite
y _snapshot.
"""
from __future__ import annotations

from compiler.ast_nodes import (
    Assignment, Call, ClassDecl, Expr, FunctionDecl, NewExpr, Program, PropertyAccess, ThisExpr, VarDecl,
)
from compiler.ir.builder import IRError
from compiler.ir.model import ClassRef, Const, Label, MethodRef, OperandValue, Temp
from compiler.ir.opcodes import Opcode
from compiler.runtime.activation_records import ClassLayout, FieldEntry
from compiler.runtime.storage import StorageKind, StorageRef
from compiler.symbols import THIS_NAME
from compiler.types import NULL, ClassType, VoidType


class ObjectLowering:

    def init_object_lowering(self, program: Program) -> None:
        """
        las clases solo pueden declararse en el nivel superior (CPS-024), asi que basta con
        indexar program.statements. se guarda el nodo de cada clase para poder abrir su
        scope al bajar los inicializadores de sus atributos.
        """
        self._class_decls: dict[str, ClassDecl] = {
            stmt.name: stmt for stmt in program.statements if isinstance(stmt, ClassDecl)
        }

    # ------------------------------------------------------------------
    # declaracion de clase
    # ------------------------------------------------------------------

    def visit_ClassDecl(self, node: ClassDecl) -> None:
        with self.enter(node):
            for member in node.members:
                if isinstance(member, FunctionDecl):
                    self.visit(member)  # metodo o constructor: una funcion mas, con this en el frame

    def visit_ThisExpr(self, node: ThisExpr) -> StorageRef:
        # this es un parametro implicito del frame del metodo; desde una funcion anidada en
        # el metodo ref_for ya devuelve el acceso nonlocal (this@frame^k[0])
        return self.variable_ref(THIS_NAME)

    # ------------------------------------------------------------------
    # instanciacion
    # ------------------------------------------------------------------

    def visit_NewExpr(self, node: NewExpr) -> Temp:
        layout = self._class_layout(node.class_name)
        obj = self.new_temp_for(node)
        self.builder.emit(Opcode.NEW_OBJ, obj, ClassRef(layout.class_name), fields=layout.size)
        for entry in layout.fields:
            self._lower_field_initializer(obj, entry)
        if layout.constructor_label is not None:
            self.builder.emit(Opcode.ARG, arg1=obj)  # el objeto nuevo pasa a ser `this`
            argc = self.emit_arguments(node.args)
            self.builder.emit(Opcode.CALL, None, Label(layout.constructor_label), argc=argc + 1)
        return obj

    def _lower_field_initializer(self, obj: Temp, entry: FieldEntry) -> None:
        """
        DECISION DE DISENO: el inicializador de un atributo se evalua en el sitio del `new`,
        antes del constructor, en el orden del layout (heredados primero). se baja dentro del
        scope de la clase que lo declara, asi sus nombres se resuelven igual que en la
        semantica (clase -> global) y no contra variables locales del sitio del `new`.
        """
        decl = self._class_decls[entry.owner_class]
        field = next(
            (m for m in decl.members if isinstance(m, VarDecl) and m.name == entry.name), None
        )
        if field is None or field.initializer is None:
            return
        with self.enter(decl):
            value = self.lower_value(field.initializer)
        self.builder.emit(Opcode.SET_FIELD, obj, self._field_ref(entry), value)
        self.release(value)

    # ------------------------------------------------------------------
    # atributos
    # ------------------------------------------------------------------

    def visit_PropertyAccess(self, node: PropertyAccess) -> Temp:
        obj = self.lower_value(node.obj)
        field = self._field_ref(self._field_entry(node.obj, node.name))
        result = self.new_temp_for(node)
        self.builder.emit(Opcode.GET_FIELD, result, obj, field)
        self.release(obj)
        return result

    def lower_property_assignment(self, node: Assignment, want_value: bool) -> OperandValue | None:
        """`obj.f = v`: se evaluan obj y v en ese orden y se emite SET_FIELD obj, f, v."""
        target: PropertyAccess = node.target
        obj = self._receiver(target.obj, [node.value])
        value = self.lower_value(node.value)
        self.builder.emit(Opcode.SET_FIELD, obj, self._field_ref(self._field_entry(target.obj, target.name)), value)
        self.release(obj)
        if want_value:
            return value
        self.release(value)
        return None

    # ------------------------------------------------------------------
    # metodos
    # ------------------------------------------------------------------

    def lower_method_call(self, node: Call, want_value: bool) -> OperandValue | None:
        """
        `obj.m(args)`: receptor, argumentos de izquierda a derecha y CALL_METHOD con el slot
        de despacho del tipo estatico del receptor. un override comparte ese slot (lo fijo el
        layout), asi que el backend futuro decide la implementacion por el objeto real.
        """
        callee: PropertyAccess = node.callee
        receiver = self._receiver(callee.obj, node.args)
        entry = self._class_layout(self._static_class(callee.obj)).method_named(callee.name)
        if entry is None:
            raise IRError(f"'{callee.name}' en {node.line}:{node.column} no es un metodo de la clase")
        argc = self.emit_arguments(node.args)
        returns_value = not isinstance(node.inferred_type, VoidType)
        result = self.new_temp_for(node) if want_value and returns_value else None
        self.builder.emit(Opcode.CALL_METHOD, result, receiver, MethodRef(entry.name, entry.slot), argc=argc)
        self.release(receiver)
        if want_value and not returns_value:
            return Const(None, NULL)  # mismo criterio que lower_call con funciones void
        return result

    # ------------------------------------------------------------------
    # helpers
    # ------------------------------------------------------------------

    def _receiver(self, expr: Expr, later: list[Expr]) -> OperandValue:
        """el objeto se evalua primero; si lo que viene despues puede reescribir esa variable, se copia."""
        obj = self.lower_value(expr)
        if isinstance(obj, StorageRef) and any(self._may_overwrite(obj, e) for e in later):
            return self._snapshot(obj, expr)
        return obj

    def _static_class(self, expr: Expr) -> str:
        if not isinstance(expr.inferred_type, ClassType):
            raise IRError(f"{type(expr).__name__} en {expr.line}:{expr.column} no tiene tipo de clase")
        return expr.inferred_type.name

    def _class_layout(self, class_name: str) -> ClassLayout:
        return self.layout.class_layouts[class_name]

    def _field_entry(self, obj: Expr, name: str) -> FieldEntry:
        entry = self._class_layout(self._static_class(obj)).field_named(name)
        if entry is None:
            raise IRError(f"'{name}' en {obj.line}:{obj.column} no es un atributo de la clase")
        return entry

    @staticmethod
    def _field_ref(entry: FieldEntry) -> StorageRef:
        return StorageRef(StorageKind.FIELD, entry.slot, name=entry.name)
