"""
modelo de runtime: le asigna a cada simbolo donde va a vivir en tiempo de ejecucion y
arma los registros de activacion y los layouts de clase. corre una sola vez, despues de
una semantica sin errores, y escribe sus resultados en la misma tabla de simbolos (no
crea otra).

  prepare(result) -> RuntimeLayout

decisiones (detalladas en docs/INTERMEDIATE_CODE.md):
- globales: toda variable que no vive dentro de una funcion, en preorden de scopes.
- frame: [this] [params] [locales]; locales en preorden de los scopes de la funcion,
  sin entrar a funciones anidadas y sin reusar slots entre bloques hermanos.
- static link: solo si la funcion (o algo que llama, o algo anidado en ella) necesita
  llegar al frame de una funcion que la encierra.
- clases: campos heredados primero; un override reusa el slot del padre; el
  constructor no tiene slot de despacho (se llama directo) y, si la clase no declara
  uno, su layout apunta al del ancestro mas cercano.
- warnings no bloquean: el pdf corta la generacion por ERRORES.
"""
from __future__ import annotations

from types import MappingProxyType

from compiler.ast_nodes import Identifier, ThisExpr
from compiler.extended_semantics import SemanticResult
from compiler.ir.label_manager import LabelManager
from compiler.runtime.activation_records import (
    ActivationRecord, ClassLayout, FieldEntry, FrameSlot, MethodEntry,
)
from compiler.runtime.scoped_visitor import ScopedVisitor, all_functions, index_scopes
from compiler.runtime.storage import FRAME_KINDS, StorageKind, StorageRef
from compiler.scopes import Scope, ScopeKind, SymbolTable
from compiler.symbols import THIS_NAME, ClassSymbol, FunctionSymbol, Symbol, VariableSymbol


def require_semantic_success(result: SemanticResult) -> None:
    """regla unica para todo el ir: con cualquier error previo no se genera nada."""
    if result.ast is None or result.has_errors:
        raise ValueError("no se genera ir: el analisis tiene errores lexicos, sintacticos o semanticos")


class RuntimeLayout:
    """resultado de prepare(). solo lectura: los cambios ya quedaron en los simbolos."""

    def __init__(
        self,
        labels: LabelManager,
        globals_count: int,
        functions: list[FunctionSymbol],
        parents: dict[int, FunctionSymbol | None],
        class_layouts: dict[str, ClassLayout],
        index: dict[tuple[int, int], Scope],
    ) -> None:
        self._labels = labels
        self._globals_count = globals_count
        self._functions = tuple(functions)
        self._parents = parents
        self._class_layouts = MappingProxyType(dict(class_layouts))
        self._records = MappingProxyType({fn.label: fn.activation_record for fn in functions})
        self._index = index

    @property
    def labels(self) -> LabelManager:
        return self._labels

    @property
    def globals_count(self) -> int:
        return self._globals_count

    @property
    def functions(self) -> tuple[FunctionSymbol, ...]:
        return self._functions

    @property
    def records(self):
        return self._records

    @property
    def class_layouts(self):
        return self._class_layouts

    def scope_of(self, node) -> Scope | None:
        return self._index.get((node.line, node.column))

    def enclosing_function(self, fn: FunctionSymbol) -> FunctionSymbol | None:
        return self._parents[id(fn)]

    def ref_for(self, symbol: Symbol, from_function: FunctionSymbol | None) -> StorageRef:
        """como se llega a `symbol` desde el codigo de `from_function` (None = codigo global)."""
        if not isinstance(symbol, VariableSymbol) or symbol.storage_kind is None:
            raise ValueError(f"'{symbol.name}' no tiene almacenamiento asignado")
        kind = symbol.storage_kind
        if kind not in FRAME_KINDS:
            return StorageRef(kind, symbol.slot, name=symbol.name)
        hops = self._hops(from_function, symbol.owner)
        if hops == 0:
            return StorageRef(kind, symbol.slot, name=symbol.name)
        if not from_function.activation_record.static_link:
            raise RuntimeError(f"{from_function.label} accede a '{symbol.name}' de otro frame sin static link")
        return StorageRef(StorageKind.NONLOCAL, symbol.slot, lexical_depth=hops, name=symbol.name)

    def link_hops(self, caller: FunctionSymbol | None, callee: FunctionSymbol) -> int | None:
        """
        saltos de static link desde el frame del que llama hasta el frame que hay que
        pasarle al llamado; 0 = el propio frame. None si el llamado no usa static link.
        """
        if not callee.activation_record.static_link:
            return None
        return self._hops(caller, self._parents[id(callee)].label)

    def _hops(self, start: FunctionSymbol | None, owner_label: str | None) -> int:
        fn, hops = start, 0
        while fn is not None:
            if fn.label == owner_label:
                return hops
            fn, hops = self._parents[id(fn)], hops + 1
        raise ValueError(f"el frame de {owner_label} no es visible desde {start.label if start else 'el codigo global'}")


def prepare(result: SemanticResult) -> RuntimeLayout:
    require_semantic_success(result)
    symbols = result.symbols
    index = index_scopes(symbols)
    functions = all_functions(symbols)
    function_of = {id(fn.scope): fn for fn in functions}
    parents = {id(fn): _owning_function(fn.scope.parent, function_of) for fn in functions}

    labels = LabelManager()
    for fn in functions:
        fn.label = labels.function_label(_path(fn, parents))

    owners = _variable_owners(symbols, function_of)
    globals_count = _assign_globals(symbols, owners)
    class_layouts = _assign_class_layouts(symbols)
    links = _static_links(result, owners, parents)
    for fn in functions:
        fn.activation_record = _activation_record(fn, parents, links)

    return RuntimeLayout(labels, globals_count, functions, parents, class_layouts, index)


# ----------------------------------------------------------------------
# helpers de prepare
# ----------------------------------------------------------------------

def _owning_function(scope: Scope | None, function_of: dict[int, FunctionSymbol]) -> FunctionSymbol | None:
    """la funcion cuyo frame contiene a `scope` (None si es codigo global o una clase)."""
    while scope is not None:
        if scope.kind is ScopeKind.FUNCTION:
            fn = function_of.get(id(scope))
            if fn is None:
                raise RuntimeError(f"el scope {scope} no tiene simbolo de funcion")
            return fn
        scope = scope.parent
    return None


def _path(fn: FunctionSymbol, parents: dict[int, FunctionSymbol | None]) -> str:
    if fn.is_method:
        return f"{fn.owner_class}.{fn.name}"
    parent = parents[id(fn)]
    return f"{_path(parent, parents)}.{fn.name}" if parent is not None else fn.name


def _variable_owners(symbols: SymbolTable, function_of: dict[int, FunctionSymbol]) -> dict[int, FunctionSymbol | None]:
    """id(variable) -> funcion duenia de su frame, o None si es global."""
    return {
        id(symbol): _owning_function(scope, function_of)
        for scope in symbols.all_scopes()
        for symbol in scope.symbols.values()
        if isinstance(symbol, VariableSymbol)
    }


def _assign_globals(symbols: SymbolTable, owners: dict[int, FunctionSymbol | None]) -> int:
    slot = 0
    for scope in symbols.all_scopes():
        for symbol in scope.symbols.values():
            if isinstance(symbol, VariableSymbol) and owners[id(symbol)] is None:
                symbol.storage_kind, symbol.slot, symbol.owner = StorageKind.GLOBAL, slot, None
                slot += 1
    return slot


def _assign_class_layouts(symbols: SymbolTable) -> dict[str, ClassLayout]:
    layouts: dict[str, ClassLayout] = {}

    def layout_of(cls: ClassSymbol) -> ClassLayout:
        if cls.name in layouts:
            return layouts[cls.name]
        parent = layout_of(cls.parent) if cls.parent is not None else None
        fields = list(parent.fields) if parent is not None else []
        for field in cls.fields.values():
            field.storage_kind, field.slot, field.owner = StorageKind.FIELD, len(fields), cls.name
            fields.append(FieldEntry(field.slot, field.name, cls.name))
        methods = list(parent.methods) if parent is not None else []
        for method in cls.methods.values():
            if method.is_constructor:
                method.method_slot = None
                continue
            inherited = next((m for m in methods if m.name == method.name), None)
            method.method_slot = inherited.slot if inherited is not None else len(methods)
            entry = MethodEntry(method.name, method.method_slot, method.label, cls.name)
            if inherited is not None:
                methods[method.method_slot] = entry
            else:
                methods.append(entry)
        layout = ClassLayout(
            class_name=cls.name, parent_name=cls.parent.name if cls.parent is not None else None,
            fields=tuple(fields), methods=tuple(methods),
            # sin constructor propio se usa el del ancestro mas cercano (ya resuelto en su layout)
            constructor_label=(
                cls.constructor.label if cls.constructor is not None
                else parent.constructor_label if parent is not None else None
            ),
        )
        cls.layout = layouts[cls.name] = layout
        return layout

    for symbol in symbols.global_scope.symbols.values():
        if isinstance(symbol, ClassSymbol):
            layout_of(symbol)
    return layouts


def _frame_scopes(scope: Scope):
    """el scope de la funcion y sus descendientes, sin meterse en funciones anidadas."""
    yield scope
    for child in scope.children:
        if child.kind is not ScopeKind.FUNCTION:
            yield from _frame_scopes(child)


def _activation_record(
    fn: FunctionSymbol, parents: dict[int, FunctionSymbol | None], links: set[int],
) -> ActivationRecord:
    slots: list[tuple[VariableSymbol, StorageKind]] = []
    this = fn.scope.symbols.get(THIS_NAME)
    if fn.is_method:
        if not isinstance(this, VariableSymbol):
            raise RuntimeError(f"el metodo {fn.label} no tiene 'this' declarado")
        slots.append((this, StorageKind.THIS))
    params = [p for p in fn.params if fn.scope.symbols.get(p.name) is p]
    slots.extend((p, StorageKind.PARAM) for p in params)
    taken = {id(this)} | {id(p) for p in params}
    for scope in _frame_scopes(fn.scope):
        for symbol in scope.symbols.values():
            if isinstance(symbol, VariableSymbol) and id(symbol) not in taken:
                slots.append((symbol, StorageKind.LOCAL))

    frame = []
    for slot, (symbol, kind) in enumerate(slots):
        symbol.storage_kind, symbol.slot, symbol.owner = kind, slot, fn.label
        frame.append(FrameSlot(slot, symbol.name, kind))

    depth, parent = 0, parents[id(fn)]
    while parent is not None:
        depth, parent = depth + 1, parents[id(parent)]
    return ActivationRecord(
        label=fn.label, lexical_depth=depth, static_link=id(fn) in links, is_method=fn.is_method,
        owner_class=fn.owner_class, slots=tuple(frame),
    )


class _CaptureScanner(ScopedVisitor):
    """anota que frames ajenos toca cada funcion y a que funciones llama."""

    def __init__(self, symbols: SymbolTable, owners: dict[int, FunctionSymbol | None]) -> None:
        super().__init__(symbols)
        self._owners = owners
        self.accesses: list[tuple[FunctionSymbol, FunctionSymbol]] = []
        self.calls: list[tuple[FunctionSymbol, FunctionSymbol]] = []

    def _use(self, name: str) -> None:
        current = self.current_function
        if current is None:
            return
        symbol = self.resolve(name)
        if isinstance(symbol, VariableSymbol):
            owner = self._owners.get(id(symbol))
            if owner is not None and owner is not current:
                self.accesses.append((current, owner))
        elif isinstance(symbol, FunctionSymbol):
            self.calls.append((current, symbol))

    def visit_Identifier(self, node: Identifier) -> None:
        self._use(node.name)

    def visit_ThisExpr(self, node: ThisExpr) -> None:
        self._use(THIS_NAME)


def _static_links(
    result: SemanticResult, owners: dict[int, FunctionSymbol | None], parents: dict[int, FunctionSymbol | None],
) -> set[int]:
    scanner = _CaptureScanner(result.symbols, owners)
    scanner.visit(result.ast)
    needs: set[int] = set()

    def mark(start: FunctionSymbol, frame_owner: FunctionSymbol | None) -> bool:
        # toda funcion entre `start` y el dueño del frame tiene que poder subir
        changed, fn = False, start
        while fn is not None and fn is not frame_owner:
            if id(fn) not in needs:
                needs.add(id(fn))
                changed = True
            fn = parents[id(fn)]
        return changed

    for current, owner in scanner.accesses:
        mark(current, owner)
    changed = True
    while changed:
        # llamar a una funcion con static link obliga a conseguirle el frame de su padre
        changed = False
        for current, callee in scanner.calls:
            frame_owner = parents[id(callee)]
            if id(callee) in needs and frame_owner is not current:
                changed |= mark(current, frame_owner)
    return needs
