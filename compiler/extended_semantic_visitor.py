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
propia, pero solo para cerrar un hueco puntual de la arquitectura de dos pasadas (ver mas
abajo) -- no repite ninguna validacion que la core ya haya hecho.

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

nota sobre un hueco real de la arquitectura de dos pasadas (documentado en el README,
seccion "Semantica core > Division con la semantica extendida" y en el handoff, 4.4):
`CoreSemanticVisitor._check_declared_initializer` valida `let x: T = expr;` y
`x = expr;` usando `expr.inferred_type` en el momento en que la CORE los visita -- si
`expr` es un NewExpr/ArrayLiteral/PropertyAccess/IndexAccess/llamada a metodo, ese tipo
todavia es None en ese momento (esta etapa no corrio todavia), asi que la comparacion se
salta por completo, NO se absorbe como "compatible": nunca se valida. Como este visitor
corre despues y sabe leer el declared_type sintactico (`_resolve_declared_type`, mismo
calculo que `symbol_collector._resolve_type` con los mismos `self._classes`) y el tipo
que un `Assignment.target` Identifier ya trae cacheado (`target.inferred_type`, que la
core siempre escribe, incluso cuando no llego a validar nada), `_visit_var_decl` y la
rama Identifier de `_visit_assignment` cierran ese hueco especificamente para las
expresiones que son responsabilidad exclusiva de esta etapa (`_is_extended_typed`), sin
tocar ni duplicar nada que la core ya haya validado bien (evita reportar el mismo error
dos veces con codigos distintos).

catalogo de mensajes: CPS-2xx esta reservado a esta etapa (frontend usa CPS-0xx, la
semantica core CPS-1xx). mismo criterio que core_semantic_visitor.py: catalogo propio
local (_MESSAGES), reutilizando de diagnostics.py solo el mecanismo compartido
(Diagnostic, DiagnosticBag, Severity).
"""
from __future__ import annotations

from compiler.array_rules import check_array_literal, check_index_access, is_valid_index_type
from compiler.ast_nodes import (
    ArrayLiteral, Assignment, AstVisitor, Call, ClassDecl, Expr, FunctionDecl, Identifier,
    IndexAccess, NewExpr, Program, PropertyAccess, ThisExpr, TypeRef, VarDecl,
)
from compiler.class_rules import check_method_call, check_new_call, check_override, check_property_access
from compiler.diagnostics import Diagnostic, DiagnosticBag, Severity
from compiler.scopes import SymbolTable
from compiler.symbols import ClassSymbol, FunctionSymbol, VariableSymbol
from compiler.types import (
    ArrayType, BOOLEAN, ClassHierarchy, ClassType, ERROR, EmptyArrayType, ErrorType, INTEGER, STRING, Type,
    is_assignable,
)

# nombres de tipo primitivo tal como aparecen en una TypeRef sintactica. mismo mapeo que
# symbol_collector._base_type_name_to_type, duplicado a proposito (3 lineas, sin logica)
# para no depender de un helper privado de un modulo ajeno.
_PRIMITIVE_TYPES: dict[str, Type] = {"integer": INTEGER, "string": STRING, "boolean": BOOLEAN}

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
    "CPS-209": "tipo incompatible en la inicializacion/asignacion de '{detail}'",
    "CPS-210": "numero de argumentos incorrecto en 'new {detail}(...)'",
    "CPS-211": "el argumento {detail} es incompatible con el parametro del constructor",
    "CPS-212": "numero de argumentos incorrecto en la llamada al metodo '{detail}'",
    "CPS-213": "el argumento {detail} es incompatible con el parametro del metodo",
    "CPS-214": "el literal de arreglo vacio requiere un tipo de contexto",
}

# ninguno de estos codigos es advertencia: todos impiden result.ok, a diferencia de
# CPS-117/118 en la core.
_WARNING_CODES: set[str] = set()


def _is_extended_typed(expr: Expr) -> bool:
    """
    True si el tipo de `expr` es responsabilidad EXCLUSIVA de esta etapa (la core lo deja
    en None): NewExpr, ArrayLiteral, PropertyAccess, IndexAccess, o un Call a metodo
    (callee PropertyAccess). se usa para decidir cuando vale la pena cerrar el hueco de
    `_visit_var_decl`/`_visit_assignment` (ver docstring del modulo) sin volver a
    validar -- y potencialmente duplicar el diagnostico de -- una expresion que la
    semantica core ya valido correctamente.
    """
    if isinstance(expr, (NewExpr, ArrayLiteral, PropertyAccess, IndexAccess)):
        return True
    return isinstance(expr, Call) and isinstance(expr.callee, PropertyAccess)


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
    # declaraciones: cierra el hueco de la arquitectura de dos pasadas (ver docstring)
    # ------------------------------------------------------------------

    def _resolve_declared_type(self, type_ref: TypeRef | None) -> Type | None:
        """
        misma resolucion que symbol_collector._resolve_type, duplicada aca (no es logica
        nueva: nombre de primitivo o de clase ya conocida, mas [] anidados) para no
        depender de un helper privado de un modulo ajeno. devuelve None si no hay
        anotacion o si el nombre de tipo no se reconoce (ya reportado por el frontend
        como CPS-030, no hay nada que re-chequear aca).
        """
        if type_ref is None:
            return None
        base = _PRIMITIVE_TYPES.get(type_ref.base_name)
        if base is None:
            if type_ref.base_name not in self._classes:
                return None
            base = ClassType(type_ref.base_name)
        result: Type = base
        for _ in range(type_ref.array_dimensions):
            result = ArrayType(result)
        return result

    def _visit_var_decl(self, node: VarDecl) -> None:
        if node.initializer is not None:
            self.visit(node.initializer)
        if node.declared_type is None or node.initializer is None:
            if node.initializer is not None and isinstance(node.initializer.inferred_type, EmptyArrayType):
                self._emit("CPS-214", node.line, node.column)
            return
        if not _is_extended_typed(node.initializer):
            return  # la semantica core ya lo valido con el tipo correcto
        declared = self._resolve_declared_type(node.declared_type)
        if declared is None:
            return
        self._check_assignment_compat(declared, node.initializer, "CPS-209", node.line, node.column, node.name)

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
        # target es Identifier: la semantica core ya resolvio target.inferred_type (el
        # tipo declarado de la variable, cacheado ahi por CoreSemanticVisitor incluso
        # cuando no llego a validar el valor -- ver docstring del modulo), no se re-visita
        # el target. si el VALOR es de un tipo que la core no pudo tipar a tiempo, cierra
        # el mismo hueco que _visit_var_decl para reasignaciones (`x = new Foo();`).
        if isinstance(target, Identifier) and _is_extended_typed(node.value):
            self._check_assignment_compat(
                target.inferred_type, node.value, "CPS-209", node.line, node.column, target.name,
            )

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
