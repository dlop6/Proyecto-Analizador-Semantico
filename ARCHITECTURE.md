# Arquitectura del compilador Compiscript (analisis semantico + codigo intermedio)

## Flujo de compilacion

El punto de entrada para clientes es `compiler.compiler_service.compile_source`:

```
source -> frontend -> core_semantics <-> extended_semantics          (analisis)
       -> runtime_layout.prepare -> ExtendedTacGenerator -> serialize  (codigo intermedio)
       -> CompilationResult(success, diagnostics, ast_svg, tac_text, symbols) -> IDE
```

1. **Frontend.** `frontend.analyze_source` ejecuta ANTLR, construye el AST propio y
   recolecta simbolos. Ante un error lexico o sintactico no construye AST.
2. **Semantica core.** `core_semantics.analyze` resuelve nombres por scope, tipos
   primitivos, funciones, retornos y control de flujo. Un nombre de función o clase
   usado como valor se rechaza con `CPS-119`.
3. **Semantica extendida.** `extended_semantics.analyze` completa clases, miembros,
   `new`, arreglos e indices. Como esos tipos pueden ser hijos de expresiones core,
   alterna las pasadas core y extendida hasta estabilizar los tipos del AST y de los
   simbolos. Asi una condicion, llamada, return u operador se valida con el tipo final.
4. **Modelo de runtime.** Solo si no hubo ningun error, `runtime_layout.prepare` asigna
   slots abstractos (globales, frames, campos), etiquetas de funcion, registros de
   activacion (con static link) y layouts de clase, y los escribe en la misma tabla de
   simbolos.
5. **Codigo intermedio.** `ExtendedTacGenerator.generate` recorre el AST ya validado y
   emite `TACInstruction` estructuradas a traves de `IRBuilder`; `serialize` produce el
   texto que muestra la GUI.
6. **Integracion.** `compiler_service` compone las etapas y pide el SVG a Graphviz.
   Si `dot` no esta disponible, la compilacion conserva sus diagnosticos y el SVG es
   `None`.

Las fachadas mantienen sus contratos: `FrontendResult`, `CoreSemanticResult`,
`ExtendedSemanticResult` (alias `SemanticResult`), `RuntimeLayout`, `IRProgram` y
`CompilationResult` no reconstruyen el AST ni la tabla de simbolos entre etapas.

**Invariante de seguridad.** Con cualquier error lexico, sintactico o semantico no se
genera IR: `compile_source` devuelve `tac_text=None` sin llamar a `prepare`, `prepare`
rechaza un resultado con errores (`ValueError`) y `IRBuilder` solo se construye con un
`RuntimeLayout`. Las advertencias no bloquean.

## AST, scopes y simbolos

El AST vive en `compiler/ast_nodes.py`; cada expresion contiene `inferred_type`, que
las pasadas semanticas completan in-place. `SymbolTable` contiene un arbol de `Scope`:

```
GLOBAL
  FUNCTION / CLASS / BLOCK / LOOP / CATCH / SWITCH
```

`Scope.lookup` busca primero el scope local y luego sus padres. Las clases y funciones
top-level se predeclaran para recursividad y referencias posteriores. Una funcion
anidada se declara en su scope contenedor antes de recorrer su propio cuerpo: permite
autorrecursion y closures basicos de simbolos ya declarados en un scope padre. No hay
hoisting de funciones hermanas ni captura de variables declaradas despues de la funcion
anidada. `this` solo existe en scopes de metodos y constructores.

## Tipos y semantica

`types.py` es la capa inferior y no depende del AST ni de simbolos. Soporta `integer`,
`string`, `boolean`, `null`, clases, arreglos, `void` y el tipo interno de error.

- No existe `float`: es una decision deliberada del proyecto.
- `null` es asignable solo a referencias (clases y arreglos).
- Las clases admiten subtipado nominal hacia el padre.
- Los arreglos son invariantes.
- El ancestro comun de clases se calcula recorriendo ambas cadenas de herencia.
- `[]` requiere contexto de una anotacion de arreglo; sin ella reporta `CPS-214`.
- Un método leído sin invocarlo reporta `CPS-215`; Compiscript no tiene métodos ni
  funciones de primera clase.
- `foreach` exige `ArrayType(T)` y asigna `T` a su variable de iteración. Un iterable
  no-arreglo o `[]` sin tipo de elemento reporta `CPS-120`; la revalidación detecta
  también propiedades, índices, llamadas y construcciones tipadas después de core.
- Una clase sin constructor propio usa el del ancestro mas cercano que lo declare
  (como `new Dog("Rex")` en el ejemplo oficial); si ninguno lo declara, solo acepta cero
  argumentos. Metodos y atributos tambien usan lookup heredado.
- `+` concatena un `string` con otro `string`, un `integer` o un `boolean`, como en el
  ejemplo oficial; el resto de operadores aritmeticos es solo numerico.

Las reglas puras de expresiones, funciones, control de flujo, clases y arreglos devuelven
tipos y codigos; los visitors son los unicos que escriben diagnosticos con posicion.
La estabilizacion entre core y extendida reutiliza esas reglas, sin un segundo sistema de
tipos ni analisis de flujo avanzado.

## Diagnosticos

Los diagnosticos son `Diagnostic(code, message, line, column)` y se ordenan por linea,
columna y codigo. Los rangos son:

| Rango | Propietario | Ejemplos |
|---|---|---|
| `CPS-0xx` | Frontend | sintaxis, scopes, simbolos, herencia |
| `CPS-1xx` | Semantica core | asignaciones, operadores, llamadas, retornos |
| `CPS-2xx` | Semantica extendida | miembros, arreglos, constructores |

`CPS-214` indica un literal de arreglo vacio sin tipo de contexto. `CPS-102` se reutiliza
para cualquier reasignacion de constante, incluidos atributos `const`.
`CPS-119` y `CPS-120` son diagnósticos core; `CPS-215` pertenece a la semántica
extendida.

## Codigo intermedio (TAC)

La especificacion completa del lenguaje intermedio (gramatica textual, los 24 opcodes,
temporales, etiquetas, almacenamiento y convenciones de lowering) esta en
`docs/INTERMEDIATE_CODE.md`. Las piezas y sus responsabilidades:

| Modulo | Responsabilidad |
|---|---|
| `ir/opcodes.py`, `ir/model.py` | contrato cerrado de opcodes y operandos; cada instruccion es un objeto |
| `ir/builder.py` | unica forma de emitir: valida roles de operandos, temporales vivos y etiquetas |
| `ir/temp_manager.py`, `ir/label_manager.py` | temporales por unidad con reciclaje por categoria; etiquetas deterministas |
| `ir/serializer.py` | unica serializacion a texto |
| `runtime/*` | slots, registros de activacion, static links y layouts de clase |
| `tac/core_generator.py` + 3 mixins | TAC core: expresiones, control de flujo, funciones |
| `tac/extended_generator.py` + 3 mixins | TAC extendido: arreglos, objetos, herencia, try/catch |

Los generadores se componen por herencia de mixins, una familia de construcciones por
modulo (SRP):

```
CoreTacGenerator(ExpressionLowering, ControlFlowLowering, FunctionLowering, ScopedVisitor)
ExtendedTacGenerator(ArrayLowering, ObjectLowering, ExceptionLowering, CoreTacGenerator)
```

- **LSP.** `ExtendedTacGenerator` solo reemplaza los `visit_` y los ganchos
  (`lower_member_assignment`, `lower_method_call`) que en el core terminaban en
  `UnsupportedConstructError`. Para cualquier programa core produce exactamente el mismo
  IR; un test lo compara contra todas las fixtures doradas del core.
- **Sin segunda fuente de verdad.** Los generadores no validan tipos ni nombres, no crean
  tablas de simbolos ni managers y no arman texto TAC a mano. Los nombres se resuelven con
  `ScopedVisitor` (los mismos scopes que el collector), el almacenamiento con
  `RuntimeLayout.ref_for` y la herencia con el `ClassLayout` ya aplanado: el generador
  extendido nunca recorre la jerarquia de clases. Tests de arquitectura lo hacen cumplir.
- **Temporales.** Quien recibe un temporal lo libera tras su ultimo uso; el resultado se
  pide antes de liberar operandos. `foreach` mantiene vivos arreglo, indice y longitud
  durante el cuerpo. El pico por funcion queda en `FUNC_END temps=k`.

## IDE

El IDE Flask solo delega en `compile_source`. El cliente construye diagnosticos con
`textContent`, por lo que el codigo fuente del usuario nunca se interpreta como HTML.
El editor conserva un `textarea` como fuente de verdad y una capa visual sincronizada
de resaltado léxico y números de línea. Esta capa solo reconoce tokens de la gramática:
no consulta símbolos ni decide validez semántica. Todas las respuestas de la API incluyen
`success`, `diagnostics`, `ast_svg`, `tac_text`, `symbols` y `error`. El limite HTTP se aplica antes de
deserializar JSON, y el compilador conserva su limite de fuente como segunda defensa.
El selector `.cps` lee localmente con `FileReader`, valida extensión y tamaño con el
mismo límite del compilador y solo envía el texto al servidor cuando el usuario pulsa
“Compilar”. La UI permite navegar diagnósticos, filtrarlos, copiarlos y controlar el SVG
sin cambiar la API ni los contratos públicos.

La pestaña TAC solo presenta el texto que ya serializo el backend (por `textContent`,
linea por linea). Si la respuesta no trae TAC, por errores o por un fallo de red, el
panel se vacia y muestra "No generado por errores": nunca queda visible el TAC de una
compilacion anterior. La pestaña de simbolos muestra la informacion de runtime que
`prepare` escribio en la tabla (slots, etiquetas, frames, layouts).

## Limites intencionales

Se sigue KISS/YAGNI: no hay float, optimizador, interprete, debugger, persistencia,
autenticacion, autocompletado, rate limiting, CFG ni analisis de flujo avanzado. El TAC
no se ejecuta, no se traduce a assembler y no se genera codigo objeto; no hay SSA,
constant folding ni eliminacion de codigo muerto: el unico manejo de recursos es el
reciclaje de temporales.

## Pendientes docentes

No se cambia `float`, `switch` ni `break` hasta confirmar contradicciones entre los
requisitos semánticos, la gramática y los ejemplos oficiales. El comportamiento actual
se conserva y está documentado en el README. La concatenación `string + integer` y los
constructores heredados siguen al ejemplo oficial `program/program.cps`, que compila y
genera TAC.
