"""
convierte el parse tree que arma antlr en nuestro ast propio (compiler/ast_nodes.py).

hereda de CompiscriptVisitor y sobreescribe un metodo por regla gramatical. los
problemas raros de la gramatica se resuelven con un puñado de helpers reutilizados
en varios sitios (ver cada uno abajo), en vez de repetir la logica por cada regla.
"""
from __future__ import annotations

from antlr4.tree.Tree import TerminalNodeImpl

from compiler.ast_nodes import (
    ArrayLiteral, Assignment, BinaryOp, Block, BooleanLiteral, BreakStatement, Call,
    ClassDecl, ContinueStatement, DoWhileStatement, ErrorExpr, Expr, ExprStatement,
    ForStatement, ForeachStatement, FunctionDecl, Identifier, IfStatement, IndexAccess,
    IntegerLiteral, NewExpr, Node, NullLiteral, Param, PrintStatement, Program,
    PropertyAccess, ReturnStatement, Stmt, StringLiteral, SwitchCase, SwitchStatement,
    Ternary, ThisExpr, TryCatchStatement, TypeRef, UnaryOp, VarDecl, WhileStatement,
)
from compiler.diagnostics import DiagnosticBag
from compiler.generated import CompiscriptVisitor
from compiler.generated.CompiscriptParser import CompiscriptParser

# nombre del constructor dentro de una clase, unico lugar donde se define esta constante
# (symbol_collector la reusa para no repetir el literal)
CONSTRUCTOR_NAME = "constructor"

# limite defensivo para no cargar en memoria un entero absurdamente largo (hardening,
# nist sp 800-53 si-10). no es un limite del lenguaje, es una advertencia nomas.
_INT64_MAX = 2**63 - 1


def _pos(ctx_or_token) -> tuple[int, int]:
    """
    unico punto que normaliza posiciones: antlr da columna 0-based, todo el proyecto
    usa 1-based porque es lo que espera un humano leyendo un editor.

    ojo: un Token de antlr YA tiene .line (no hay que bajar a .start, eso es para
    ParserRuleContext). se distingue por duck typing con el atributo .line, que
    los ParserRuleContext no tienen directo.
    """
    if hasattr(ctx_or_token, "line"):
        token = ctx_or_token  # ya es un Token
    else:
        token = ctx_or_token.start  # es un ParserRuleContext, bajamos a su token inicial
    return token.line, token.column + 1


class AstBuilder(CompiscriptVisitor):
    """
    un `AstBuilder` por compilacion, no se reusa entre llamadas (evita estado compartido
    accidental). recibe la bolsa de diagnosticos donde reporta lo que encuentra al vuelo
    (literales malformados, asignaciones a destinos invalidos, etc).
    """

    def __init__(self, diagnostics: DiagnosticBag) -> None:
        super().__init__()
        self._diag = diagnostics
        self._in_class_member = False  # para saber si un functionDeclaration es metodo/constructor

    # ------------------------------------------------------------------
    # programa / bloques
    # ------------------------------------------------------------------

    def visitProgram(self, ctx):
        line, col = _pos(ctx)
        statements = [self.visit(s) for s in ctx.statement()]
        return Program(line=line, column=col, statements=statements)

    def visitStatement(self, ctx):
        # statement es puro passthrough a la alternativa real, no hace falta nodo propio
        return self.visit(ctx.getChild(0))

    def visitBlock(self, ctx):
        line, col = _pos(ctx)
        statements = [self.visit(s) for s in ctx.statement()]
        return Block(line=line, column=col, statements=statements)

    # ------------------------------------------------------------------
    # declaraciones de variables/constantes
    # ------------------------------------------------------------------

    def visitVariableDeclaration(self, ctx):
        line, col = _pos(ctx)
        name = ctx.Identifier().getText()
        declared_type = self._build_type(ctx.typeAnnotation()) if ctx.typeAnnotation() else None
        initializer = self.visit(ctx.initializer().expression()) if ctx.initializer() else None
        # 'let' o 'var' es el primer hijo terminal del contexto
        keyword = ctx.getChild(0).getText()
        return VarDecl(
            line=line, column=col, name=name, keyword=keyword, is_const=False,
            declared_type=declared_type, initializer=initializer,
        )

    def visitConstantDeclaration(self, ctx):
        line, col = _pos(ctx)
        name = ctx.Identifier().getText()
        declared_type = self._build_type(ctx.typeAnnotation()) if ctx.typeAnnotation() else None
        # const siempre trae '=' expression segun la gramatica, no es opcional aca
        initializer = self.visit(ctx.expression())
        return VarDecl(
            line=line, column=col, name=name, keyword="const", is_const=True,
            declared_type=declared_type, initializer=initializer,
        )

    # ------------------------------------------------------------------
    # asignacion como statement (2 alternativas ambiguas en un solo contexto)
    # ------------------------------------------------------------------

    def visitAssignment(self, ctx):
        """
        AssignmentContext no distingue sus dos alternativas por tipo de nodo (a diferencia
        de assignmentExpr que si usa labels). hay que mirar cuantas expression() trae:
        1 expression -> 'Identifier = expr'
        2 expression -> 'expr . Identifier = expr'  (la primera es el objeto, la segunda el valor)
        """
        line, col = _pos(ctx)
        exprs = ctx.expression()
        if len(exprs) == 1:
            target = Identifier(line=line, column=col, name=ctx.Identifier().getText())
            value = self.visit(exprs[0])
        else:
            obj = self.visit(exprs[0])
            prop_name = ctx.Identifier().getText()
            # la posicion del PropertyAccess apunta al identificador de la propiedad, no al objeto
            prop_line, prop_col = _pos(ctx.Identifier().getSymbol())
            target = PropertyAccess(line=prop_line, column=prop_col, obj=obj, name=prop_name)
            value = self.visit(exprs[1])
        assignment = self._build_assignment(line, col, target, value)
        return ExprStatement(line=assignment.line, column=assignment.column, expression=assignment)

    def visitExpressionStatement(self, ctx):
        line, col = _pos(ctx)
        expr = self.visit(ctx.expression())
        return ExprStatement(line=line, column=col, expression=expr)

    def visitPrintStatement(self, ctx):
        line, col = _pos(ctx)
        return PrintStatement(line=line, column=col, expression=self.visit(ctx.expression()))

    def _build_assignment(self, line: int, column: int, target: Expr, value: Expr) -> Assignment:
        """
        un solo constructor de Assignment para las 4 rutas gramaticales (2 de statement,
        2 de expresion). valida que el target sea algo asignable de verdad.
        """
        if not isinstance(target, (Identifier, PropertyAccess, IndexAccess)):
            t_line, t_col = target.line, target.column
            self._diag.error("CPS-010", t_line, t_col, detail=type(target).__name__)
        return Assignment(line=line, column=column, target=target, value=value)

    # ------------------------------------------------------------------
    # control de flujo
    # ------------------------------------------------------------------

    def visitIfStatement(self, ctx):
        line, col = _pos(ctx)
        condition = self.visit(ctx.expression())
        blocks = ctx.block()
        then_block = self.visit(blocks[0])
        else_block = self.visit(blocks[1]) if len(blocks) > 1 else None
        return IfStatement(line=line, column=col, condition=condition, then_block=then_block, else_block=else_block)

    def visitWhileStatement(self, ctx):
        line, col = _pos(ctx)
        return WhileStatement(line=line, column=col, condition=self.visit(ctx.expression()), body=self.visit(ctx.block()))

    def visitDoWhileStatement(self, ctx):
        line, col = _pos(ctx)
        return DoWhileStatement(line=line, column=col, body=self.visit(ctx.block()), condition=self.visit(ctx.expression()))

    def visitForStatement(self, ctx):
        line, col = _pos(ctx)
        init = None
        if ctx.variableDeclaration():
            init = self.visit(ctx.variableDeclaration())
        elif ctx.assignment():
            # visitAssignment devuelve un ExprStatement envolviendo la Assignment, sacamos la de adentro
            init = self.visit(ctx.assignment()).expression
        exprs = ctx.expression()
        # segun cuantos () esten presentes, la condicion y el update pueden faltar. la gramatica es
        # 'for' '(' (varDecl|assignment|';') expression? ';' expression? ')' block
        condition = self.visit(exprs[0]) if len(exprs) >= 1 else None
        update = self.visit(exprs[1]) if len(exprs) >= 2 else None
        body = self.visit(ctx.block())
        return ForStatement(line=line, column=col, init=init, condition=condition, update=update, body=body)

    def visitForeachStatement(self, ctx):
        line, col = _pos(ctx)
        var_name = ctx.Identifier().getText()
        iterable = self.visit(ctx.expression())
        body = self.visit(ctx.block())
        return ForeachStatement(line=line, column=col, var_name=var_name, iterable=iterable, body=body)

    def visitBreakStatement(self, ctx):
        line, col = _pos(ctx)
        return BreakStatement(line=line, column=col)

    def visitContinueStatement(self, ctx):
        line, col = _pos(ctx)
        return ContinueStatement(line=line, column=col)

    def visitReturnStatement(self, ctx):
        line, col = _pos(ctx)
        value = self.visit(ctx.expression()) if ctx.expression() else None
        return ReturnStatement(line=line, column=col, value=value)

    def visitTryCatchStatement(self, ctx):
        line, col = _pos(ctx)
        blocks = ctx.block()
        try_block = self.visit(blocks[0])
        catch_block = self.visit(blocks[1])
        exception_name = ctx.Identifier().getText()
        return TryCatchStatement(line=line, column=col, try_block=try_block, exception_name=exception_name, catch_block=catch_block)

    def visitSwitchStatement(self, ctx):
        line, col = _pos(ctx)
        subject = self.visit(ctx.expression())
        cases = [self.visit(c) for c in ctx.switchCase()]
        default_statements = None
        if ctx.defaultCase():
            default_statements = [self.visit(s) for s in ctx.defaultCase().statement()]
        return SwitchStatement(line=line, column=col, subject=subject, cases=cases, default_statements=default_statements)

    def visitSwitchCase(self, ctx):
        line, col = _pos(ctx)
        value = self.visit(ctx.expression())
        statements = [self.visit(s) for s in ctx.statement()]
        return SwitchCase(line=line, column=col, value=value, statements=statements)

    # ------------------------------------------------------------------
    # funciones y clases
    # ------------------------------------------------------------------

    def visitFunctionDeclaration(self, ctx):
        line, col = _pos(ctx)
        name = ctx.Identifier().getText()
        params = []
        if ctx.parameters():
            params = [self.visit(p) for p in ctx.parameters().parameter()]
        return_type = self._build_type(ctx.type_()) if ctx.type_() else None
        body = self.visit(ctx.block())
        # constructor se determina por nombre Y por estar dentro de un classMember,
        # no por nombre solo (una funcion top-level llamada "constructor" es normal)
        is_constructor = self._in_class_member and name == CONSTRUCTOR_NAME
        return FunctionDecl(
            line=line, column=col, name=name, params=params, return_type=return_type,
            body=body, is_constructor=is_constructor, is_method=self._in_class_member,
        )

    def visitParameter(self, ctx):
        line, col = _pos(ctx)
        name = ctx.Identifier().getText()
        declared_type = self._build_type(ctx.type_()) if ctx.type_() else None
        return Param(line=line, column=col, name=name, declared_type=declared_type)

    def visitClassDeclaration(self, ctx):
        line, col = _pos(ctx)
        identifiers = ctx.Identifier()
        name = identifiers[0].getText()
        parent_name = identifiers[1].getText() if len(identifiers) > 1 else None
        prev = self._in_class_member
        self._in_class_member = True
        try:
            members = [self.visit(m) for m in ctx.classMember()]
        finally:
            self._in_class_member = prev
        return ClassDecl(line=line, column=col, name=name, parent_name=parent_name, members=members)

    def visitClassMember(self, ctx):
        # classMember: functionDeclaration | variableDeclaration | constantDeclaration
        return self.visit(ctx.getChild(0))

    # ------------------------------------------------------------------
    # expresiones: fachada expression -> assignmentExpr
    # ------------------------------------------------------------------

    def visitExpression(self, ctx):
        return self.visit(ctx.assignmentExpr())

    def visitExprNoAssign(self, ctx):
        return self.visit(ctx.conditionalExpr())

    def visitAssignExpr(self, ctx):
        line, col = _pos(ctx)
        target = self.visit(ctx.leftHandSide())
        value = self.visit(ctx.assignmentExpr())
        return self._build_assignment(line, col, target, value)

    def visitPropertyAssignExpr(self, ctx):
        line, col = _pos(ctx)
        obj = self.visit(ctx.leftHandSide())
        prop_name = ctx.Identifier().getText()
        prop_line, prop_col = _pos(ctx.Identifier().getSymbol())
        target = PropertyAccess(line=prop_line, column=prop_col, obj=obj, name=prop_name)
        value = self.visit(ctx.assignmentExpr())
        return self._build_assignment(line, col, target, value)

    def visitTernaryExpr(self, ctx):
        exprs = ctx.expression()
        if not exprs:
            # sin '?' no hay ternario real, es solo passthrough al logicalOrExpr
            return self.visit(ctx.logicalOrExpr())
        line, col = _pos(ctx)
        condition = self.visit(ctx.logicalOrExpr())
        then_expr = self.visit(exprs[0])
        else_expr = self.visit(exprs[1])
        return Ternary(line=line, column=col, condition=condition, then_expr=then_expr, else_expr=else_expr)

    # ------------------------------------------------------------------
    # reglas binarias planas: una sola funcion de plegado para las 6 (dry)
    # ------------------------------------------------------------------

    def _fold_binary(self, ctx, operand_accessor_name: str):
        """
        pliega 'operando (OP operando)*' en BinaryOp izquierda-asociativo. sirve para
        logicalOrExpr, logicalAndExpr, equalityExpr, relationalExpr, additiveExpr y
        multiplicativeExpr: todas tienen la misma forma, solo cambia el accessor del operando.
        """
        get_operand = getattr(ctx, operand_accessor_name)
        operands = get_operand()
        node = self.visit(operands[0])
        if len(operands) == 1:
            return node
        # los operadores son los TerminalNodeImpl intercalados entre los operandos
        operators = [c for c in ctx.children if isinstance(c, TerminalNodeImpl)]
        for i, op_token in enumerate(operators):
            right = self.visit(operands[i + 1])
            line, col = _pos(op_token.getSymbol())
            node = BinaryOp(line=line, column=col, op=op_token.getText(), left=node, right=right)
        return node

    def visitLogicalOrExpr(self, ctx):
        return self._fold_binary(ctx, "logicalAndExpr")

    def visitLogicalAndExpr(self, ctx):
        return self._fold_binary(ctx, "equalityExpr")

    def visitEqualityExpr(self, ctx):
        return self._fold_binary(ctx, "relationalExpr")

    def visitRelationalExpr(self, ctx):
        return self._fold_binary(ctx, "additiveExpr")

    def visitAdditiveExpr(self, ctx):
        return self._fold_binary(ctx, "multiplicativeExpr")

    def visitMultiplicativeExpr(self, ctx):
        return self._fold_binary(ctx, "unaryExpr")

    def visitUnaryExpr(self, ctx):
        if ctx.unaryExpr() is not None:
            line, col = _pos(ctx)
            op = ctx.getChild(0).getText()  # '-' o '!'
            operand = self.visit(ctx.unaryExpr())
            return UnaryOp(line=line, column=col, op=op, operand=operand)
        return self.visit(ctx.primaryExpr())

    def visitPrimaryExpr(self, ctx):
        if ctx.literalExpr() is not None:
            return self.visit(ctx.literalExpr())
        if ctx.leftHandSide() is not None:
            return self.visit(ctx.leftHandSide())
        # '(' expression ')'
        return self.visit(ctx.expression())

    # ------------------------------------------------------------------
    # literales
    # ------------------------------------------------------------------

    def visitLiteralExpr(self, ctx):
        if ctx.arrayLiteral() is not None:
            return self.visit(ctx.arrayLiteral())
        if ctx.Literal() is not None:
            return self._classify_literal(ctx.Literal())
        line, col = _pos(ctx)
        text = ctx.getText()
        if text == "null":
            return NullLiteral(line=line, column=col)
        if text == "true":
            return BooleanLiteral(line=line, column=col, value=True)
        if text == "false":
            return BooleanLiteral(line=line, column=col, value=False)
        # no deberia pasar con esta gramatica, hardening por si acaso
        self._diag.error("CPS-003", line, col, detail=text)
        return ErrorExpr(line=line, column=col)

    def _classify_literal(self, literal_token) -> Expr:
        """
        el token 'Literal' es unificado (IntegerLiteral | StringLiteral), antlr no
        distingue el subtipo. las dos reglas del lexer son disjuntas por construccion:
        StringLiteral siempre arranca con comilla, IntegerLiteral siempre con digito.
        se mira el texto crudo, no hay otra fuente de verdad posible sin tocar la gramatica.
        """
        text = literal_token.getText()
        line, col = _pos(literal_token.getSymbol())
        if text.startswith('"'):
            # la gramatica no define escapes (~["\r\n]*), asi que no se interpreta \n ni \\
            value = text[1:-1]
            return StringLiteral(line=line, column=col, value=value)
        if text and text[0].isdigit():
            int_value = int(text, 10)
            if abs(int_value) > _INT64_MAX:
                self._diag.warning("CPS-002", line, col, detail=text)
            return IntegerLiteral(line=line, column=col, value=int_value)
        # fail-closed: con la gramatica actual esto no deberia ocurrir nunca
        self._diag.error("CPS-003", line, col, detail=text)
        return ErrorExpr(line=line, column=col)

    def visitArrayLiteral(self, ctx):
        line, col = _pos(ctx)
        elements = [self.visit(e) for e in ctx.expression()]
        return ArrayLiteral(line=line, column=col, elements=elements)

    # ------------------------------------------------------------------
    # leftHandSide: fold izquierdo de primaryAtom (suffixOp)*
    # ------------------------------------------------------------------

    def visitLeftHandSide(self, ctx):
        node = self.visit(ctx.primaryAtom())
        for suffix_ctx in ctx.suffixOp():
            node = self._apply_suffix(node, suffix_ctx)
        return node

    def _apply_suffix(self, base: Expr, suffix_ctx) -> Expr:
        """
        cada sufijo envuelve al acumulador. la posicion del nodo resultante es la del
        TOKEN DEL SUFIJO (el '.', el '[' o el '('), no la del nodo base -- asi un error
        de "propiedad no existe" apunta al '.', que es donde el usuario tiene que mirar.
        """
        line, col = _pos(suffix_ctx)
        # los tres tipos vienen distinguidos por clase (labels de suffixOp), a diferencia
        # de assignment que es ambiguo -- aca si podemos usar isinstance con seguridad
        if isinstance(suffix_ctx, CompiscriptParser.CallExprContext):
            args = [self.visit(a) for a in suffix_ctx.arguments().expression()] if suffix_ctx.arguments() else []
            return Call(line=line, column=col, callee=base, args=args)
        if isinstance(suffix_ctx, CompiscriptParser.IndexExprContext):
            index = self.visit(suffix_ctx.expression())
            return IndexAccess(line=line, column=col, collection=base, index=index)
        if isinstance(suffix_ctx, CompiscriptParser.PropertyAccessExprContext):
            name = suffix_ctx.Identifier().getText()
            return PropertyAccess(line=line, column=col, obj=base, name=name)
        # defensivo: no deberia alcanzarse con la gramatica actual
        self._diag.error("CPS-003", line, col, detail="sufijo desconocido")
        return ErrorExpr(line=line, column=col)

    def visitIdentifierExpr(self, ctx):
        line, col = _pos(ctx)
        return Identifier(line=line, column=col, name=ctx.Identifier().getText())

    def visitNewExpr(self, ctx):
        line, col = _pos(ctx)
        class_name = ctx.Identifier().getText()
        args = [self.visit(a) for a in ctx.arguments().expression()] if ctx.arguments() else []
        return NewExpr(line=line, column=col, class_name=class_name, args=args)

    def visitThisExpr(self, ctx):
        line, col = _pos(ctx)
        return ThisExpr(line=line, column=col)

    # ------------------------------------------------------------------
    # tipos (TypeRef, no confundir con types.Type)
    # ------------------------------------------------------------------

    def _build_type(self, ctx) -> TypeRef:
        """
        ctx puede ser un TypeAnnotationContext (':' type) o un TypeContext directo
        (por ejemplo el de retorno de funcion). se normaliza antes de seguir.
        """
        type_ctx = ctx.type_() if hasattr(ctx, "type_") else ctx
        line, col = _pos(type_ctx)
        base_name = type_ctx.baseType().getText()
        # contar los '[' terminales, no asumir la forma de los hijos por posicion
        array_dimensions = sum(1 for c in type_ctx.children if isinstance(c, TerminalNodeImpl) and c.getText() == "[")
        return TypeRef(line=line, column=col, base_name=base_name, array_dimensions=array_dimensions)
