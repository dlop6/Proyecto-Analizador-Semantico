# Backend MIPS — base compartida

Contrato de la base del backend (`compiler/backend/mips/`): modelo de ensamblador, ABI, frames, registros y registros de activación. Los lowerers TAC→MIPS se construyen **encima** de esto y no escriben ensamblador a mano. Los ejemplos de este documento los genera el código real; `tests/mips_base/test_docs.py` falla si dejan de coincidir.

## 1. Target y cómo se ensambla

- **MARS 4.5** (`tools/Mars4_5.jar`, release `v.4.5.1` de `dpetersanderson/MARS`, SHA-256 `ac340b676ba2b62246b9df77e62f81ad4447bcfd329ab539716bcd09950b7096`). Se baja y verifica con `tools/fetch_mars.sh` o `tools/fetch_mars.ps1`.
- Ejecución por consola: `java -Djava.awt.headless=true -jar tools/Mars4_5.jar nc programa.asm <pasos> [$reg ...]`.
- **Delayed branching apagado** (default de MARS). La ejecución empieza en la **primera instrucción de `.text`**, por eso `main` va primero (el builder lo exige).
- MARS devuelve código de salida 0 aunque falle: los errores se detectan en la salida (`Error in ... line n`, `Runtime exception`, `maximum step limit`). Ver `tests/mips_base/mars_runner.py`.
- `div` por cero hace *trap* en MARS: el código generado tiene que revisar el divisor antes (`rt_check_divisor`).

## 2. Registros

| Registros | Uso |
|---|---|
| `$t0-$t7` | los reparte el `RegisterAllocator` a los temporales del IR |
| `$t8-$t9` | scratch del backend: constantes, variables, static link, despacho (`$t9` = puntero al método) |
| `$v0` | valor de retorno / mensaje de error |
| `$v1` | estado de retorno: `0` normal, `1` error |
| `$a0` | argumento de syscalls (impresión) |
| `$sp $fp $ra` | pila, frame y retorno |
| `$at` | reservado para el ensamblador (pseudo-instrucciones como `lw label+off`) |
| `$s0-$s7` | no se usan |

Todos los `$t` son *caller-saved*: antes de una llamada se guardan los temporales sucios en su home y después de la llamada ningún registro se considera válido.

## 3. ABI y convención de pila

Una sola convención para todo: funciones, métodos, constructores y helpers de runtime.

- Palabra de 4 bytes. `true = 1`, `false = 0`, `null = 0`. Un string es un puntero a `.asciiz`.
- El que llama reserva el bloque de argumentos, lo llena **en orden** y lo limpia después del `jal`.
- **Orden de argumentos:** static link (si el llamado lo usa), `this` (métodos y constructores), explícitos.
- Retorno: `$v0` = valor, `$v1 = 0`. Error: `$v1 = 1` y el mensaje en `$v0`.

```
mayor dirección
| arg n-1        |  8+4(n-1)($fp)
| arg 0          |  8($fp)
| $ra guardado   |  4($fp)
| $fp viejo      |  0($fp)   <- $fp
| locales        |  -4($fp), -8($fp)...
| home de temps  |
| args pendientes|
menor dirección  <- $sp
```

## 4. Registro de activación: prólogo y epílogo

`FramePlanner.plan(función, layout)` da el `FramePlan`: `size`, `static_link`, `receiver`, `param_offsets`, `local_offsets`, `temp_offsets`, `arg_stash`, `incoming_bytes`. Las locales se ponen en cero en el prólogo porque el IR nunca las inicializa. Cada función tiene **una sola salida** (`<fn>_exit`), que usan `return` y la propagación de errores.

```
fn_f:
    addi $sp, $sp, -8
    sw $ra, 4($sp)
    sw $fp, 0($sp)
    move $fp, $sp
    addi $sp, $sp, -8
    sw $zero, -4($fp)    # local en cero
    li $v0, 0
    li $v1, 0
fn_f_exit:
    lw $ra, 4($fp)
    move $sp, $fp
    lw $fp, 0($sp)
    addi $sp, $sp, 8
    jr $ra
```

El código global (`main`) no tiene `FUNC_BEGIN` en el IR: se le arma un frame (`move $fp, $sp`) para sus temporales y argumentos pendientes; sus variables viven en `__globals`.

## 5. Llamadas y argumentos pendientes

El IR emite los `ARG` sueltos y los consume un `CALL` más adelante, incluso con llamadas anidadas (`f(1, g(2))` → `ARG 1; ARG 2; CALL g; ARG t; CALL f`) y con temporales que se reusan entre el `ARG` y su `CALL`. Por eso cada `ARG` se guarda **apenas se ejecuta** en una casilla del frame (`arg_stash`) y el `CALL` copia los últimos `argc` a la pila. El tamaño del área es la profundidad máxima de `ARG` pendientes (`max_pending_args`). `print(f(1, 2))`:

```
main:
    move $fp, $sp
    addi $sp, $sp, -12
    li $t8, 1
    sw $t8, -8($fp)    # arg 0
    li $t8, 2
    sw $t8, -12($fp)    # arg 1
    addi $sp, $sp, -8
    lw $t8, -8($fp)
    sw $t8, 0($sp)
    lw $t8, -12($fp)
    sw $t8, 4($sp)
    jal fn_f
    addi $sp, $sp, 8
    move $t0, $v0
    sw $t0, -4($fp)    # guarda t0
    bne $v1, $zero, main_error
```

- `CALL_METHOD`: el receptor no es un `ARG` (no entra en `argc`); se pasa como `this`. Despacho: `lw $t9, 0(recv)` (vtable) y `lw $t9, 4*slot($t9)`, luego `jalr $t9`. El receptor tiene que estar chequeado contra null antes.
- Constructores: `this` sí es el primer `ARG` del IR (`argc = n + 1`) y se llaman directo (`constructor_label`, que ya resuelve el heredado).

## 6. Static link

Solo lo reciben las funciones que lo necesitan (`ActivationRecord.static_link`), siempre como primer argumento (`8($fp)`). El metadata `link=k` del `CALL` dice cuántos saltos dar desde el frame del que llama (0 = el propio):

```
    move $t8, $fp    # static link = este frame
    sw $t8, 0($sp)
```

Un `StorageRef` NONLOCAL con `lexical_depth = d` sigue `d` links y lee el slot en el frame dueño (su offset sale del `FramePlan` de esa función):

```
    lw $t8, 8($fp)    # static link
    lw $t8, 8($t8)
```

## 7. Variables

| `StorageRef` | Dirección |
|---|---|
| `GLOBAL` | `__globals + 4*slot` (`.space` en `.data`, arranca en cero) |
| `THIS`, `PARAM` | `offset($fp)` positivo (argumento entrante) |
| `LOCAL` | `offset($fp)` negativo |
| `NONLOCAL` | static link × `lexical_depth`, luego el offset del slot en el frame dueño |
| `FIELD` | `4 + 4*slot` desde el puntero al objeto (`load_field` / `store_field`) |

El `StorageRef` no trae tipo: `RuntimeLayout.storage_type(ref, from_function)` lo da para globales y variables de frame (hace falta para imprimir, concatenar y comparar strings). El tipo de un campo lo da el temporal del `GET_FIELD`/`SET_FIELD`.

## 8. Selección de registros

`RegisterAllocator` (mapeo con el PDF):

| PDF | API |
|---|---|
| `getReg` | `get_reg(temp, load=True)`: `load=False` para un destino (no carga nada) |
| `markDirty` | `mark_dirty(temp)` después de escribir el registro |
| `release` | `release(temp)`: libera sin guardar; liberar dos veces falla |
| `flushLive` | `flush_live()`: guarda los sucios en su home, quedan cacheados limpios |
| `invalidateCallerSaved` | `invalidate_caller_saved()`: olvida todo; exige no tener sucios |
| `reset` | `reset(plan)`: función nueva, estado limpio |

- Solo se cachean temporales (clave `(unidad, índice)`; el tipo no cuenta, `t0` puede ser bool y después int). Constantes y variables se cargan a `$t8/$t9` en cada instrucción.
- Sin libres: **spill LRU** determinista; si el expulsado está sucio se guarda en su home. Contadores `spills` y `reloads`.
- `instruction()` (adición al contrato): fija los registros que la instrucción en curso ya pidió, para que el segundo operando no expulse al primero. Cada instrucción del IR se baja dentro de un `with allocator.instruction():`.
- **Límites de bloque** (los aplica `ActivationEmitter`): `mark_label` hace flush antes de la etiqueta e invalida después; `emit_branch`, `emit_error_check` y las llamadas hacen flush antes. El home del temporal es siempre la fuente de verdad entre bloques.

## 9. Datos

- Strings: `.asciiz` deduplicados por contenido (`str_<n>`, `add_string`). Solo ASCII imprimible más `\n \t \r \" \\`; otro carácter es error de compilación.
- Arreglo: `[longitud][elementos...]`, elementos desde el offset 4 (`array_size(n) = 4 + 4n`).
- Objeto: `[vtable][campos...]`, campos desde el offset 4 (`field_offset(slot)`, `object_size(campos)`). Heredados primero (sale de `ClassLayout`).
- Vtable: `vt_<Clase>: .word ...` en orden de `method_slot` (`vtable_entries(layout)`); un override reusa el slot del padre; el constructor no está.
- `NEW_OBJ`/`NEW_ARR` reservan con `rt_alloc` (memoria en cero).
- Impresión: integer con syscall 1, string con syscall 4, boolean como `true`/`false` (`rt_print_boolean`), null como `null`.

## 10. Errores y helpers de runtime

Errores modelados: índice fuera de rango, acceso a null, división por cero. Quien falla deja `$v1 = 1` y el mensaje en `$v0`; el que llama hace `bne $v1, $zero, destino` (`emit_error_check`). El destino es el handler activo o `error_target()`: la salida de la función (el error sube tal cual) o, en `main`, `main_error`, que llama a `rt_uncaught_error` y termina.

Contrato (`helpers.py`, mismo ABI; los cuerpos los implementa el runtime):

| Helper | Args | Devuelve | Puede fallar |
|---|---|---|---|
| `rt_alloc` | bytes | puntero | no |
| `rt_check_null` | puntero | — | sí |
| `rt_check_bounds` | arreglo, índice | — | sí |
| `rt_check_divisor` | divisor | — | sí |
| `rt_int_to_string` | integer | string | no |
| `rt_concat` | a, b | string | no |
| `rt_string_equals` | a, b | 0/1 | no |
| `rt_print_boolean` | boolean | — | no |
| `rt_uncaught_error` | mensaje | no vuelve | no |

`emit_helper_call` valida aridad, resultado y que se indique `on_error` si el helper puede fallar.

## 11. Etiquetas

Las del IR no son válidas en MIPS (`::` no se acepta y `#` abre comentario). `mangle_label` es inyectiva: `fn::` → `fn_` y se escapan `_`→`_u`, `.`→`_d`, `#`→`_h` (`fn::A.m` → `fn_A_dm`, `fn::f.g#2` → `fn_f_dg_h2`). Las de control (`L_<prefijo>_<n>`) no cambian. Propias del backend: `main`, `main_exit`, `main_error`, `<fn>_exit`, `__globals`, `str_<n>`, `vt_<Clase>`, `rt_*`.

## 12. API para los lowerers

- `MipsBuilder`: `emit`, `emit_branch`, `mark`, `add_data`, `add_string`, `build`, `render`. Valida cada instrucción contra `SIGNATURES` (`model.py`), etiquetas únicas y saltos sin destino.
- `plan_program(program, layout)` → planes por etiqueta del IR (`"main"` para el código global).
- `ActivationEmitter`: `begin_entry/end_entry`, `begin_function/end_function`, `mark_label`, `emit_branch`, `value_in_reg`, `load_value`, `store_storage`, `load_field`, `store_field`, `emit_arg`, `emit_call`, `emit_method_call`, `emit_helper_call`, `emit_return`, `error_target`, `emit_error_check`.

## 13. Supuestos y diferencias con el PDF

| Tema | PDF | Implementado |
|---|---|---|
| Constructores | no se heredan | se heredan: `constructor_label` apunta al del ancestro; el ABI no cambia |
| `StorageRef` | — | sin tipo: se agregó `RuntimeLayout.storage_type` |
| Código global | — | sin `FUNC_BEGIN`: frame propio en `main` |
| Argumentos | `ARG`/`CALL` | `ARG` intercalados: área de argumentos pendientes |
| Static link | argumento implícito | solo metadata `link=k`: el backend lo pasa primero |
| Inicialización | — | el IR no inicializa: locales en cero en el prólogo, globales por `.space`, campos por `rt_alloc` |
| `getReg` | API base | + `instruction()` para fijar registros por instrucción |
| `CompilationResult` | con `asm_text` | todavía `(success, diagnostics, ast_svg, tac_text, symbols)`; lo extiende la integración |
