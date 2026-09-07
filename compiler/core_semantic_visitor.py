"""
visitor que recorre el ast propio y ejecuta las reglas semanticas core: declaraciones,
asignaciones, expresiones, funciones y control de flujo. coordina el recorrido y delega
en expression_rules / function_rules / control_flow_rules (srp) -- no duplica type
checking (types.py), lookup (scopes.py) ni el mecanismo de diagnosticos (diagnostics.py).

NO reconstruye ast, scopes ni tabla de simbolos: symbol_collector.py ya armo el arbol de
scopes completo con todas las variables/parametros/clases/funciones declaradas. este
visitor solo se mueve por ese arbol ya existente, ubicando el scope de cada nodo por su
posicion (line, column) -- el mismo par que scopes.py usa en find_scope_for -- cacheado
en un diccionario para que sea O(1) por nodo en vez de recorrer todo el arbol en cada
visita. nunca se llama a SymbolTable.push() aca: eso crearia scopes nuevos y paralelos,
justo lo que gate b prohibe.

catalogo de mensajes: CPS-1xx esta reservado a la semantica core (ver diagnostics.py,
donde el frontend deja ese rango libre y un test propio le impide invadirlo). como
diagnostics.py es propiedad ajena y su unico catalogo (_MESSAGES) es exclusivamente del
frontend, este modulo mantiene su propio catalogo CPS-1xx aca -- unica fuente de verdad
para los mensajes de la semantica core -- y reutiliza de diagnostics.py solo el mecanismo
compartido: las clases Diagnostic, DiagnosticBag y Severity.
"""
from __future__ import annotations

from compiler.ast_nodes import (
    Assignment, AstVisitor, BinaryOp, Block, BooleanLiteral, Call, ClassDecl, DoWhileStatement,
    Expr, ForStatement, ForeachStatement, FunctionDecl, Identifier, IfStatement,
    IntegerLiteral, NullLiteral, Program, ReturnStatement, Stmt, StringLiteral,
    SwitchStatement, Ternary, TryCatchStatement, UnaryOp, VarDecl, WhileStatement,
)
from compiler.control_flow_rules import check_foreach_iterable, check_switch_case, check_switch_subject, find_dead_code
from compiler.diagnostics import Diagnostic, DiagnosticBag, Severity
from compiler.expression_rules import check_binary_op, check_condition, check_ternary, check_unary_op
from compiler.function_rules import ReturnTracker, check_call, check_return, finalize_return_type
from compiler.scopes import Scope, SymbolTable
from compiler.symbols import ClassSymbol, FunctionSymbol, VariableSymbol
from compiler.types import (
    ArrayType, BOOLEAN, ClassHierarchy, ERROR, ErrorType, INTEGER, NULL, STRING, Type,
    is_assignable,
)

# catalogo unico de mensajes de la semantica core. mismo formato que el catalogo del
# frontend (texto con placeholder {detail}), pero es una tabla propia: CPS-1xx no vive
# en diagnostics.py (ver docstring del modulo).
_MESSAGES: dict[str, str] = {
    "CPS-100": "tipo incompatible en la inicializacion/asignacion de '{detail}'",
    "CPS-101": "'{detail}' necesita un tipo declarado o un inicializador",
    "CPS-102": "no se puede reasignar la constante '{detail}'",
    "CPS-103": "identificador no declarado: '{detail}'",
    "CPS-104": "operandos incompatibles para el operador '{detail}'",
    "CPS-105": "el operador relacional '{detail}' requiere operandos numericos",
    "CPS-106": "los operandos de '{detail}' no son comparables",
    "CPS-107": "el operador logico '{detail}' requiere operandos booleanos",
    "CPS-108": "el operando del operador unario '{detail}' tiene tipo incompatible",
    "CPS-109": "la condicion de '{detail}' debe ser booleana",
    "CPS-110": "'{detail}' no es una funcion",
    "CPS-111": "numero de argumentos incorrecto en la llamada a '{detail}'",
    "CPS-112": "el argumento {detail} es incompatible con el parametro esperado",
    "CPS-113": "el valor de 'return' es incompatible con el tipo de retorno de '{detail}'",
    "CPS-114": "no hay un tipo de retorno comun entre los 'return' de '{detail}'",
    "CPS-115": "el discriminante de 'switch' debe ser integer, string o boolean",
    "CPS-116": "el 'case' es incompatible con el tipo del discriminante",
    "CPS-117": "codigo inalcanzable",
    "CPS-118": "el operador ternario no tiene un tipo comun entre sus ramas",
    "CPS-119": "el identificador '{detail}' no puede usarse como valor sin una construccion o llamada valida",
    "CPS-120": "la expresion de 'foreach' debe ser un arreglo con tipo de elemento conocido",
}

# codigos que son advertencia y no error, igual que _WARNING_CODES en diagnostics.py
_WARNING_CODES = {"CPS-117"}


class _ClassHierarchyView:
    """
    protocolo minimo de types.py (ClassHierarchy) sobre las clases ya resueltas por el
    frontend. no importa symbol_collector.py: se reconstruye aca a partir de
    ClassSymbol.parent, que frontend.analyze_source ya deja resuelto en cada ClassSymbol
    de la tabla de simbolos -- no es logica nueva, es leer un puntero que ya existe.
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


class _ScopeCursor:
    """context manager liviano: mueve el cursor del visitor a un scope ya existente y lo restaura al salir."""

    __slots__ = ("_visitor", "_scope", "_previous")

    def __init__(self, visitor: "CoreSemanticVisitor", scope: Scope) -> None:
        self._visitor = visitor
        self._scope = scope

    def __enter__(self) -> Scope:
        self._previous = self._visitor._current
        self._visitor._current = self._scope
        return self._scope

    def __exit__(self, *exc_info) -> None:
        self._visitor._current = self._previous


class CoreSemanticVisitor(AstVisitor):
    """un CoreSemanticVisitor por compilacion, sin estado compartido entre llamadas."""

    def __init__(self, symbols: SymbolTable, diagnostics: DiagnosticBag) -> None:
        super().__init__()
        self._symbols = symbols
        self._diag = diagnostics
        self._current: Scope = symbols.global_scope

        # posicion -> scope, para no recorrer todo el arbol de scopes en cada nodo visitado
        self._scope_by_pos: dict[tuple[int, int], Scope] = {
            (scope.line, scope.column): scope
            for scope in symbols.all_scopes()
            if scope is not symbols.global_scope
        }
        self._classes: dict[str, ClassSymbol] = {
            sym.name: sym for sym in symbols.global_scope.symbols.values() if isinstance(sym, ClassSymbol)
        }
        self._hierarchy: ClassHierarchy = _ClassHierarchyView(self._classes)
        self._current_class: ClassSymbol | None = None
        self._return_stack: list[ReturnTracker | None] = []
        self._function_nodes: list[FunctionDecl] = []

        self._dispatch = {
            Program: self._visit_program,
            Block: self._visit_block,
            VarDecl: self._visit_var_decl,
            Assignment: self._visit_assignment,
            BinaryOp: self._visit_binary_op,
            UnaryOp: self._visit_unary_op,
            Ternary: self._visit_ternary,
            Identifier: self._visit_identifier,
            IntegerLiteral: self._visit_integer_literal,
            StringLiteral: self._visit_string_literal,
            BooleanLiteral: self._visit_boolean_literal,
            NullLiteral: self._visit_null_literal,
            Call: self._visit_call,
            FunctionDecl: self._visit_function_decl,
            ClassDecl: self._visit_class_decl,
            IfStatement: self._visit_if,
            WhileStatement: self._visit_while,
            DoWhileStatement: self._visit_do_while,
            ForStatement: self._visit_for,
            ForeachStatement: self._visit_foreach,
            TryCatchStatement: self._visit_try_catch,
            SwitchStatement: self._visit_switch,
            ReturnStatement: self._visit_return,
        }

    def analyze(self, program: Program) -> None:
        self.visit(program)

    # ------------------------------------------------------------------
    # navegacion de scopes ya construidos (nunca se hace push, solo se mueve el cursor)
    # ------------------------------------------------------------------

    def _scope_at(self, node) -> Scope:
        # fail-closed: si por algun motivo no hay scope registrado en esa posicion (no
        # deberia pasar para los nodos que symbol_collector sabe que abren scope), se
        # queda en el scope actual en vez de reventar.
        return self._scope_by_pos.get((node.line, node.column), self._current)

    def _enter(self, node) -> _ScopeCursor:
        return _ScopeCursor(self, self._scope_at(node))

    def _emit(self, code: str, line: int, column: int, detail: str | None = None) -> None:
        template = _MESSAGES[code]
        message = template.format(detail=detail) if detail is not None else template
        severity = Severity.WARNING if code in _WARNING_CODES else Severity.ERROR
        self._diag.add(Diagnostic(code=code, message=message, line=line, column=column, severity=severity))

    def _lookup_with_scope(self, name: str) -> tuple[object | None, Scope | None]:
        scope: Scope | None = self._current
        while scope is not None:
            found = scope.lookup_local(name)
            if found is not None:
                return found, scope
            scope = scope.parent
        return None, None

    def _type_of(self, expr: Expr | None) -> Type:
        if expr is None or expr.inferred_type is None:
            return ERROR
        return expr.inferred_type

    def _check_dead_code(self, statements: list[Stmt]) -> None:
        for stmt in find_dead_code(statements):
            self._emit("CPS-117", stmt.line, stmt.column)

    def _check_condition(self, context: str, expr: Expr) -> None:
        code = check_condition(self._type_of(expr))
        if code is not None:
            self._emit(code, expr.line, expr.column, context)

    def _check_declared_initializer(self, symbol: VariableSymbol, initializer: Expr | None,
                                     line: int, column: int, name: str) -> None:
        """
        valida (si `symbol` ya tiene tipo) o infiere (si no) el tipo de una declaracion o
        asignacion contra su inicializador/valor. si hay inicializador pero su tipo aun
        no se determino (una PropertyAccess/IndexAccess/etc, que resuelve la extendida),
        no se reporta nada todavia: se espera a que esa etapa complete inferred_type.
        """
        has_initializer = initializer is not None
        value_type = initializer.inferred_type if has_initializer else None
        if symbol.type is not None:
            # Una pasada anterior pudo guardar ERROR solo porque un nodo extendido aun
            # no tenia tipo. La revalidacion posterior puede reemplazarlo por el tipo real.
            if (isinstance(symbol.type, ErrorType) and value_type is not None
                    and not isinstance(value_type, ErrorType)):
                symbol.type = value_type
                return
            if value_type is not None and not is_assignable(symbol.type, value_type, self._hierarchy):
                self._emit("CPS-100", line, column, name)
            return
        if value_type is not None:
            symbol.type = value_type
        elif not has_initializer:
            self._emit("CPS-101", line, column, name)

    def _resolve_function_symbol(self, node: FunctionDecl) -> FunctionSymbol | None:
        """
        resuelve el FunctionSymbol que corresponde a `node`, sin crear ninguno nuevo.
        - metodo: se busca en la clase actual (self._current_class), ya predeclarado por
          symbol_collector en fase 1.
        - funciones top-level y anidadas: se buscan en el scope contenedor actual.
        """
        if node.is_method:
            return self._current_class.methods.get(node.name) if self._current_class else None
        found = self._current.lookup_local(node.name)
        if isinstance(found, FunctionSymbol) and found.line == node.line and found.column == node.column:
            return found
        return None

    # ------------------------------------------------------------------
    # programa y bloques
    # ------------------------------------------------------------------

    def _visit_program(self, node: Program) -> None:
        self._check_dead_code(node.statements)
        for stmt in node.statements:
            self.visit(stmt)

    def _visit_block(self, node) -> None:
        with self._enter(node):
            self._check_dead_code(node.statements)
            for stmt in node.statements:
                self.visit(stmt)

    # ------------------------------------------------------------------
    # declaraciones y asignacion
    # ------------------------------------------------------------------

    def _visit_var_decl(self, node: VarDecl) -> None:
        if node.initializer is not None:
            self.visit(node.initializer)
        symbol = self._current.lookup_local(node.name)
        if isinstance(symbol, VariableSymbol):
            self._check_declared_initializer(symbol, node.initializer, node.line, node.column, node.name)

    def _visit_assignment(self, node: Assignment) -> None:
        self.visit(node.value)
        target = node.target
        if isinstance(target, Identifier):
            symbol = self._current.lookup(target.name)
            if not isinstance(symbol, VariableSymbol):
                self._emit("CPS-103", target.line, target.column, target.name)
                target.inferred_type = ERROR
                node.inferred_type = ERROR
                return
            if symbol.is_const:
                self._emit("CPS-102", target.line, target.column, target.name)
            self._check_declared_initializer(symbol, node.value, node.line, node.column, target.name)
            target.inferred_type = symbol.type if symbol.type is not None else ERROR
            node.inferred_type = target.inferred_type
            return
        # PropertyAccess / IndexAccess: destino de clases o arreglos, lo completa la
        # etapa extendida (persona 3). se visita para no dejar sub-arboles sin recorrer.
        self.visit(target)
        node.inferred_type = None

    # ------------------------------------------------------------------
    # expresiones core
    # ------------------------------------------------------------------

    def _visit_identifier(self, node: Identifier) -> None:
        symbol, declaring_scope = self._lookup_with_scope(node.name)
        if symbol is None:
            self._emit("CPS-103", node.line, node.column, node.name)
            node.inferred_type = ERROR
            return
        if isinstance(symbol, VariableSymbol):
            # Las closures basicas solo capturan el entorno que ya existia al
            # declararse la funcion anidada; no implementamos hoisting de variables.
            if (len(self._function_nodes) > 1 and declaring_scope is not self._current
                    and (symbol.line, symbol.column) > (self._function_nodes[-1].line,
                                                         self._function_nodes[-1].column)):
                self._emit("CPS-103", node.line, node.column, node.name)
                node.inferred_type = ERROR
                return
            node.inferred_type = symbol.type if symbol.type is not None else ERROR
            return
        # Compiscript no tiene funciones ni clases de primera clase. Las llamadas y
        # construcciones se resuelven por sus visitors propios; fuera de esos contextos
        # el nombre no representa un valor y debe diagnosticarse una sola vez.
        if isinstance(symbol, (FunctionSymbol, ClassSymbol)):
            self._emit("CPS-119", node.line, node.column, node.name)
        node.inferred_type = ERROR

    def _visit_integer_literal(self, node) -> None:
        node.inferred_type = INTEGER

    def _visit_string_literal(self, node) -> None:
        node.inferred_type = STRING

    def _visit_boolean_literal(self, node) -> None:
        node.inferred_type = BOOLEAN

    def _visit_null_literal(self, node) -> None:
        node.inferred_type = NULL

    def _visit_binary_op(self, node: BinaryOp) -> None:
        self.visit(node.left)
        self.visit(node.right)
        result, code, detail = check_binary_op(node.op, self._type_of(node.left), self._type_of(node.right), self._hierarchy)
        if code is not None:
            self._emit(code, node.line, node.column, detail)
        node.inferred_type = result

    def _visit_unary_op(self, node: UnaryOp) -> None:
        self.visit(node.operand)
        result, code, detail = check_unary_op(node.op, self._type_of(node.operand))
        if code is not None:
            self._emit(code, node.line, node.column, detail)
        node.inferred_type = result

    def _visit_ternary(self, node: Ternary) -> None:
        self.visit(node.condition)
        self._check_condition("ternario", node.condition)
        self.visit(node.then_expr)
        self.visit(node.else_expr)
        result, code = check_ternary(self._type_of(node.then_expr), self._type_of(node.else_expr), self._hierarchy)
        if code is not None:
            self._emit(code, node.line, node.column)
        node.inferred_type = result

    def _visit_call(self, node: Call) -> None:
        for arg in node.args:
            self.visit(arg)
        callee = node.callee
        if isinstance(callee, Identifier):
            symbol = self._current.lookup(callee.name)
            if symbol is None:
                self._emit("CPS-103", callee.line, callee.column, callee.name)
                callee.inferred_type = ERROR
                node.inferred_type = ERROR
                return
            if not isinstance(symbol, FunctionSymbol):
                self._emit("CPS-110", callee.line, callee.column, callee.name)
                callee.inferred_type = ERROR
                node.inferred_type = ERROR
                return
            callee.inferred_type = ERROR  # las funciones no son valores, ver _visit_identifier
            arg_types = [self._type_of(arg) for arg in node.args]
            result, code, detail = check_call(callee.name, symbol, arg_types, self._hierarchy)
            if code is not None:
                self._emit(code, node.line, node.column, detail)
            node.inferred_type = result
            return
        # llamada a metodo (callee es PropertyAccess) u otra forma: la resuelve la
        # etapa extendida, que conoce clases y objetos.
        self.visit(callee)
        node.inferred_type = None

    # ------------------------------------------------------------------
    # funciones y clases
    # ------------------------------------------------------------------

    def _visit_function_decl(self, node: FunctionDecl) -> None:
        function = self._resolve_function_symbol(node)
        with self._enter(node):
            self._function_nodes.append(node)
            try:
                if function is None:
                # Aisla retornos de una funcion cuya firma no pudo resolverse: nunca
                # deben terminar en el tracker de su funcion exterior.
                    self._return_stack.append(None)
                    try:
                        self._check_dead_code(node.body.statements)
                        for stmt in node.body.statements:
                            self.visit(stmt)
                    finally:
                        self._return_stack.pop()
                    return
            # El valor mutable del simbolo puede ser una inferencia de una pasada previa;
            # la presencia de anotacion en el AST es la unica fuente de verdad.
                tracker = ReturnTracker(function=function, declared=function.return_type if node.return_type is not None else None)
                self._return_stack.append(tracker)
                try:
                    self._check_dead_code(node.body.statements)
                    for stmt in node.body.statements:
                        self.visit(stmt)
                finally:
                    self._return_stack.pop()
                code = finalize_return_type(tracker, self._hierarchy)
                if code is not None:
                    self._emit(code, node.line, node.column, function.name)
            finally:
                self._function_nodes.pop()

    def _visit_class_decl(self, node: ClassDecl) -> None:
        cls = self._classes.get(node.name)
        previous_class = self._current_class
        self._current_class = cls
        try:
            with self._enter(node):
                for member in node.members:
                    if isinstance(member, FunctionDecl):
                        self.visit(member)
                    elif isinstance(member, VarDecl):
                        self._visit_field(cls, member)
        finally:
            self._current_class = previous_class

    def _visit_field(self, cls: ClassSymbol | None, node: VarDecl) -> None:
        if node.initializer is not None:
            self.visit(node.initializer)
        if cls is None:
            return
        field_symbol = cls.fields.get(node.name)
        if field_symbol is not None:
            self._check_declared_initializer(field_symbol, node.initializer, node.line, node.column, node.name)

    # ------------------------------------------------------------------
    # control de flujo
    # ------------------------------------------------------------------

    def _visit_if(self, node: IfStatement) -> None:
        self.visit(node.condition)
        self._check_condition("if", node.condition)
        self.visit(node.then_block)
        if node.else_block is not None:
            self.visit(node.else_block)

    def _visit_while(self, node: WhileStatement) -> None:
        self.visit(node.condition)
        self._check_condition("while", node.condition)
        with self._enter(node):
            self.visit(node.body)

    def _visit_do_while(self, node: DoWhileStatement) -> None:
        with self._enter(node):
            self.visit(node.body)
        self.visit(node.condition)
        self._check_condition("do-while", node.condition)

    def _visit_for(self, node: ForStatement) -> None:
        with self._enter(node):
            if node.init is not None:
                self.visit(node.init)
            if node.condition is not None:
                self.visit(node.condition)
                self._check_condition("for", node.condition)
            if node.update is not None:
                self.visit(node.update)
            self.visit(node.body)

    def _visit_foreach(self, node: ForeachStatement) -> None:
        self.visit(node.iterable)
        iterable_type = self._type_of(node.iterable)
        code = check_foreach_iterable(iterable_type)
        if code is not None:
            self._emit(code, node.iterable.line, node.iterable.column)
        with self._enter(node):
            var_symbol = self._current.lookup_local(node.var_name)
            if isinstance(var_symbol, VariableSymbol):
                var_symbol.type = iterable_type.element if isinstance(iterable_type, ArrayType) else ERROR
            self.visit(node.body)

    def _visit_try_catch(self, node: TryCatchStatement) -> None:
        self.visit(node.try_block)
        with self._enter(node):
            self._check_dead_code(node.catch_block.statements)
            for stmt in node.catch_block.statements:
                self.visit(stmt)

    def _visit_switch(self, node: SwitchStatement) -> None:
        self.visit(node.subject)
        subject_type = self._type_of(node.subject)
        code = check_switch_subject(subject_type)
        if code is not None:
            self._emit(code, node.subject.line, node.subject.column)
        with self._enter(node):
            for case in node.cases:
                self.visit(case.value)
                case_code = check_switch_case(subject_type, self._type_of(case.value), self._hierarchy)
                if case_code is not None:
                    self._emit(case_code, case.value.line, case.value.column)
                self._check_dead_code(case.statements)
                for stmt in case.statements:
                    self.visit(stmt)
            if node.default_statements is not None:
                self._check_dead_code(node.default_statements)
                for stmt in node.default_statements:
                    self.visit(stmt)

    def _visit_return(self, node: ReturnStatement) -> None:
        if node.value is not None:
            self.visit(node.value)
        if not self._return_stack:
            return  # ya reportado como CPS-014 por el frontend (return fuera de funcion)
        value_type = self._type_of(node.value) if node.value is not None else None
        tracker = self._return_stack[-1]
        if tracker is None:
            return
        code = check_return(tracker, value_type, self._hierarchy)
        if code is not None:
            self._emit(code, node.line, node.column, tracker.function.name)
