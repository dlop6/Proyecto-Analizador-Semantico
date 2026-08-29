"""
recolector de simbolos (persona 1). recorre el ast propio y arma la tabla de simbolos
en tres pasadas, todas dentro de un solo objeto SymbolCollector:

  fase 0 (predeclaracion): registra nombres de clases y funciones TOP-LEVEL antes de
    tocar ningun cuerpo. asi "function fact(n){return fact(n-1);}" y "class A:B{}"
    con B declarada mas abajo funcionan sin trucos de resolucion perezosa.
  fase 1 (firmas): resuelve herencia, tipos de parametros/retorno/atributos. aca ya
    todos los nombres de clase existen, asi que resolver un ClassType nunca falla
    por orden de declaracion.
  fase 2 (cuerpos): recorre cuerpos de funciones/metodos/bloques, abre y cierra scopes
    segun las reglas de la fase H del plan, declara variables/parametros/this, valida
    duplicados y las reglas estructurales (break/continue/return fuera de contexto, etc).
"""
from __future__ import annotations

from compiler.ast_nodes import (
    Assignment, BinaryOp, Block, BooleanLiteral, BreakStatement, Call, ClassDecl,
    ContinueStatement, DoWhileStatement, ExprStatement, ForStatement, ForeachStatement,
    FunctionDecl, Identifier, IfStatement, IndexAccess, IntegerLiteral, NewExpr,
    NullLiteral, Param, PrintStatement, Program, PropertyAccess, ReturnStatement,
    StringLiteral, SwitchStatement, Ternary, ThisExpr, TryCatchStatement, TypeRef,
    UnaryOp, VarDecl, WhileStatement,
)
from compiler.diagnostics import DiagnosticBag
from compiler.scopes import ScopeKind, SymbolTable
from compiler.symbols import (
    CATCH_VAR_TYPE, CONSTRUCTOR_NAME, ClassSymbol, FunctionSymbol, THIS_NAME,
    VariableSymbol,
)
from compiler.types import ArrayType, BOOLEAN, ClassType, ERROR, INTEGER, STRING, Type


def _base_type_name_to_type(name: str) -> Type | None:
    """primitivos conocidos por nombre. None si es un nombre de clase (se resuelve aparte)."""
    return {"integer": INTEGER, "string": STRING, "boolean": BOOLEAN}.get(name)


class _ClassHierarchyView:
    """implementa el protocolo ClassHierarchy de types.py sobre las clases ya recolectadas."""

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


class SymbolCollector:
    """un collector por compilacion, sin estado compartido entre llamadas."""

    def __init__(self, diagnostics: DiagnosticBag) -> None:
        self._diag = diagnostics
        self.symbols = SymbolTable()
        self._classes: dict[str, ClassSymbol] = {}
        self._functions: dict[str, FunctionSymbol] = {}
        self.hierarchy = _ClassHierarchyView(self._classes)

    def collect(self, program: Program) -> SymbolTable:
        self._predeclare(program)
        self._resolve_signatures(program)
        self._visit_body_statements(program.statements)
        return self.symbols

    # ------------------------------------------------------------------
    # fase 0: predeclaracion de nombres top-level
    # ------------------------------------------------------------------

    def _predeclare(self, program: Program) -> None:
        for stmt in program.statements:
            if isinstance(stmt, ClassDecl):
                self._predeclare_class(stmt)
            elif isinstance(stmt, FunctionDecl):
                self._predeclare_function(stmt)

    def _predeclare_class(self, node: ClassDecl) -> None:
        existing = self.symbols.declare(ClassSymbol(name=node.name, line=node.line, column=node.column,
                                                      parent_name=node.parent_name, type=ClassType(node.name)))
        if existing is None:
            self._diag.error("CPS-020", node.line, node.column, detail=node.name)
            return
        self._classes[node.name] = existing  # type: ignore[assignment]

    def _predeclare_function(self, node: FunctionDecl) -> None:
        existing = self.symbols.declare(FunctionSymbol(name=node.name, line=node.line, column=node.column))
        if existing is None:
            self._diag.error("CPS-020", node.line, node.column, detail=node.name)
            return
        self._functions[node.name] = existing  # type: ignore[assignment]

    # ------------------------------------------------------------------
    # fase 1: resolucion de firmas (herencia, tipos de parametros/retorno/atributos)
    # ------------------------------------------------------------------

    def _resolve_signatures(self, program: Program) -> None:
        for stmt in program.statements:
            if isinstance(stmt, ClassDecl):
                self._resolve_class_signature(stmt)
            elif isinstance(stmt, FunctionDecl):
                self._resolve_function_signature(stmt)

    def _resolve_class_signature(self, node: ClassDecl) -> None:
        cls = self._classes.get(node.name)
        if cls is None:
            return  # ya se reporto duplicado en predeclaracion

        if node.parent_name is not None:
            parent = self._classes.get(node.parent_name)
            if parent is None:
                self._diag.error("CPS-023", node.line, node.column, detail=node.parent_name)
            else:
                cls.parent = parent
                if self._has_inheritance_cycle(cls):
                    self._diag.error("CPS-031", node.line, node.column, detail=node.name)
                    cls.parent = None  # cortamos el ciclo para no romper el resto del analisis

        for member in node.members:
            if isinstance(member, FunctionDecl):
                self._resolve_method_signature(cls, member)
            elif isinstance(member, VarDecl):
                self._resolve_field_signature(cls, member)

    def _has_inheritance_cycle(self, cls: ClassSymbol) -> bool:
        visited: set[str] = set()
        current: ClassSymbol | None = cls
        while current is not None:
            if current.name in visited:
                return True
            visited.add(current.name)
            current = current.parent
        return False

    def _resolve_method_signature(self, cls: ClassSymbol, node: FunctionDecl) -> None:
        if node.is_constructor and node.return_type is not None:
            self._diag.error("CPS-032", node.line, node.column)

        params = [
            VariableSymbol(name=p.name, line=p.line, column=p.column,
                            type=self._resolve_type(p.declared_type), is_param=True, initialized=True)
            for p in node.params
        ]
        return_type = self._resolve_type(node.return_type) if node.return_type else None
        fn = FunctionSymbol(
            name=node.name, line=node.line, column=node.column, params=params,
            return_type=return_type, is_constructor=node.is_constructor, is_method=True,
            owner_class=cls.name,
        )
        if node.name in cls.methods:
            self._diag.error("CPS-021", node.line, node.column, detail=node.name)
        else:
            cls.methods[node.name] = fn
            if node.is_constructor:
                cls.constructor = fn

    def _resolve_field_signature(self, cls: ClassSymbol, node: VarDecl) -> None:
        field_type = self._resolve_type(node.declared_type) if node.declared_type else None
        symbol = VariableSymbol(name=node.name, line=node.line, column=node.column,
                                 type=field_type, is_const=node.is_const, is_field=True)
        if node.name in cls.fields:
            self._diag.error("CPS-021", node.line, node.column, detail=node.name)
            return
        if cls.parent is not None and cls.parent.lookup_member(node.name) is not None:
            self._diag.warning("CPS-033", node.line, node.column, detail=node.name)
        cls.fields[node.name] = symbol

    def _resolve_function_signature(self, node: FunctionDecl) -> None:
        fn = self._functions.get(node.name)
        if fn is None:
            return
        fn.params = [
            VariableSymbol(name=p.name, line=p.line, column=p.column,
                            type=self._resolve_type(p.declared_type), is_param=True, initialized=True)
            for p in node.params
        ]
        fn.return_type = self._resolve_type(node.return_type) if node.return_type else None

    def _resolve_type(self, type_ref: TypeRef | None) -> Type | None:
        if type_ref is None:
            return None
        base = _base_type_name_to_type(type_ref.base_name)
        if base is None:
            if type_ref.base_name not in self._classes:
                self._diag.error("CPS-030", type_ref.line, type_ref.column, detail=type_ref.base_name)
                base = ERROR
            else:
                base = ClassType(type_ref.base_name)
        result: Type = base
        for _ in range(type_ref.array_dimensions):
            result = ArrayType(result)
        return result

    # ------------------------------------------------------------------
    # fase 2: cuerpos -- scopes, duplicados, this, break/continue/return
    # ------------------------------------------------------------------

    def _visit_body_statements(self, statements: list) -> None:
        for stmt in statements:
            self._visit_stmt(stmt)

    def _visit_stmt(self, node) -> None:
        handler = self._STMT_DISPATCH.get(type(node))
        if handler is not None:
            handler(self, node)
        else:
            self._visit_expr_in_stmt(node)

    def _visit_expr_in_stmt(self, node) -> None:
        """statements que solo envuelven una expresion (ExprStatement, PrintStatement)."""
        if isinstance(node, ExprStatement):
            self._visit_expr(node.expression)
        elif isinstance(node, PrintStatement):
            self._visit_expr(node.expression)

    def _visit_var_decl(self, node: VarDecl) -> None:
        if node.initializer is not None:
            self._visit_expr(node.initializer)
        elif node.is_const:
            # en la practica esto es inalcanzable: la gramatica exige '=' expression
            # en constantDeclaration, asi que un const sin inicializador ya es error
            # de sintaxis antes de llegar aca. se deja como defensa fail-closed.
            self._diag.error("CPS-011", node.line, node.column, detail=node.name)

        declared_type = self._resolve_type(node.declared_type) if node.declared_type else None
        symbol = VariableSymbol(name=node.name, line=node.line, column=node.column,
                                 type=declared_type, is_const=node.is_const,
                                 initialized=node.initializer is not None)
        if self.symbols.declare(symbol) is None:
            self._diag.error("CPS-020", node.line, node.column, detail=node.name)

    def _visit_function_decl(self, node: FunctionDecl) -> None:
        # top-level ya viene predeclarada; los metodos se resuelven en _visit_class_decl
        with self.symbols.push(ScopeKind.FUNCTION, f"function:{node.name}", node.line, node.column):
            self._declare_params(node.params)
            self._visit_function_body(node.body)

    def _declare_params(self, params: list[Param]) -> None:
        seen: set[str] = set()
        for p in params:
            if p.name in seen:
                self._diag.error("CPS-022", p.line, p.column, detail=p.name)
                continue
            seen.add(p.name)
            declared_type = self._resolve_type(p.declared_type) if p.declared_type else None
            self.symbols.declare(VariableSymbol(name=p.name, line=p.line, column=p.column,
                                                 type=declared_type, is_param=True, initialized=True))

    def _visit_function_body(self, body: Block) -> None:
        """
        el cuerpo de una funcion/metodo REUSA el scope FUNCTION recien abierto (no
        anida un BLOCK extra) -- asi 'function f(x){let x;}' es duplicado, como en
        typescript/java, en vez de shadowing legal.
        """
        for stmt in body.statements:
            self._visit_stmt(stmt)

    def _visit_class_decl(self, node: ClassDecl) -> None:
        cls = self._classes.get(node.name)
        with self.symbols.push(ScopeKind.CLASS, f"class:{node.name}", node.line, node.column) as class_scope:
            if cls is not None:
                cls.scope = class_scope
            for member in node.members:
                if isinstance(member, FunctionDecl):
                    self._visit_method(cls, member)
                # los atributos ya quedaron resueltos en fase 1, no hay cuerpo que recorrer

    def _visit_method(self, cls: ClassSymbol | None, node: FunctionDecl) -> None:
        with self.symbols.push(ScopeKind.FUNCTION, f"function:{node.name}", node.line, node.column):
            if cls is not None:
                # 'this' se resuelve como cualquier variable -- cero codigo especial en persona 2
                self.symbols.declare(VariableSymbol(
                    name=THIS_NAME, line=node.line, column=node.column,
                    type=ClassType(cls.name), is_const=True, is_implicit=True, initialized=True,
                ))
            self._declare_params(node.params)
            self._visit_function_body(node.body)

    def _visit_block(self, node: Block) -> None:
        with self.symbols.push(ScopeKind.BLOCK, "block", node.line, node.column):
            for stmt in node.statements:
                self._visit_stmt(stmt)

    def _visit_if(self, node: IfStatement) -> None:
        self._visit_expr(node.condition)
        self._visit_block(node.then_block)
        if node.else_block is not None:
            self._visit_block(node.else_block)

    def _visit_while(self, node: WhileStatement) -> None:
        self._visit_expr(node.condition)
        with self.symbols.push(ScopeKind.LOOP, "loop", node.line, node.column):
            for stmt in node.body.statements:
                self._visit_stmt(stmt)

    def _visit_do_while(self, node: DoWhileStatement) -> None:
        # la condicion se evalua fuera del scope del cuerpo (variables del cuerpo no
        # son visibles ahi), por eso no se mete dentro del 'with'
        with self.symbols.push(ScopeKind.LOOP, "loop", node.line, node.column):
            for stmt in node.body.statements:
                self._visit_stmt(stmt)
        self._visit_expr(node.condition)

    def _visit_for(self, node: ForStatement) -> None:
        """
        siempre 2 scopes: LOOP (cabecera) + BLOCK (cuerpo), sin importar si la cabecera
        tiene contenido. asi 'let i' de la cabecera no se filtra al scope circundante
        pero si es visible en condicion/actualizacion/cuerpo, y el cuerpo puede
        shadowearla sin ser duplicado.
        """
        with self.symbols.push(ScopeKind.LOOP, "loop", node.line, node.column):
            if isinstance(node.init, VarDecl):
                self._visit_var_decl(node.init)
            elif isinstance(node.init, Assignment):
                self._visit_expr(node.init)
            if node.condition is not None:
                self._visit_expr(node.condition)
            if node.update is not None:
                self._visit_expr(node.update)
            with self.symbols.push(ScopeKind.BLOCK, "block", node.body.line, node.body.column):
                for stmt in node.body.statements:
                    self._visit_stmt(stmt)

    def _visit_foreach(self, node: ForeachStatement) -> None:
        # la coleccion se visita ANTES de abrir el LOOP: la variable de iteracion
        # no debe ser visible ahi
        self._visit_expr(node.iterable)
        with self.symbols.push(ScopeKind.LOOP, "loop", node.line, node.column):
            # el tipo se deja en None a proposito: resolverlo requiere tipar 'iterable',
            # que es responsabilidad de persona 2. unico simbolo con tipo diferido de persona 1.
            self.symbols.declare(VariableSymbol(
                name=node.var_name, line=node.line, column=node.column,
                type=None, is_iteration_var=True, initialized=True,
            ))
            with self.symbols.push(ScopeKind.BLOCK, "block", node.body.line, node.body.column):
                for stmt in node.body.statements:
                    self._visit_stmt(stmt)

    def _visit_break(self, node: BreakStatement) -> None:
        in_loop = self.symbols.current.enclosing_of_kind(ScopeKind.LOOP)
        in_switch = self.symbols.current.enclosing_of_kind(ScopeKind.SWITCH)
        if in_loop is None and in_switch is None:
            self._diag.error("CPS-012", node.line, node.column)

    def _visit_continue(self, node: ContinueStatement) -> None:
        if self.symbols.current.enclosing_of_kind(ScopeKind.LOOP) is None:
            self._diag.error("CPS-013", node.line, node.column)

    def _visit_return(self, node: ReturnStatement) -> None:
        if node.value is not None:
            self._visit_expr(node.value)
        if self.symbols.current.enclosing_of_kind(ScopeKind.FUNCTION) is None:
            self._diag.error("CPS-014", node.line, node.column)

    def _visit_try_catch(self, node: TryCatchStatement) -> None:
        with self.symbols.push(ScopeKind.BLOCK, "try", node.try_block.line, node.try_block.column):
            for stmt in node.try_block.statements:
                self._visit_stmt(stmt)
        with self.symbols.push(ScopeKind.CATCH, "catch", node.line, node.column):
            self.symbols.declare(VariableSymbol(
                name=node.exception_name, line=node.line, column=node.column,
                type=CATCH_VAR_TYPE, initialized=True,
            ))
            # el cuerpo del catch REUSA este scope, no anida uno extra: redeclarar el
            # parametro adentro es duplicado, como en java
            for stmt in node.catch_block.statements:
                self._visit_stmt(stmt)

    def _visit_switch(self, node: SwitchStatement) -> None:
        self._visit_expr(node.subject)
        with self.symbols.push(ScopeKind.SWITCH, "switch", node.line, node.column):
            for case in node.cases:
                self._visit_expr(case.value)
                for stmt in case.statements:
                    self._visit_stmt(stmt)
            if node.default_statements is not None:
                for stmt in node.default_statements:
                    self._visit_stmt(stmt)

    _STMT_DISPATCH = {
        VarDecl: _visit_var_decl,
        FunctionDecl: _visit_function_decl,
        ClassDecl: _visit_class_decl,
        Block: _visit_block,
        IfStatement: _visit_if,
        WhileStatement: _visit_while,
        DoWhileStatement: _visit_do_while,
        ForStatement: _visit_for,
        ForeachStatement: _visit_foreach,
        BreakStatement: _visit_break,
        ContinueStatement: _visit_continue,
        ReturnStatement: _visit_return,
        TryCatchStatement: _visit_try_catch,
        SwitchStatement: _visit_switch,
    }

    # ------------------------------------------------------------------
    # expresiones: solo se recorren para encontrar 'this' fuera de contexto y
    # para no dejar sub-arboles sin visitar. persona 2 hace el chequeo de tipos real.
    # ------------------------------------------------------------------

    def _visit_expr(self, node) -> None:
        if node is None:
            return
        if isinstance(node, ThisExpr):
            if self.symbols.current.enclosing_class() is None:
                self._diag.error("CPS-040", node.line, node.column)
            return
        if isinstance(node, Assignment):
            self._visit_expr(node.target)
            self._visit_expr(node.value)
        elif isinstance(node, BinaryOp):
            self._visit_expr(node.left)
            self._visit_expr(node.right)
        elif isinstance(node, UnaryOp):
            self._visit_expr(node.operand)
        elif isinstance(node, Ternary):
            self._visit_expr(node.condition)
            self._visit_expr(node.then_expr)
            self._visit_expr(node.else_expr)
        elif isinstance(node, Call):
            self._visit_expr(node.callee)
            for arg in node.args:
                self._visit_expr(arg)
        elif isinstance(node, IndexAccess):
            self._visit_expr(node.collection)
            self._visit_expr(node.index)
        elif isinstance(node, PropertyAccess):
            self._visit_expr(node.obj)
        elif isinstance(node, NewExpr):
            if node.class_name not in self._classes:
                self._diag.error("CPS-023", node.line, node.column, detail=node.class_name)
            for arg in node.args:
                self._visit_expr(arg)
        elif hasattr(node, "elements"):  # ArrayLiteral
            for el in node.elements:
                self._visit_expr(el)
        # Identifier / IntegerLiteral / StringLiteral / BooleanLiteral / NullLiteral:
        # nada que resolver en persona 1, el lookup de identificadores en expresiones
        # es responsabilidad de persona 2 (frontera explicita, ver CPS-023 en el catalogo)


def collect_symbols(program: Program, diagnostics: DiagnosticBag) -> SymbolTable:
    """punto de entrada del modulo: arma y corre el collector, devuelve la tabla resultante."""
    collector = SymbolCollector(diagnostics)
    return collector.collect(program)
