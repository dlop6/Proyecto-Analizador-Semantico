# Compiscript — Analizador Semántico

Proyecto de Construcción de Compiladores: analizador semántico para Compiscript
(subconjunto de TypeScript), en Python 3 + ANTLR4. El trabajo está dividido en
etapas con dependencia secuencial (ver `docs/temp/` para la división completa).

**Este README documenta el frontend y la semántica core** (parser, AST, tipos,
tabla de símbolos; expresiones, funciones y control de flujo). La sección de
integración/IDE se agrega cuando esa etapa del proyecto arranca.

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

## Semántica core (expresiones, funciones, control de flujo)

Consume exclusivamente `FrontendResult` (ast, symbols, diagnostics) de la sección
anterior. No reconstruye el AST, los scopes ni la tabla de símbolos: los recorre
tal como los deja el frontend.

### Contrato congelado: `core_semantics.analyze`

```python
from compiler.core_semantics import analyze
from compiler.frontend import analyze_source

result = analyze(analyze_source(source)) -> CoreSemanticResult(ast, symbols, diagnostics)
```

- `ast` / `symbols`: exactamente los mismos objetos que trae el `FrontendResult` de
  entrada (misma identidad, no una copia). Si `frontend_result.ast is None` (error de
  sintaxis), `analyze` no corre nada y devuelve los diagnósticos del frontend tal cual.
- `diagnostics`: los diagnósticos del frontend **más** los de la semántica core, todos
  en la misma lista.
- `result.ok` / `result.has_errors`: mismo significado que en `FrontendResult`.

### Cómo se recorre el árbol sin reconstruirlo

`symbol_collector.py` ya abrió un scope por cada nodo que lo necesita (función, clase,
bloque, bucle, switch, catch), en la posición `(line, column)` de ese nodo. `CoreSemanticVisitor`
arma una sola vez un diccionario `posición -> Scope` a partir de `SymbolTable.all_scopes()`
y, al visitar un nodo, mueve un cursor (`_current`) a su scope correspondiente en vez de
llamar a `SymbolTable.push()` — así nunca crea un scope nuevo ni duplica el árbol.

Los tres módulos de reglas (`expression_rules.py`, `function_rules.py`,
`control_flow_rules.py`) son funciones puras: reciben tipos ya inferidos (nunca el AST
ni los scopes) y devuelven `(tipo_resultante, código_de_diagnóstico_o_None, detalle)`.
Quien realmente escribe en la bolsa de diagnósticos es `CoreSemanticVisitor`, que es el
único que conoce la posición real de cada nodo.

### Catálogo de diagnósticos (`CPS-1xx`, de la semántica core)

`diagnostics.py` es propiedad del frontend y su catálogo de mensajes (`_MESSAGES`) es
exclusivamente `CPS-0xx` (hay un test del frontend que lo hace cumplir). Por eso la
semántica core mantiene su **propio** catálogo en `compiler/core_semantic_visitor.py`
(`_MESSAGES` local), reutilizando de `diagnostics.py` solo el mecanismo compartido:
`Diagnostic`, `DiagnosticBag` y `Severity`.

| Código | Severidad | Significado |
|---|---|---|
| CPS-100 | error | tipo incompatible en la inicialización/asignación de una variable, constante o atributo |
| CPS-101 | error | variable/atributo sin tipo declarado y sin inicializador |
| CPS-102 | error | reasignación de una constante |
| CPS-103 | error | identificador no declarado |
| CPS-104 | error | operandos incompatibles para `+`, `-`, `*`, `/` o `%` |
| CPS-105 | error | operador relacional (`<`, `<=`, `>`, `>=`) con operandos no numéricos |
| CPS-106 | error | operandos no comparables con `==` / `!=` |
| CPS-107 | error | operador lógico (`&&`, `\|\|`) con operando no booleano |
| CPS-108 | error | operando de `-` o `!` unario con tipo incompatible |
| CPS-109 | error | condición no booleana en `if`/`while`/`do-while`/`for`/ternario |
| CPS-110 | error | se intenta invocar algo que no es una función |
| CPS-111 | error | número de argumentos incorrecto en una llamada |
| CPS-112 | error | tipo de argumento incompatible con el parámetro |
| CPS-113 | error | `return` incompatible con el tipo de retorno declarado |
| CPS-114 | error | los `return` de una función sin anotación no tienen un tipo común |
| CPS-115 | error | discriminante de `switch` de tipo no escalar (no es integer/string/boolean) |
| CPS-116 | error | `case` incompatible con el tipo del discriminante |
| CPS-117 | warning | código inalcanzable después de `return`/`break`/`continue` en el mismo bloque |
| CPS-118 | warning\* | el operador ternario no tiene un tipo común entre sus dos ramas |

\* CPS-118 se reporta con severidad de error (impide `result.ok`); solo CPS-117 es warning.

### Decisiones de diseño relevantes (semántica core)

- **Reglas ya cubiertas por el frontend no se repiten aquí.** `break`/`continue` fuera de
  bucle, `return` fuera de función (`CPS-012`/`013`/`014`), funciones y clases duplicadas
  (`CPS-020`/`021`) y parámetros duplicados (`CPS-022`) ya los valida
  `symbol_collector.py` durante la construcción de scopes — repetirlos aquí violaría DRY.
- **División con la semántica extendida (clases y arreglos).** `PropertyAccess`,
  `IndexAccess`, `NewExpr`, `ThisExpr` y `ArrayLiteral` **no** reciben `inferred_type` en
  esta etapa: se dejan en `None` a propósito para que la etapa siguiente (clases/arreglos)
  los complete con la información de miembros y objetos que solo ella conoce. Esto es
  posible porque `AstVisitor.generic_visit` (de `ast_nodes.py`) recorre igual sus
  subexpresiones aunque este visitor no tenga un manejador propio para ellos — así una
  llamada a método (`obj.metodo()`) o un acceso a arreglo (`a[i]`) siguen visitándose sin
  que `CoreSemanticVisitor` tenga que conocer clases ni arreglos.
- **Inferencia de retorno con recursión.** Cuando una función sin anotación de retorno se
  llama a sí misma (o a otra función mutuamente recursiva sin anotación) antes de que su
  cuerpo termine de recorrerse, su tipo de retorno todavía es `None`. Esa llamada resuelve
  a tipo `ERROR` (que se absorbe en silencio en el resto de la expresión) en vez de forzar
  un análisis de punto fijo — una limitación documentada y aceptada: el enunciado no exige
  resolver ese caso, y una función *con* anotación de retorno nunca lo sufre (su tipo se
  conoce desde la fase de firmas del frontend).
- **Funciones anidadas dentro de un cuerpo (no top-level, no método).** `symbol_collector.py`
  abre un scope para su cuerpo pero no la registra como símbolo en ningún scope (solo
  predeclara nombres top-level). `CoreSemanticVisitor` sigue analizando su cuerpo con
  normalidad, pero no puede validar sus `return` contra una firma que no existe, y una
  llamada a esa función por nombre reporta `CPS-103`. Es una limitación conocida del
  frontend, no de esta etapa — está fuera del alcance de Persona 2 modificar
  `symbol_collector.py`.
- **Igualdad de tipos por valor, no por identidad.** Los tipos primitivos (`INTEGER`,
  `STRING`, `BOOLEAN`) son singletons en `types.py`, pero las reglas de esta etapa los
  comparan con `==` (igualdad estructural de dataclass) y no con `is`, para que sigan
  funcionando igual si algún día dejan de ser singletons únicos.

### Estructura de la semántica core

```
compiler/
  expression_rules.py     # tipos de operadores binarios/unarios, condiciones, ternario
  function_rules.py       # validación de llamadas y de 'return' (incluye ReturnTracker)
  control_flow_rules.py   # discriminante/case de switch, código muerto
  core_semantic_visitor.py  # coordina el recorrido, catálogo CPS-1xx propio
  core_semantics.py         # fachada: analyze (API congelada)
tests/person2/
  fixtures/{valid,invalid}/*.cps
  test_*.py
```

### Ejecutar tests de la semántica core

```bash
pytest tests/person2 -v
```

Corren sobre el frontend real (`compiler.frontend.analyze_source`), no sobre mocks: cada
test de integración arma su AST y su tabla de símbolos ejecutando el pipeline completo del
frontend antes de correr `core_semantics.analyze`.
