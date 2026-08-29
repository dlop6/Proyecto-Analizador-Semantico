# Compiscript — Analizador Semántico

Proyecto de Construcción de Compiladores: analizador semántico para Compiscript
(subconjunto de TypeScript), en Python 3 + ANTLR4. El trabajo está dividido en
etapas con dependencia secuencial (ver `docs/temp/` para la división completa).

**Este README documenta el frontend** (parser, AST, tipos, tabla de símbolos).
Las secciones de semántica core y de integración/IDE se agregan cuando esas
etapas del proyecto arrancan.

## Requisitos

- Python 3.11+ (se usa `StrEnum`, requiere 3.11 como mínimo)
- Java 11+ (para regenerar el parser con ANTLR; no hace falta si solo vas a correr tests)
- Docker (opcional, fallback si no hay Java local)

## Instalación

```bash
pip install -r requirements.txt
```

## Regenerar ANTLR

El parser, lexer y visitor de Python (`compiler/generated/*.py`) están commiteados
en el repo, así que un clon limpio puede correr los tests sin regenerar nada. Si
modificás `program/Compiscript.g4`, hay que regenerar:

### Opción A — local con Java (primaria)

```bash
# windows
.\tools\generate_antlr.ps1

# linux / mac / git bash
./tools/generate_antlr.sh
```

El script descarga `antlr-4.13.1-complete.jar` si no está, **verifica su SHA-256**
contra un hash pinneado en el propio script (aborta si no coincide, no confía
ciegamente en la red) y corre:

```
java -cp antlr-4.13.1-complete.jar org.antlr.v4.Tool -Dlanguage=Python3 -visitor -no-listener -o compiler/generated program/Compiscript.g4
```

### Opción B — Docker (fallback sin Java local)

```bash
docker build -f docker/Dockerfile.antlr -t compiscript-antlr .
docker run --rm -v "$(pwd)/program:/work/program" -v "$(pwd)/compiler/generated:/work/out" compiscript-antlr
```

Corre como usuario sin privilegios y monta solo lo necesario (mínimo privilegio).

**Importante:** el runtime de Python (`antlr4-python3-runtime` en `requirements.txt`)
y el jar usado para generar **deben coincidir exactamente en versión** (4.13.1).
ANTLR lo valida en tiempo de ejecución y falla ruidosamente si no coinciden — es la
causa de fallo #1 si algo no arranca.

## Ejecutar tests del frontend

```bash
pytest tests/frontend -v
```

Ningún test usa `pytest.skip`: si `compiler/generated/` no existe o el import falla,
el test de gramática falla directamente (no es un detalle opcional, sino una condición
que debe cumplirse siempre).

## Contrato congelado: `frontend.analyze_source`

```python
from compiler.frontend import analyze_source

result = analyze_source(source: str) -> FrontendResult(ast, symbols, diagnostics)
```

- `ast`: `Program | None`. Es `None` únicamente cuando hubo error de sintaxis (no se
  construye AST sobre un parse roto, ver más abajo). Si no es `None`, siempre es la
  raíz completa del programa.
- `symbols`: `SymbolTable` con el árbol de scopes completo, sin importar si hubo
  errores semánticos (siempre se recolecta lo que se pudo).
- `diagnostics`: `list[Diagnostic]`, ordenados por línea → columna → código,
  determinista.
- `result.ok`: `True` si `ast is not None` y no hay diagnósticos de severidad error.
- `result.has_errors`: `True` si hay al menos un diagnóstico de severidad error.

Esta API **no cambia de forma** — está protegida por un test de introspección
(`test_frontend.py::test_frontend_result_tiene_exactamente_los_atributos_del_pdf`).

## Catálogo de diagnósticos (`CPS-0xx`, del frontend)

| Código | Severidad | Significado |
|---|---|---|
| CPS-000 | error | carácter no reconocido (léxico) |
| CPS-001 | error | error de sintaxis |
| CPS-002 | warning | literal entero fuera del rango de 64 bits |
| CPS-003 | error | literal malformado (hardening, no debería ocurrir con la gramática actual) |
| CPS-004 | error | fuente excede el tamaño máximo permitido |
| CPS-010 | error | destino de asignación inválido (ej. `f() = 1;`) |
| CPS-011 | error | `const` sin inicializador (inalcanzable con la gramática actual, defensivo) |
| CPS-012 | error | `break` fuera de bucle o switch |
| CPS-013 | error | `continue` fuera de bucle |
| CPS-014 | error | `return` fuera de función |
| CPS-020 | error | redeclaración en el mismo scope |
| CPS-021 | error | miembro de clase duplicado |
| CPS-022 | error | parámetro duplicado |
| CPS-023 | error | nombre de clase no declarado (en `new` o herencia) |
| CPS-030 | error | tipo desconocido en una anotación |
| CPS-031 | error | herencia circular |
| CPS-032 | error | el constructor no debe declarar tipo de retorno |
| CPS-033 | warning | un atributo oculta uno heredado |
| CPS-040 | error | `this` usado fuera de un método o constructor |

Rango reservado: `CPS-0xx` es del frontend, `CPS-1xx` queda para la semántica core
(tipos), `CPS-2xx` para integración/IDE. Un test (`test_diagnostics.py`) impide
que un código del frontend se salga de su rango.

## Decisiones de diseño relevantes

- **No hay `float`.** La gramática oficial no lo trae, y por decisión del proyecto
  no se modifica. `integer` es el único tipo numérico. `numeric_result` y
  `common_type` (en `compiler/types.py`) quedan con semántica honesta para ese
  escenario: si algún día se agrega `float`, se actualiza una sola función.
- **Arrays son invariantes.** `Array[Perro]` no es asignable a `Array[Animal]`
  aunque `Perro` herede de `Animal` — evita el array-store problem.
- **Sin AST tras error de sintaxis.** Si hubo error léxico o sintáctico,
  `analyze_source` devuelve `ast=None`. Construir sobre un parse tree con recovery
  (que trae `ErrorNode` y contextos `None`) generaría ruido, no información.
- **Scopes de `for`/`foreach`:** siempre 2 scopes (`LOOP` + `BLOCK`), la variable de
  cabecera vive en `LOOP` y no se filtra al scope circundante.
- **Scope de `switch`:** uno solo, compartido por todos los `case` (sin llaves en
  la gramática, replica el fallthrough de C/Java: declarar la misma variable en dos
  cases distintos es duplicado).
- **Scope de `catch`:** el parámetro y el cuerpo comparten un único scope
  (redeclarar el parámetro dentro es duplicado, como en Java).
- **Literal unificado.** El token `Literal` de la gramática cubre tanto enteros
  como strings; `ast_builder.py` desambigua mirando el primer carácter del texto
  (las dos reglas del lexer son léxicamente disjuntas por construcción).
- **Strings sin escapes.** La gramática no define secuencias de escape
  (`~["\r\n]*`), así que `"a\nb"` se guarda literal, no se interpreta `\n`.

## Fronteras con las siguientes etapas (semántica core / integración)

- Cada nodo `Expr` trae `inferred_type: Type | None = None`. El frontend **nunca**
  lo escribe — es el campo que la etapa de semántica core rellena in-place durante
  el chequeo de tipos.
- El uso general de identificadores dentro de expresiones (`x` sin declarar en
  `x + 1`) **no** lo valida el frontend — le corresponde a la semántica core. El
  frontend solo valida nombres de clase en `new`/herencia (`CPS-023`), porque es
  estructura de símbolos, no resolución de expresiones.
- El tipo de la variable de iteración de un `foreach` queda en `None` — requiere
  tipar la colección, responsabilidad de la etapa siguiente.
- `types.py` no depende de `symbols.py` ni de `ast_nodes.py` (verificado por
  `test_architecture.py`). `is_assignable` y `common_type` aceptan un parámetro
  opcional `hierarchy` para hacer subtipado nominal cuando quien los llama tiene
  acceso a la tabla de clases.

## Estructura del proyecto (frontend)

```
program/
  Compiscript.g4          # gramática oficial, sin modificar
  program.cps              # programa de ejemplo oficial
compiler/
  generated/                # salida de antlr (commiteada)
  diagnostics.py             # Diagnostic, DiagnosticBag, CollectingErrorListener
  types.py                   # sistema de tipos: same_type, is_assignable, numeric_result, common_type
  ast_nodes.py                # catálogo de ~40 nodos + AstVisitor genérico
  ast_builder.py               # parse tree de antlr -> ast propio
  symbols.py                    # Symbol, VariableSymbol, FunctionSymbol, ClassSymbol
  scopes.py                      # Scope, ScopeKind, SymbolTable
  symbol_collector.py             # predeclaración + firmas + cuerpos, en 3 pasadas
  frontend.py                      # fachada: analyze_source (API congelada)
tools/
  generate_antlr.ps1 / .sh     # regenera el parser, con verificación de integridad
docker/
  Dockerfile.antlr              # fallback sin java local
tests/frontend/
  fixtures/{valid,invalid}/*.cps
  test_*.py
```
