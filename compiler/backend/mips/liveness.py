"""
analisis de vida de temporales sobre el grafo de flujo de UNA unidad del ir (el codigo
global o una funcion). sirve para que el backend libere un temporal apenas deja de servir:
un temporal muerto no se vuelve a guardar en su home en cada etiqueta, salto o llamada.

  dead = dead_temps(instructions)   # dead[i] = Temps que mueren en la instruccion i (nadie los vuelve a leer)

clasico analisis hacia atras: bloques basicos (empiezan en una LABEL o despues de un salto),
use/def por bloque e iteracion hasta punto fijo de
    out[B] = union in[S] de los sucesores;   in[B] = use[B] | (out[B] - def[B]).
el grafo sale de las etiquetas del propio ir: GOTO, IF_TRUE/IF_FALSE (con caida al siguiente)
y TRY_BEGIN (que tambien puede llegar a su manejador). RETURN y FUNC_END no tienen sucesores.

es conservador a proposito:
- un opcode que no conoce trata su resultado como lectura (asi el temporal vive mas, nunca menos);
- en una unidad con try, todo temporal vivo al entrar a un manejador queda vivo en toda la
  unidad: un error puede saltar al catch desde cualquier instruccion del bloque protegido.
solo mira temporales: variables y constantes no se reparten registros.
"""
from __future__ import annotations

from compiler.ir.model import TACInstruction, Temp
from compiler.ir.opcodes import Opcode

_Key = tuple[int, int]

# opcodes cuyo `result` es un destino que se escribe. en ARR_SET y SET_FIELD el `result` es
# el arreglo/objeto que se modifica: se LEE.
_WRITES_RESULT = frozenset({
    Opcode.MOV, Opcode.BIN, Opcode.UN, Opcode.CALL, Opcode.NEW_ARR, Opcode.ARR_GET, Opcode.LEN,
    Opcode.NEW_OBJ, Opcode.GET_FIELD, Opcode.CALL_METHOD, Opcode.CATCH,
})
_JUMPS = frozenset({Opcode.GOTO, Opcode.IF_TRUE, Opcode.IF_FALSE})
_NO_FALLTHROUGH = frozenset({Opcode.GOTO, Opcode.RETURN, Opcode.FUNC_END})


def _key(temp: Temp) -> _Key:
    return (temp.unit, temp.index)


def uses_and_defs(instr: TACInstruction) -> tuple[set[_Key], set[_Key]]:
    """temporales que la instruccion lee y que escribe."""
    uses = {_key(op) for op in (instr.arg1, instr.arg2) if isinstance(op, Temp)}
    defs: set[_Key] = set()
    if isinstance(instr.result, Temp):
        (defs if instr.opcode in _WRITES_RESULT else uses).add(_key(instr.result))
    return uses, defs


def _jump_label(instr: TACInstruction) -> str | None:
    if instr.opcode in (Opcode.GOTO, Opcode.TRY_BEGIN):
        return instr.arg1.name
    if instr.opcode in (Opcode.IF_TRUE, Opcode.IF_FALSE):
        return instr.arg2.name
    return None


def dead_temps(instructions: tuple[TACInstruction, ...]) -> list[frozenset[_Key]]:
    count = len(instructions)
    if not count:
        return []

    # bloques basicos
    leaders = {0}
    for i, instr in enumerate(instructions):
        if instr.opcode is Opcode.LABEL:
            leaders.add(i)
        if (instr.opcode in _JUMPS or instr.opcode in _NO_FALLTHROUGH) and i + 1 < count:
            leaders.add(i + 1)
    starts = sorted(leaders)
    ends = starts[1:] + [count]
    block_of_label = {
        instructions[s].arg1.name: b for b, s in enumerate(starts) if instructions[s].opcode is Opcode.LABEL
    }

    successors: list[set[int]] = []
    handler_blocks: set[int] = set()
    for b, (start, end) in enumerate(zip(starts, ends)):
        succ: set[int] = set()
        for instr in instructions[start:end]:
            label = _jump_label(instr)
            if label is not None and label in block_of_label:
                succ.add(block_of_label[label])
                if instr.opcode is Opcode.TRY_BEGIN:
                    handler_blocks.add(block_of_label[label])
        last = instructions[end - 1]
        if last.opcode not in _NO_FALLTHROUGH and b + 1 < len(starts):
            succ.add(b + 1)
        successors.append(succ)

    # use / def por bloque
    block_use: list[set[_Key]] = []
    block_def: list[set[_Key]] = []
    for start, end in zip(starts, ends):
        use: set[_Key] = set()
        define: set[_Key] = set()
        for instr in instructions[start:end]:
            u, d = uses_and_defs(instr)
            use |= u - define
            define |= d
        block_use.append(use)
        block_def.append(define)

    # punto fijo
    live_in: list[set[_Key]] = [set() for _ in starts]
    live_out: list[set[_Key]] = [set() for _ in starts]
    changed = True
    while changed:
        changed = False
        for b in reversed(range(len(starts))):
            out = set().union(*(live_in[s] for s in successors[b])) if successors[b] else set()
            new_in = block_use[b] | (out - block_def[b])
            if out != live_out[b] or new_in != live_in[b]:
                live_out[b], live_in[b] = out, new_in
                changed = True

    # lo que esta vivo al entrar a un catch no puede morir en ningun punto de la unidad
    pinned: set[_Key] = set().union(*(live_in[h] for h in handler_blocks)) if handler_blocks else set()

    # recorrido hacia atras dentro de cada bloque
    dead: list[tuple[Temp, ...]] = [()] * count
    for b, (start, end) in enumerate(zip(starts, ends)):
        live = set(live_out[b])
        for i in reversed(range(start, end)):
            uses, defs = uses_and_defs(instructions[i])
            dying = (uses | defs) - live - pinned
            dead[i] = _temps_of(instructions[i], dying)
            live = (live - defs) | uses
    return dead


def _temps_of(instr: TACInstruction, keys: set[_Key]) -> tuple[Temp, ...]:
    """los Temp de la instruccion con esas claves, sin repetir y en orden de indice."""
    found = {}
    for op in (instr.result, instr.arg1, instr.arg2):
        if isinstance(op, Temp) and _key(op) in keys:
            found.setdefault(_key(op), op)
    return tuple(found[k] for k in sorted(found))
