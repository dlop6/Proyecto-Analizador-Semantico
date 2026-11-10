# Baseline del Proyecto 01 (Gate 0 del Proyecto 02)

Esta es la auditoría del repositorio antes de construir el código intermedio. Documenta las APIs
**reales** para que nadie programe contra los nombres que supone el PDF de división de trabajo, las
correcciones que hizo falta aplicar para poder continuar y las limitaciones que siguen vigentes.

## 1. Cómo se ejecuta

| Qué | Comando |
|---|---|
| Instalar | `pip install -r requirements.txt` (`antlr4-python3-runtime==4.13.1`, `pytest==9.0.2`, `flask==3.1.3`, `graphviz==0.21`) |
| Regenerar ANTLR (Windows) | `.\tools\generate_antlr.ps1` |
| Regenerar ANTLR (bash) | `./tools/generate_antlr.sh` |
| Regenerar ANTLR (Docker) | `docker build -f docker/Dockerfile.antlr -t compiscript-antlr .` y luego `docker run` (ver README) |
| Tests | `pytest tests -q` |
| IDE | `flask --app ide.app run` |

- Los tres caminos de regeneración usan **ANTLR 4.13.1** y verifican el SHA-256 del jar
  (`bc13a9c5…8487`).
- La salida queda versionada en `compiler/generated/`. Regenerarla da archivos idénticos (verificado),
  salvo la primera línea, que lleva la ruta local de la gramática.
- Docker no reescribe `compiler/generated/__init__.py`, pero ese archivo está versionado.

## 2. APIs reales del pipeline

| Etapa | Función | Resultado (frozen) |
|---|---|---|
| Frontend | `frontend.analyze_source(source)` | `FrontendResult(ast, symbols, diagnostics)` + `ok` / `has_errors` |
| Semántica core | `core_semantics.analyze(frontend_result)` | `CoreSemanticResult(ast, symbols, diagnostics)` |
| Semántica extendida | `extended_semantics.analyze(core_result)` | `ExtendedSemanticResult(ast, symbols, diagnostics)` |
| Integración | `compiler_service.compile_source(source)` | `CompilationResult(success, diagnostics, ast_svg, symbols)` |

- **AST y tabla de símbolos.** Las cuatro etapas comparten el mismo AST y la misma `SymbolTable`; ninguna
  los reconstruye. Cada `Expr` trae `inferred_type`.
- **Visitor.** `AstVisitor` (`compiler/ast_nodes.py`) despacha primero por `_dispatch`, después por
  `visit_<Nodo>` y por último cae en `generic_visit`.
- **Tamaño de la fuente.** `MAX_SOURCE_BYTES` = 5 MiB.

## 3. Lo que el PDF supone y lo que hay en realidad

| El PDF dice | En el repo |
|---|---|
| `SemanticResult` | No existía. Ahora `extended_semantics.SemanticResult` es un **alias** de `ExtendedSemanticResult`, el resultado semántico final. No es otro contrato. |
| `DiagnosticCollector`, con deduplicación por `(phase, code, line, column)` | Es `DiagnosticBag`, que deduplica por `(code, line, column)` y ordena por `(line, column, code)`. La fase se deduce del rango del código: `CPS-0xx` frontend, `CPS-1xx` core, `CPS-2xx` extendida. Por eso la clave ya equivale a la del PDF y no se agregó un campo de fase (YAGNI). |
| "La semántica restringe `break` a bucles" | **Falso:** `break` dentro de `switch` se acepta. La IR lo baja a `GOTO L_switch_end` (ver `INTERMEDIATE_CODE.md` §10). |
| Recuperación de errores ANTLR | Confirmada: se quitan los listeners por defecto, se usa `CollectingErrorListener` y la estrategia por defecto (sin `BailErrorStrategy`). Una misma corrida acumula varios errores léxicos y sintácticos. Con error de sintaxis no se construye AST. |
| Campos de runtime en la tabla de símbolos | No existían. Los agrega Persona 1 (§5). |

## 4. Correcciones hechas en el Gate 0

Cada corrección tiene su test de regresión.

1. **Función anidada dentro de un método marcada como método** (`ast_builder.py`).
   - Daba un `CPS-113` falso y resolvía contra `cls.methods`.
   - Ahora el cuerpo de un método ya no cuenta como "miembro de clase".
2. **`FunctionSymbol.scope` siempre `None`, y parámetros duplicados en dos objetos distintos**
   (`symbol_collector.py`).
   - Ahora toda función, anidada, método y constructor apunta a su scope.
   - Los objetos de `fn.params` son los mismos que viven en el scope.
   - Se unificó la construcción de parámetros (DRY).
3. **Función top-level duplicada que le pisaba la firma a la primera.** Ahora el símbolo se asocia al nodo
   por posición.
4. **Función anidada con un nombre ya declarado en su scope.** Pasaba en silencio; ahora da `CPS-020`.
5. **Error duplicado `CPS-100` + `CPS-209`** con el mismo punto y el mismo mensaje.
   - La re-pasada de `extended_semantics.analyze` ya hace que la core reporte `CPS-100`.
   - Se **retiró `CPS-209`** junto con su código muerto, y se actualizaron 4 tests y el README.
   - Un test general verifica que ninguna fixture reporte la misma causa dos veces.
6. **Clase declarada dentro de una función o bloque** (decisión de diseño).
   - Antes pasaba como válida, pero sin `ClassSymbol` ni `this`, e instanciarla ya daba `CPS-030`/`CPS-023`.
   - Ahora es el error explícito **`CPS-024`**.
   - Una clase local homónima de una top-level ya no le pisa el scope.
7. **`tests/frontend/test_architecture.py`.**
   - Su detector no veía `from compiler.x import y`, así que verificaba en vacío.
   - Ahora detecta los imports reales, ignora `if TYPE_CHECKING:` y tiene un test que prueba que detecta.
   - No apareció ninguna violación de capas.

## 5. Lo que agrega Persona 1

| Módulo | Qué contiene |
|---|---|
| `compiler/runtime/storage.py` | `StorageKind`, `StorageRef` |
| `compiler/runtime/activation_records.py` | `ActivationRecord`, `ClassLayout`, `FrameSlot`, `FieldEntry`, `MethodEntry` |
| `compiler/runtime/scoped_visitor.py` | Extra al PDF, justificado por SRP. Recorre el AST resolviendo cada nombre al mismo símbolo que el collector; lo usan Persona 1 y Persona 2. |
| `compiler/runtime/runtime_layout.py` | `prepare`, `RuntimeLayout`, `require_semantic_success` |
| `compiler/ir/` | `opcodes`, `model`, `builder`, `serializer`, `temp_manager`, `label_manager` |
| `compiler/symbols.py` | Campos de runtime con default `None`, fuera de `repr` y `==`: `storage_kind`, `slot`, `owner`, `label`, `method_slot`, `activation_record`, `layout` |

La especificación completa está en `docs/INTERMEDIATE_CODE.md`.

## 6. Tests

| Carpeta | Tests |
|---|---|
| `tests/frontend` | 560 |
| `tests/person2` | 114 |
| `tests/person3` | 73 |
| `tests/integration` | 67 |
| `tests/grading` | 4 |
| `tests/ir` (Persona 1, Proyecto 02) | 258 |
| **Total** | **1076** |

El baseline anterior era de 799. Todos siguen pasando; solo se ajustaron los 4 que esperaban `CPS-209`.

## 7. Limitaciones vigentes

Se documentan; no se corrigieron en este gate.

- **`program/program.cps` (el ejemplo oficial) no pasa la semántica**, así que no genera IR.
  - 7 errores `CPS-104` por concatenaciones `string + integer`: la regla del Proyecto 01 solo admite
    `string + string`.
  - 1 error `CPS-210` en `new Dog("Rex")`: los constructores no se heredan (regla 12).
  - **Resuelto en la integración final:** se sigue el ejemplo oficial, así que `+` concatena un
    `string` con `integer`/`boolean` y una clase sin constructor usa el del ancestro más cercano.
    `program.cps` ahora compila sin diagnósticos y genera TAC.
- **No hay `float`** (decisión del proyecto).

## 8. Notas para Persona 2 y Persona 3

- **Punto de partida:** `prepare(result)` solo acepta un resultado sin errores; las advertencias se
  permiten. Después, `IRBuilder(layout)`.
- **Variables:** el acceso a cualquier variable sale de `layout.ref_for(simbolo, funcion_actual)`. Para
  saber el símbolo y la función actual, conviene extender `ScopedVisitor` en vez de recorrer scopes a mano.
- **Estructura de scopes del collector:**
  - el cuerpo de una función reutiliza su scope FUNCTION;
  - `while` y `do-while` usan un scope LOOP sin BLOCK;
  - `for` y `foreach` usan LOOP + BLOCK;
  - todos los `case` comparten un único SWITCH;
  - el `catch` y su cuerpo comparten un único CATCH.
- **Constructores y métodos:** `ClassSymbol.constructor` es el único constructor válido (no se buscan en
  los padres). Los slots de despacho salen de `cls.layout`.
