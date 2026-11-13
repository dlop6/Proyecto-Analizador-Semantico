# Baseline — Proyecto 03 (generación de MIPS)

Estado de partida auditado antes de escribir el backend, y los supuestos verificados en MARS.

## Entorno

| Pieza | Versión |
|---|---|
| Commit base | `73bc0b3` (`master`, después del PR #3) |
| Rama | `feature/p1-mips-foundation` |
| Python | 3.13.6 |
| Java | 25 (2025-09-16 LTS) |
| ANTLR | 4.13.1 (`tools/antlr-4.13.1-complete.jar`, SHA-256 `bc13a9c5…8487`) |
| MARS | 4.5 (`tools/Mars4_5.jar`, SHA-256 `ac340b67…7096`, se baja con `tools/fetch_mars.*`) |

## Verificación

```
pytest tests -q -p no:cacheprovider        # base: 1393 en verde
java -cp tools/antlr-4.13.1-complete.jar org.antlr.v4.Tool -Dlanguage=Python3 -visitor -no-listener <dir>/Compiscript.g4
```

Regenerar el parser fuera del árbol da `CompiscriptLexer.py`, `CompiscriptParser.py` y `CompiscriptVisitor.py` idénticos a `compiler/generated/` (salvo la línea del comentario con la ruta). ANTLR sigue siendo el generador; la gramática no se tocó.

## Diferencias entre el PDF y lo implementado

| Tema | Situación real | Dónde se ve / resuelve |
|---|---|---|
| Constructores heredados | el PDF (§3.10) dice que no se heredan; el proyecto sí los hereda (`new Dog("Rex")` usa el de `Animal`). Impacto en el ABI: ninguno | `runtime_layout.py` (`constructor_label`), `tests/integration/test_compiler_service.py`, `tests/mips_base/test_class_metadata.py` |
| `StorageRef` sin tipo | el backend no sabe si imprimir/concatenar/comparar como string | `RuntimeLayout.storage_type`, `tests/ir/test_runtime_layout.py` |
| `IRProgram` sin layout | el backend recibe `(IRProgram, RuntimeLayout)` | `frame_planner.plan_program` |
| Código global sin frame | `entry` no tiene `FUNC_BEGIN` | `FramePlanner.plan_entry`, `ActivationEmitter.begin_entry` |
| `CompilationResult` | real: `(success, diagnostics, ast_svg, tac_text, symbols)`; el PDF pide `asm_text` y `asm_unoptimized` | lo cambia la integración; `tests/integration/test_compiler_service.py` |
| `ARG` intercalados | `f(1, g(2))` → `ARG 1; ARG 2; CALL g; ARG t; CALL f`, y el temporal se reusa entre `ARG` y `CALL` | área de argumentos pendientes; `tests/mips_base/test_calls_mars.py` |
| Static link | solo metadata `link=k`, sin `ARG` | `ActivationEmitter.emit_call`; `test_calls_mars.py` |
| `CALL_METHOD` | el receptor no es `ARG` ni cuenta en `argc` | `emit_method_call`; `test_abi.py` |
| Salida de `try` | `return`/`break`/`continue` dentro de un `try` no emiten `TRY_END` | queda para el lowering de excepciones (contar `TRY_BEGIN`/`TRY_END` linealmente) |
| Operandos inmediatos | `Const` a la izquierda (`BIN -, 5, r`), `Const op Const`, `IF_FALSE true, L` | `value_in_reg` carga cualquier operando |
| Sin inicialización | locales, globales y campos sin inicializador nunca se escriben | prólogo en cero, `.space`, `rt_alloc` en cero |
| Etiquetas del IR | `fn::A.m`, `fn::f.g#2` no son válidas en MIPS | `mangle_label`; `test_operands.py` |
| Strings | `BIN +` con resultado STRING es concatenación; `==` no dice si compara contenido | tipo del temporal o `storage_type`; helpers `rt_concat`, `rt_string_equals` |
| Errores de runtime | el IR no modela null, límites ni división por cero | convención `$v1` + helpers; `docs/BACKEND_MIPS.md` §10 |

## Supuestos probados en MARS

| Supuesto | Resultado | Test |
|---|---|---|
| Código de salida ante errores | siempre 0: se detecta por la salida (`Error in ... line n`; ejecución: `Runtime exception`) | `test_mars_env.py` |
| Límite de pasos | corta bucles infinitos (`maximum step limit`) | `test_mars_env.py` |
| Salida del programa | MARS agrega un salto de línea al terminar | `mars_runner.py` lo quita |
| `.` en etiquetas | válido | `test_mars_env.py` |
| `::` en etiquetas | inválido (error de ensamblado) | `test_mars_env.py` |
| Punto de inicio | la primera instrucción de `.text`, no la etiqueta `main` | por eso el builder exige `main` primero |
| `lw label+offset`, `jalr`, `div`/`rem` de 3 operandos | funcionan | `test_mars_env.py` |
| `div` por cero | trap (`break instruction executed`): no se puede dejar a MARS | `test_mars_env.py` |
| Temporal reusado entre `ARG` y `CALL` | ocurre en IR real (`CALL t0, fn::f` con `ARG t0`) y funciona con el área de pendientes | `test_calls_mars.py` |
| Registros finales | `$sp` inicial `0x7fffeffc`, `$fp` inicial 0 | `test_calls_mars.py` |

## Riesgos abiertos y notas para el resto del backend

- Calendario: el PDF pide la base antes de empezar el lowering; la entrega es el 16/11/2026.
- El allocator no hace análisis de vida: sin `release` explícito, los temporales muertos se expulsan por LRU (correcto, solo menos eficiente). No hay que liberar por "última aparición lineal": `foreach` mantiene temporales vivos a través del lazo.
- Cada instrucción del IR se baja dentro de `allocator.instruction()`, y las etiquetas/saltos/llamadas pasan por `ActivationEmitter` para respetar los límites de bloque.
- Los helpers `rt_*` tienen contrato pero no cuerpo; el builder rechaza el ensamblador si se llama a uno que no está definido.
- Strings con caracteres fuera de ASCII imprimible se rechazan al generar `.asciiz`.
