"""
visitor que recorre el ast propio y completa la semantica extendida: clases (herencia,
'this', 'new', acceso a miembros, llamadas a metodos, override) y arreglos (literales,
acceso por indice). corre DESPUES de CoreSemanticVisitor (frontend -> core -> extended,
ver compiler_service.py) y delega en class_rules.py / array_rules.py (srp) -- no duplica
type checking (types.py), lookup de miembros (symbols.ClassSymbol.lookup_member) ni el
mecanismo de diagnosticos (diagnostics.py).

que nodos completa esta etapa (quedaban en inferred_type = None despues de la core, ver
el README seccion "Semantica core > Division con la semantica extendida"):
PropertyAccess, IndexAccess, NewExpr, ThisExpr, ArrayLiteral, y el Assignment/Call cuyo
target/callee es uno de esos nodos. todo lo demas (BinaryOp, if/while/for, literales,
identificadores...) ya quedo resuelto por CoreSemanticVisitor y no se vuelve a tocar: se
deja que AstVisitor.generic_visit baje solo por esos nodos. VarDecl SI tiene una entrada
propia, pero solo para reportar un [] sin tipo de contexto (CPS-214).

diferencia deliberada con CoreSemanticVisitor: este visitor NO arma un cursor de scopes
por posicion (`_scope_by_pos`). ese mecanismo existe en la core para resolver
identificadores por cadena de scopes (`Scope.lookup`), y este visitor casi nunca hace
lookup de identificadores -- toda la informacion que necesita sale de leer
`inferred_type` de los hijos (ya resuelto por la core o por si mismo, recorriendo
primero) y de consultar `ClassSymbol.lookup_member`/el diccionario de clases. lo unico
que hay que trackear es "en que clase estoy" mientras se visitan los metodos de un
ClassDecl, y para eso alcanza con guardar/restaurar un atributo simple
(`self._current_class`), igual que hace CoreSemanticVisitor con el suyo. construir el
cursor de scopes completo solo para no usarlo violaria yagni.

nota sobre `let x: T = expr;` y `x = expr;` cuando `expr` es un NewExpr/ArrayLiteral/
PropertyAccess/IndexAccess/llamada a metodo: en la primera pasada la core ve ese tipo en
None y se salta la comparacion. extended_semantics.analyze despues alterna core y
extendida hasta un punto fijo, asi que la core vuelve a pasar con el tipo ya puesto por
esta etapa y reporta CPS-100. por eso aca no se valida esa compatibilidad: hacerlo era
reportar la misma causa dos veces (antes salia CPS-209 junto a CPS-100).

catalogo de mensajes: CPS-2xx esta reservado a esta etapa (frontend usa CPS-0xx, la
semantica core CPS-1xx). mismo criterio que core_semantic_visitor.py: catalogo propio
local (_MESSAGES), reutilizando de diagnostics.py solo el mecanismo compartido
(Diagnostic, DiagnosticBag, Severity).
"""
from __future__ import annotations

from compiler.array_rules import check_array_literal, check_index_access, is_valid_index_type
from compiler.ast_nodes import (
    ArrayLiteral, Assignment, AstVisitor, Call, ClassDecl, Expr, FunctionDecl,
    IndexAccess, NewExpr, Program, PropertyAccess, ThisExpr, VarDecl,
)
from compiler.class_rules import check_method_call, check_new_call, check_override, check_property_access
from compiler.diagnostics import Diagnostic, DiagnosticBag, Severity
from compiler.scopes import SymbolTable
from compiler.symbols import ClassSymbol, FunctionSymbol, VariableSymbol
from compiler.types import (
    ClassHierarchy, ClassType, ERROR, EmptyArrayType, ErrorType, Type, is_assignable,
)

# catalogo unico de mensajes de la semantica extendida. CPS-2xx no vive en
# diagnostics.py ni en core_semantic_visitor.py (ver docstring del modulo).
_MESSAGES: dict[str, str] = {
    "CPS-200": "'{detail}' no es un miembro de la clase",
    "CPS-201": "'{detail}' no es un metodo invocable",
    "CPS-202": "el metodo '{detail}' no respeta la firma heredada",
    "CPS-203": "tipo incompatible en la asignacion del atributo '{detail}'",
    "CPS-204": "tipo incompatible en la asignacion de un elemento del arreglo",
    "CPS-205": "el indice de un arreglo debe ser 'integer'",
    "CPS-206": "no se puede indexar un valor que no es un arreglo",
    "CPS-207": "los elementos del arreglo no tienen un tipo comun",
    "CPS-208": "no se puede acceder a '{detail}' sobre un valor que no es un objeto",
    "CPS-210": "numero de argumentos incorrecto en 'new {detail}(...)'",
    "CPS-211": "el argumento {detail} es incompatible con el parametro del constructor",
    "CPS-212": "numero de argumentos incorrecto en la llamada al metodo '{detail}'",
    "CPS-213": "el argumento {detail} es incompatible con el parametro del metodo",
    "CPS-214": "el literal de arreglo vacio requiere un tipo de contexto",
    "CPS-215": "el metodo '{detail}' debe invocarse para producir un valor",
}

# ninguno de estos codigos es advertencia: todos impiden result.ok, a diferencia de
# CPS-117/118 en la core.
_WARNING_CODES: set[str] = set()


class _ClassHierarchyView:
    """
    protocolo minimo de types.py (ClassHierarchy) sobre las clases ya resueltas por el
    frontend. duplicado deliberado de la misma clase en symbol_collector.py y
    core_semantic_visitor.py (ninguno de los dos expone la suya como utilidad
    compartida): es informacion derivada de un puntero que ya existe
    (ClassSymbol.parent), no logica nueva -- mismo criterio documentado en el handoff.
    """

    def __init__(self, classes: dict[str, ClassSymbol]) -> None:
        self._classes = classes

    def is_subclass(self, sub_name: str, super_name: str) -> bool:
        if sub_name == super_name:
            return True
        cls = self._classes.get(sub_name)
        while cls is not None and cls.parent is not None:
            if cls.parent.name == super_name:
                return True
            cls = cls.parent
        return False

    def ancestors(self, name: str) -> list[str]:
        result: list[str] = []
        cls = self._classes.get(name)
        while cls is not None:
            result.append(cls.name)
            cls = cls.parent
        return result


class ExtendedSemanticVisitor(AstVisitor):
    """un ExtendedSemanticVisitor por compilacion, sin estado compartido entre llamadas."""

    def __init__(self, symbols: SymbolTable, diagnostics: DiagnosticBag) -> None:
        super().__init__()
        self._symbols = symbols
        self._diag = diagnostics
        self._classes: dict[str, ClassSymbol] = {
            sym.name: sym for sym in symbols.global_scope.symbols.values() if isinstance(sym, ClassSymbol)
        }
        self._hierarchy: ClassHierarchy = _ClassHierarchyView(self._classes)
        self._current_class: ClassSymbol | None = None

        self._dispatch = {
            ClassDecl: self._visit_class_decl,
            VarDecl: self._visit_var_decl,
            NewExpr: self._visit_new,
            ThisExpr: self._visit_this,
            PropertyAccess: self._visit_property_access,
            IndexAccess: self._visit_index_access,
            ArrayLiteral: self._visit_array_literal,
            Assignment: self._visit_assignment,
            Call: self._visit_call,
        }

    def analyze(self, program: Program) -> None:
        self._check_overrides(program)
        self.visit(program)

    # ------------------------------------------------------------------
    # helpers
    # ------------------------------------------------------------------

    def _emit(self, code: str, line: int, column: int, detail: str | None = None) -> None:
        template = _MESSAGES[code]
        message = template.format(detail=detail) if detail is not None else template
        severity = Severity.WARNING if code in _WARNING_CODES else Severity.ERROR
        self._diag.add(Diagnostic(code=code, message=message, line=line, column=column, severity=severity))

    def _emit_const_reassignment(self, line: int, column: int, name: str) -> None:
        # CPS-102 pertenece al catalogo core; la regla es la misma para variables y
        # atributos, asi que se conserva el codigo sin duplicarlo en el catalogo 2xx.
        self._diag.add(Diagnostic(
            code="CPS-102", message=f"no se puede reasignar la constante '{name}'",
            line=line, column=column, severity=Severity.ERROR,
        ))

    def _type_of(self, expr: Expr | None) -> Type:
        # mismo criterio que CoreSemanticVisitor._type_of: None ("todavia no
        # determinado") se convierte en ERROR solo al CONSUMIR el tipo, para no romper
        # comparaciones -- pero no se usa para decidir si hay que reportar un error
        # distinto (ver _visit_assignment, que si distingue ausencia de valor).
        if expr is None or expr.inferred_type is None:
            return ERROR
        return expr.inferred_type

    # ------------------------------------------------------------------
    # pre-pase de firmas: override exacto contra el metodo heredado
    # ------------------------------------------------------------------

    def _check_overrides(self, program: Program) -> None:
        for stmt in program.statements:
            if isinstance(stmt, ClassDecl):
                self._check_class_overrides(stmt)

    def _check_class_overrides(self, node: ClassDecl) -> None:
        cls = self._classes.get(node.name)
        if cls is None or cls.parent is None:
            return
        for member in node.members:
            if not isinstance(member, FunctionDecl) or member.is_constructor:
                continue
            own = cls.methods.get(member.name)
            if own is None:
                continue
            inherited = cls.parent.lookup_member(member.name)
            if not isinstance(inherited, FunctionSymbol):
                continue  # ningun metodo heredado con ese nombre: no es un override
            code = check_override(own, inherited)
            if code is not None:
                self._emit(code, member.line, member.column, member.name)

    # ------------------------------------------------------------------
    # declaraciones: la compatibilidad de tipos la valida la core (CPS-100) en la
    # re-pasada de extended_semantics.analyze; aca solo queda el [] sin contexto
    # ------------------------------------------------------------------

    def _visit_var_decl(self, node: VarDecl) -> None:
        if node.initializer is None:
            return
        self.visit(node.initializer)
        # sin anotacion, un [] no tiene de donde sacar el tipo de sus elementos
        if node.declared_type is None and isinstance(node.initializer.inferred_type, EmptyArrayType):
            self._emit("CPS-214", node.line, node.column)

    # ------------------------------------------------------------------
    # clases: trackeo de la clase actual, 'this' y 'new'
    # ------------------------------------------------------------------

    def _visit_class_decl(self, node: ClassDecl) -> None:
        cls = self._classes.get(node.name)
        previous = self._current_class
        self._current_class = cls
        try:
            for member in node.members:
                self.visit(member)
        finally:
            self._current_class = previous

    def _visit_this(self, node: ThisExpr) -> None:
        # la validacion estructural ('this' solo dentro de metodo/constructor) ya la
        # hace el frontend (CPS-040); aca solo falta el tipo. si no hay clase actual
        # (ya se reporto CPS-040), se deja ERROR -- se absorbe en silencio.
        node.inferred_type = ClassType(self._current_class.name) if self._current_class is not None else ERROR

    def _visit_new(self, node: NewExpr) -> None:
        for arg in node.args:
            self.visit(arg)
        cls = self._classes.get(node.class_name)
        arg_types = [self._type_of(arg) for arg in node.args]
        result, code, detail = check_new_call(node.class_name, cls, arg_types, self._hierarchy)
        if code is not None:
            self._emit(code, node.line, node.column, detail)
        node.inferred_type = result

    # ------------------------------------------------------------------
    # miembros y arreglos: lectura
    # ------------------------------------------------------------------

    def _visit_property_access(self, node: PropertyAccess) -> None:
        self.visit(node.obj)
        obj_type = self._type_of(node.obj)
        result, code, detail = check_property_access(obj_type, node.name, self._classes)
        if code is not None:
            self._emit(code, node.line, node.column, detail)
        node.inferred_type = result

    def _visit_index_access(self, node: IndexAccess) -> None:
        self.visit(node.collection)
        self.visit(node.index)
        index_type = self._type_of(node.index)
        if not is_valid_index_type(index_type):
            self._emit("CPS-205", node.index.line, node.index.column)
        collection_type = self._type_of(node.collection)
        result, code = check_index_access(collection_type)
        if code is not None:
            self._emit(code, node.line, node.column)
        node.inferred_type = result

    def _visit_array_literal(self, node: ArrayLiteral) -> None:
        for element in node.elements:
            self.visit(element)
        element_types = [self._type_of(element) for element in node.elements]
        result, code = check_array_literal(element_types, self._hierarchy)
        if code is not None:
            self._emit(code, node.line, node.column)
        node.inferred_type = result

    # ------------------------------------------------------------------
    # miembros y arreglos: escritura (destino de asignacion) y llamadas a metodo
    # ------------------------------------------------------------------

    def _check_assignment_compat(
        self, target_type: Type, value: Expr, code: str, line: int, column: int, detail: str | None,
    ) -> None:
        value_type = self._type_of(value)
        if isinstance(target_type, ErrorType) or isinstance(value_type, ErrorType):
            return
        if not is_assignable(target_type, value_type, self._hierarchy):
            self._emit(code, line, column, detail)

    def _visit_assignment(self, node: Assignment) -> None:
        self.visit(node.value)
        target = node.target
        if isinstance(target, PropertyAccess):
            self._visit_property_access(target)
            obj_type = self._type_of(target.obj)
            cls = self._classes.get(obj_type.name) if isinstance(obj_type, ClassType) else None
            member = cls.lookup_member(target.name) if cls is not None else None
            if isinstance(member, VariableSymbol) and member.is_const:
                self._emit_const_reassignment(node.line, node.column, target.name)
            self._check_assignment_compat(
                target.inferred_type, node.value, "CPS-203", node.line, node.column, target.name,
            )
            node.inferred_type = target.inferred_type
            return
        if isinstance(target, IndexAccess):
            self._visit_index_access(target)
            self._check_assignment_compat(
                target.inferred_type, node.value, "CPS-204", node.line, node.column, None,
            )
            node.inferred_type = target.inferred_type
            return
        # target Identifier: lo valida la core con CPS-100 en la re-pasada, cuando el
        # valor ya trae el tipo que le puso esta etapa. validarlo aca otra vez seria
        # reportar la misma causa dos veces.

    def _visit_call(self, node: Call) -> None:
        for arg in node.args:
            self.visit(arg)
        callee = node.callee
        if not isinstance(callee, PropertyAccess):
            # callee Identifier (funcion top-level): ya lo resolvio la semantica core.
            self.visit(callee)
            return
        self.visit(callee.obj)
        obj_type = self._type_of(callee.obj)
        arg_types = [self._type_of(arg) for arg in node.args]
        result, code, detail = check_method_call(obj_type, callee.name, arg_types, self._classes, self._hierarchy)
        if code is not None:
            self._emit(code, node.line, node.column, detail)
        # los metodos no son valores (compiscript no tiene funciones de primera clase),
        # mismo criterio que CoreSemanticVisitor._visit_call con funciones top-level.
        callee.inferred_type = ERROR
        node.inferred_type = result
