# Código intermedio de Compiscript (TAC)

Especificación del lenguaje intermedio que genera el compilador. Es el contrato entre
la infraestructura del IR y los generadores de TAC (`CoreTacGenerator` para el
subconjunto core y `ExtendedTacGenerator` para arreglos, objetos, herencia y try/catch). Los ejemplos de este documento **no están escritos a
mano**: los arma `tests/ir/test_intermediate_code_doc.py` con el `IRBuilder` real y el
test falla si el texto deja de coincidir.

Archivos: `compiler/ir/` (`opcodes`, `model`, `builder`, `serializer`, `temp_manager`,
`label_manager`) y `compiler/runtime/` (`storage`, `activation_records`,
`runtime_layout`, `scoped_visitor`).

## 1. Principios

- **TAC estructurado.** Cada instrucción es un objeto `TACInstruction(opcode, result, arg1, arg2, metadata)`.
  El texto es solo una serialización: ninguna regla arma strings de TAC a mano.
- **Slots abstractos, no bytes.** No hay arquitectura objetivo y generar código objeto está fuera de alcance.
- **Contrato cerrado.** Solo existen los 24 opcodes de la sección 5. Agregar uno exige modificar
  `opcodes.SIGNATURES` y este documento.
- **Sin optimización.** No hay SSA, CFG, constant folding ni eliminación de código muerto. El único
  manejo de recursos es el reciclaje de temporales.

## 2. Estructura de un programa

Un `IRProgram` tiene dos partes:

- **entrada** (`IRFragment`): el código global, que es por donde arranca el programa;
- **funciones** (`IRFunction`): una por cada función, método o constructor. Cada una abre con
  `FUNC_BEGIN` y cierra con `FUNC_END`.

Reglas del texto:

- Primero va la entrada y después las funciones, en el orden en que se **cerraron**. Por eso una función
  anidada aparece antes que la que la contiene.
- Las unidades se separan con una línea en blanco.
- `FUNC_BEGIN`, `FUNC_END` y `LABEL` van al margen; el resto, con dos espacios de sangría.

Cada unidad tiene sus propios temporales: todas arrancan en `t0` y no comparten estado.

## 3. Gramática textual

```ebnf
program     = [ unit { blank_line unit } ] ;
unit        = { line } ;
line        = flush | indented ;
flush       = "FUNC_BEGIN" sp function "," sp "frame=" int
            | "FUNC_END"   sp function "," sp "temps=" int
            | "LABEL"      sp label ;
indented    = "  " ( assign | plain ) ;
assign      = dest sp "=" sp OPCODE [ sp args ] ;          (* BIN UN NEW_ARR ARR_GET LEN NEW_OBJ GET_FIELD *)
plain       = OPCODE [ sp args ] ;                          (* el resto *)
args        = arg { "," sp arg } { "," sp meta } ;
meta        = key "=" int ;                                 (* argc, link, fields *)
arg         = temp | const | storage | label | function | class | method | operator ;

temp        = "t" int ;
const       = int | string | "true" | "false" | "null" ;
string      = '"' { json_char } '"' ;                       (* escapes estilo JSON: \" \\ \n *)
storage     = name "@global[" int "]"
            | name "@frame[" int "]"
            | name "@frame^" int "[" int "]"                (* NONLOCAL: saltos de static link *)
            | name "@field[" int "]" ;
label       = "L_" prefix "_" int ;                         (* prefix = [a-z_]+ *)
function    = "fn::" path [ "#" int ] ;                     (* path = ident { "." ident } *)
class       = ident ;
method      = ident "[" int "]" ;                           (* nombre[slot de despacho] *)
operator    = "+" | "-" | "*" | "/" | "%" | "==" | "!=" | "<" | "<=" | ">" | ">=" | "!" ;
```

## 4. Operandos

| Operando | Texto | Uso |
|---|---|---|
| `Temp(index, type)` | `t3` | resultado intermedio; lo reparte solo el `TempManager` |
| `Const(value, type)` | `42`, `"hola"`, `true`, `null` | literal `integer`/`string`/`boolean`/`null` |
| `StorageRef` GLOBAL | `x@global[0]` | variable fuera de toda función |
| `StorageRef` LOCAL/PARAM/THIS | `y@frame[2]` | variable del frame de la función actual |
| `StorageRef` NONLOCAL | `y@frame^1[2]` | variable del frame de una función que encierra a la actual, a 1 salto |
| `StorageRef` FIELD | `v@field[1]` | slot de un atributo; solo se usa en `GET_FIELD`/`SET_FIELD` |
| `Label` | `L_if_end_0`, `fn::f.g` | destino de salto o función a llamar |
| `ClassRef` | `Perro` | clase de `NEW_OBJ` |
| `MethodRef` | `hablar[0]` | entrada de la tabla de despacho para `CALL_METHOD` |

Roles que valida el builder:

- **valor:** temporal, constante o almacenamiento que no sea FIELD;
- **destino:** temporal o almacenamiento que no sea FIELD; nunca una constante.

## 5. Opcodes

`R` = result, `A` = arg1, `B` = arg2. "Opcional" significa que el operando puede faltar.

| Opcode | Texto | Semántica |
|---|---|---|
| `MOV` | `MOV R, A` | copia el valor A en el destino R |
| `BIN` | `R = BIN op, A, B` | operación binaria; `op` ∈ `+ - * / % == != < <= > >=`. **No** existen `&&` ni `\|\|`: se bajan con cortocircuito |
| `UN` | `R = UN op, A` | `op` ∈ `-` (negación aritmética), `!` (negación lógica) |
| `PRINT` | `PRINT A` | imprime A |
| `LABEL` | `LABEL L` | marca una etiqueta (lo emite `mark_label`) |
| `GOTO` | `GOTO L` | salto incondicional |
| `IF_TRUE` | `IF_TRUE A, L` | salta a L si A es verdadero |
| `IF_FALSE` | `IF_FALSE A, L` | salta a L si A es falso |
| `FUNC_BEGIN` | `FUNC_BEGIN fn, frame=n` | abre una función; `frame` = slots de su registro de activación |
| `FUNC_END` | `FUNC_END fn, temps=k` | cierra la función; `temps` = pico de temporales vivos |
| `ARG` | `ARG A` | pasa el siguiente argumento, en orden izquierda→derecha |
| `CALL` | `CALL [R,] fn, argc=n[, link=k]` | llama a `fn` con los últimos `n` ARG. R es opcional (sin R el resultado se descarta). `link=k` solo si la función llamada usa static link |
| `RETURN` | `RETURN [A]` | sale de la función, con valor o sin él |
| `NEW_ARR` | `R = NEW_ARR A` | crea un arreglo de A elementos |
| `ARR_GET` | `R = ARR_GET A, B` | R = A[B] |
| `ARR_SET` | `ARR_SET R, A, B` | R[A] = B (R es el arreglo que se modifica) |
| `LEN` | `R = LEN A` | longitud del arreglo A |
| `NEW_OBJ` | `R = NEW_OBJ C, fields=n` | crea un objeto de la clase C con n slots de atributo |
| `GET_FIELD` | `R = GET_FIELD A, f` | R = atributo f del objeto A |
| `SET_FIELD` | `SET_FIELD R, f, B` | atributo f del objeto R = B |
| `CALL_METHOD` | `CALL_METHOD [R,] A, m[s], argc=n` | despacha el slot `s` sobre el receptor A, que pasa a ser `this` del método; `argc` no cuenta al receptor |
| `TRY_BEGIN` | `TRY_BEGIN L` | entra a un bloque protegido cuyo manejador es L |
| `TRY_END` | `TRY_END` | sale del bloque protegido sin error |
| `CATCH` | `CATCH R` | en el manejador, guarda en R la excepción capturada |

`FUNC_BEGIN`, `FUNC_END` y `LABEL` no se emiten con `emit`: los producen
`begin_function`, `end_function` y `mark_label`.

## 6. Temporales

- Los reparte solo el `TempManager` (`IRBuilder.new_temp` / `release_temp`). Hay **uno por unidad**:
  cada función y el código global empiezan en `t0`.
- **Reciclaje:** al liberarse, el número vuelve a un pool y el siguiente pedido reutiliza el número libre
  más bajo. Un temporal **nunca** se entrega dos veces mientras sigue vivo.
- **Pool por categoría** (decisión de diseño): `int`, `bool`, `string` y `ref` (objetos, arreglos y
  `null`). Con un pool por tipo exacto, cada clase o arreglo distinto tendría el suyo y casi no habría
  reciclaje.
- **Política para los generadores:** liberar un temporal justo después de su último uso. Nunca se
  liberan variables, constantes ni `StorageRef`.
- **Validaciones del builder:**
  - usar un temporal no vivo es error;
  - liberar dos veces es error;
  - cerrar una unidad con temporales vivos es error;
  - usar un temporal de otra unidad es error.
- `FUNC_END temps=k` informa el pico de temporales vivos a la vez; `IRFunction.created_temps` informa
  cuántos nombres distintos se crearon.

## 7. Etiquetas

`LabelManager` es la única fuente de etiquetas y hay uno por compilación. Es determinista: la misma
secuencia de pedidos da siempre las mismas etiquetas.

- **Control:** `L_<prefijo>_<n>`. `n` es un contador global de la compilación, compartido entre
  prefijos, así que ninguna se repite. Prefijos sugeridos:

  | Construcción | Prefijos |
  |---|---|
  | if | `if_else`, `if_end` |
  | while | `while_cond`, `while_end` |
  | do-while | `do_body`, `do_cond`, `do_end` |
  | for | `for_cond`, `for_step`, `for_end` |
  | foreach | `foreach_cond`, `foreach_step`, `foreach_end` |
  | switch | `switch_case`, `switch_default`, `switch_end` |
  | ternario | `tern_else`, `tern_end` |
  | cortocircuito | `and_end`, `or_end` |
  | try/catch | `try_handler`, `try_end` |

- **Funciones:** `fn::<ruta>`. Ejemplos de ruta:
  - `factorial` (top-level);
  - `f.g` (`g` anidada en `f`);
  - `Perro.hablar` (método);
  - `Perro.constructor` (constructor);
  - `Perro.hablar.eco` (anidada dentro de un método).

  Si dos funciones anidadas homónimas viven en bloques hermanos, la segunda queda `fn::f.g#2`.
- Cada etiqueta de control se marca **una sola vez**. Todo salto tiene que caer en una etiqueta
  marcada dentro de su **misma** unidad, y todo `CALL` tiene que apuntar a una función emitida.

## 8. Almacenamiento y registros de activación

`runtime_layout.prepare(result)` asigna el almacenamiento una sola vez y lo escribe en la misma tabla de
símbolos: `storage_kind`, `slot` y `owner` en variables; `label`, `method_slot` y `activation_record` en
funciones; `layout` en clases.

- **Globales:** toda variable que no vive dentro de una función, incluidas las de bloques, bucles y
  `catch` del nivel superior. Toma slots `0..n-1` en preorden de scopes y orden de declaración.
- **Frame de una función:** `[this] [params] [locales]`.
  - `this` solo existe en métodos y constructores, siempre en el slot 0.
  - Los locales son las variables de todos los bloques de la función (incluidas las de `for`,
    `foreach` y `catch`) en preorden, sin entrar a funciones anidadas.
  - **No** se reutilizan slots entre bloques hermanos (KISS).
- **`lexical_depth`:** cantidad de funciones que encierran a esta. Es 0 en funciones top-level y en
  métodos.
- **Static link.** Una función lo tiene solo si necesita llegar al frame de una función que la
  encierra. Pasa en tres casos:
  1. lee o escribe una variable de ese frame, incluido `this` desde una función anidada dentro de un
     método;
  2. tiene una función anidada que necesita llegar todavía más arriba;
  3. llama a una función que usa static link y cuyo padre no es ella misma.

  Funciones top-level y métodos nunca tienen static link.
- **Acceso desde otra función:** `ref_for(simbolo, desde)` devuelve `NONLOCAL` con la cantidad de
  saltos. Por ejemplo, `this` usado dentro de una función anidada a un nivel queda `this@frame^1[0]`.
- **`link=k` en `CALL`:** `k` es la cantidad de saltos desde el frame de quien llama hasta el frame que
  hay que pasarle a la función llamada. `0` significa su propio frame; `link_hops(caller, callee)` lo
  calcula.

## 9. Clases y objetos

- **Campos:** los heredados van primero, en el slot que tienen en el padre; los propios después.
  - Un campo que oculta a uno heredado (warning `CPS-033`) recibe un **slot nuevo**. Es ocultamiento
    estilo Java: se resuelve por el tipo estático del receptor.
  - `ClassLayout.field_named` devuelve siempre el más derivado.
- **Tabla de despacho (`ClassLayout.methods`):** está completa.
  - Los métodos heredados conservan su slot y la implementación del padre.
  - Un override reutiliza el slot del padre con su propia implementación.
  - Los métodos nuevos se agregan al final.
- **Constructores:**
  - No entran a la tabla de despacho (no tienen `method_slot`): se llaman directo con `CALL`.
  - `ClassLayout.constructor_label` es el constructor propio o, si la clase no declara uno, el del
    ancestro más cercano que lo tenga (`new Dog("Rex")` llama a `fn::Animal.constructor`). Es `None`
    solo si ninguna clase de la cadena declara constructor.
- **Instanciación** `new C(args)`, en este orden:
  1. `t = NEW_OBJ C, fields=layout.size`;
  2. si hay inicializadores de atributos, `SET_FIELD t, ...` en el orden del layout (heredados primero).
     El inicializador se evalúa en el sitio del `new` (decisión de diseño), pero sus nombres se
     resuelven en el scope de la clase que lo declara, igual que en la semántica;
  3. si `constructor_label` no es `None`: `ARG t` (que pasa a ser `this`), los `ARG` de los argumentos y
     `CALL <constructor_label>, argc=n+1`.
- **Llamada a método** `obj.m(args)`, en este orden:
  1. se evalúa el receptor;
  2. se emite un `ARG` por argumento;
  3. `CALL_METHOD [R,] receptor, m[slot], argc=n`.

  El slot sale de `layout.method_named(m)` usando el tipo estático del receptor.
- **Atributos:** `obj.f` es `t = GET_FIELD obj, f@field[k]` y `obj.f = v` es `SET_FIELD obj, f@field[k], v`.
  El slot sale de `layout.field_named(f)` sobre el tipo estático de `obj`. El generador nunca recorre
  la jerarquía de clases: todo sale del layout ya aplanado.

## 10. Convenciones de lowering

- **Orden de evaluación:** izquierda a derecha en operandos y argumentos, respetando la precedencia que ya
  fija el AST.
- **Cortocircuito:** `a && b` copia `a` a un temporal y hace `IF_FALSE t, L_and_end`. Luego copia `b` a
  ese mismo temporal y marca `L_and_end`. `a || b` es igual con `IF_TRUE` y `L_or_end`.
- **Ternario:** un único temporal de resultado, con dos ramas (`tern_else` y `tern_end`).
- **`if`/`else`:**
  1. `IF_FALSE cond, L_if_else` (o `L_if_end` si no hay else);
  2. el bloque `then` y `GOTO L_if_end`;
  3. `LABEL L_if_else`, el bloque `else` y `LABEL L_if_end`.
- **`while`:**
  1. `LABEL L_while_cond`, la condición y `IF_FALSE cond, L_while_end`;
  2. el cuerpo y `GOTO L_while_cond`;
  3. `LABEL L_while_end`.

  `continue` salta a `L_while_cond`.
- **`do-while`:**
  1. `LABEL L_do_body` y el cuerpo;
  2. `LABEL L_do_cond`, la condición e `IF_TRUE cond, L_do_body`;
  3. `LABEL L_do_end`.

  `continue` salta a `L_do_cond`.
- **`for`:**
  1. la inicialización;
  2. `LABEL L_for_cond`, la condición (si existe) e `IF_FALSE`;
  3. el cuerpo;
  4. `LABEL L_for_step` y la actualización;
  5. `GOTO L_for_cond` y `LABEL L_for_end`.

  `continue` salta a `L_for_step`.
- **`foreach`** (solo sobre arreglos):
  1. el arreglo en un temporal `ref`, el índice en un temporal `int` y `LEN` en otro `int`; los tres
     quedan **vivos durante todo el cuerpo**;
  2. `LABEL L_foreach_cond`, `BIN <` entre índice y longitud, e `IF_FALSE` hacia `L_foreach_end`;
  3. `ARR_GET` y `MOV` a la variable de iteración;
  4. el cuerpo;
  5. `LABEL L_foreach_step`, índice + 1 y `GOTO L_foreach_cond`.
- **`switch`:**
  - **Sin fallthrough:** se ejecuta una sola rama.
  - El sujeto se evalúa una vez, en un temporal.
  - Para cada `case` se emiten `BIN ==` e `IF_TRUE` hacia `L_switch_case`; después, `GOTO` al default o
    al final.
  - Cada rama termina en `GOTO L_switch_end`.
  - Un `break` dentro de un `switch` (la semántica lo acepta) también salta a `L_switch_end`.
- **`break`/`continue` en bucles anidados:** se usa una pila de etiquetas; cada uno salta a las del bucle
  más interno.
- **Funciones:**
  - `begin_function(simbolo)`, el cuerpo y `end_function()`.
  - Si el cuerpo no termina en `RETURN`, se emite `RETURN` sin valor.
  - Los parámetros no se redeclaran: ya están en el frame.
- **Llamadas:**
  - Se evalúa cada argumento y se emite su `ARG` en orden, liberando el temporal después.
  - Después va `CALL [R,] fn::..., argc=n[, link=k]`.
  - Una llamada usada como sentencia va sin `R`.
  - La recursión es un `CALL` normal a la misma etiqueta.
- **`try`/`catch`:**
  1. `TRY_BEGIN L_try_handler`;
  2. el bloque `try`, `TRY_END` y `GOTO L_try_end`;
  3. `LABEL L_try_handler` y `CATCH variable`;
  4. el bloque `catch` y `LABEL L_try_end`.

  Un `return`, `break` o `continue` dentro del `try` sale del bloque protegido sin `TRY_END`
  explícito: cerrar el manejador en esa salida le corresponde al backend (decisión de diseño).
- **Arreglos:**
  - Literal `[e0, …, en-1]`: `t = NEW_ARR n` y un `ARR_SET t, i, ei` por elemento, en orden.
  - Un arreglo multidimensional es un arreglo cuyos elementos son arreglos: `m[i][j]` son dos
    `ARR_GET` encadenados y `m[i][j] = v` es un `ARR_GET` seguido de un `ARR_SET`.
- **Asignación a índice o atributo usada como valor** (`x = a[i] = v`): el valor de la expresión es
  `v`, sin otro temporal (decisión de diseño, igual que con variables).
- **Orden de evaluación con receptores e índices:** si un argumento, un índice o el valor asignado
  puede reescribir una variable ya leída como arreglo o receptor (por ejemplo, una llamada que
  modifica una global), esa variable se copia antes a un temporal.

## 11. Cuándo se genera IR

**Solo** si el análisis no tiene errores léxicos, sintácticos ni semánticos (`require_semantic_success`).
Las advertencias (`CPS-002`, `CPS-033`, `CPS-117`) no bloquean, porque el PDF bloquea por *errores*. La
invariante es estructural:

- `IRBuilder` solo se crea con un `RuntimeLayout`;
- un `RuntimeLayout` solo sale de `prepare()`;
- `prepare()` rechaza con `ValueError` cualquier resultado con errores.

## 12. API congelada

```python
from compiler.extended_semantics import SemanticResult          # = ExtendedSemanticResult
from compiler.runtime.runtime_layout import prepare, require_semantic_success, RuntimeLayout
from compiler.runtime.scoped_visitor import ScopedVisitor
from compiler.ir.builder import IRBuilder, IRError
from compiler.ir.serializer import serialize

layout = prepare(result)                  # RuntimeLayout
layout.labels / globals_count / functions / records / class_layouts
layout.scope_of(node) / enclosing_function(fn)
layout.ref_for(symbol, from_function)     # -> StorageRef
layout.link_hops(caller, callee)          # -> int | None

builder = IRBuilder(layout)
builder.new_temp(type) / release_temp(temp) / new_label(prefix) / mark_label(label)
builder.begin_function(fn) / end_function()
builder.emit(opcode, result=None, arg1=None, arg2=None, **metadata)
program = builder.build()                 # IRProgram
text = serialize(program)
```

`ScopedVisitor(symbols)` recorre el AST con el mismo scope que usó el collector. Expone `current_scope`,
`current_function` y `resolve(nombre)`. Para extenderlo, se sobrescribe `visit_<Nodo>` y se usa
`with self.enter(node):` en los nodos que abren scope. Los tests de `tests/ir/test_api_surface.py`
congelan estos nombres y firmas.

## 13. Ejemplos (salida real del builder)

**Aritmética y reciclaje.** `x = a + b * c; y = b - c;`: el segundo cálculo reutiliza `t0`.

```text
  t0 = BIN *, b@global[1], c@global[2]
  t1 = BIN +, a@global[0], t0
  MOV x@global[3], t1
  t0 = BIN -, b@global[1], c@global[2]
  MOV y@global[4], t0
```

**Cortocircuito.** `let r = p && q;`: no existe `BIN &&`.

```text
  MOV t0, p@global[0]
  IF_FALSE t0, L_and_end_0
  MOV t0, q@global[1]
LABEL L_and_end_0
  MOV r@global[2], t0
```

**Recursión.** `factorial(n)`: la llamada recursiva es un `CALL` normal.

```text
FUNC_BEGIN fn::factorial, frame=1
  t0 = BIN <=, n@frame[0], 1
  IF_FALSE t0, L_if_end_0
  RETURN 1
LABEL L_if_end_0
  t1 = BIN -, n@frame[0], 1
  ARG t1
  CALL t1, fn::factorial, argc=1
  t2 = BIN *, n@frame[0], t1
  RETURN t2
FUNC_END fn::factorial, temps=2
```

**Función anidada con captura.** `sumar` lee `total` del frame de `contador`
(`@frame^1`), y `contador` le pasa su propio frame (`link=0`).

```text
FUNC_BEGIN fn::contador.sumar, frame=1
  t0 = BIN +, total@frame^1[0], n@frame[0]
  RETURN t0
FUNC_END fn::contador.sumar, temps=1

FUNC_BEGIN fn::contador, frame=1
  MOV total@frame[0], 10
  ARG 5
  CALL t0, fn::contador.sumar, argc=1, link=0
  RETURN t0
FUNC_END fn::contador, temps=1
```

**Objetos, constructor y método.**

```text
  t0 = NEW_OBJ Animal, fields=1
  ARG t0
  ARG "Rex"
  CALL fn::Animal.constructor, argc=2
  MOV a@global[0], t0
  CALL_METHOD t1, a@global[0], hablar[0], argc=0
  PRINT t1

FUNC_BEGIN fn::Animal.constructor, frame=2
  SET_FIELD this@frame[0], nombre@field[0], n@frame[1]
  RETURN
FUNC_END fn::Animal.constructor, temps=0

FUNC_BEGIN fn::Animal.hablar, frame=1
  t0 = GET_FIELD this@frame[0], nombre@field[0]
  RETURN t0
FUNC_END fn::Animal.hablar, temps=1
```

**Arreglo y try/catch.** El índice fuera de rango queda para el runtime: no hay chequeo estático de
límites.

```text
  t0 = NEW_ARR 2
  ARR_SET t0, 0, 1
  ARR_SET t0, 1, 2
  MOV arr@global[0], t0
  TRY_BEGIN L_try_handler_0
  t1 = ARR_GET arr@global[0], 5
  PRINT t1
  TRY_END
  GOTO L_try_end_1
LABEL L_try_handler_0
  CATCH err@global[1]
  PRINT err@global[1]
LABEL L_try_end_1
```

## 14. Supuestos y límites

- **Sin `float`.** Es una decisión deliberada del proyecto: `integer` es el único tipo numérico.
- **`null`** es un valor de referencia: es asignable a clases y arreglos.
- **Strings:** la gramática no define escapes, así que el valor del literal es el texto crudo entre
  comillas. Al serializarlo se escapa estilo JSON solo para que el TAC sea legible y no ambiguo.
- **Excepciones:** no hay `throw` en la gramática; `CATCH` solo recibe lo que el runtime levante (por
  ejemplo, un índice fuera de rango). La variable del `catch` es `string` (`CATCH_VAR_TYPE`).
- **Clases locales:** una clase declarada dentro de una función o bloque es error (`CPS-024`), así que no
  hay IR para ese caso.
- **Ejecución:** nada en este proyecto ejecuta, interpreta ni traduce el TAC a assembler. La semántica
  descrita aquí es la que un backend futuro tendría que respetar.
