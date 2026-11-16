# Registros y árboles de activación — evidencia de ejecución

Este documento muestra los registros y árboles de activación del código que genera `CoreMipsBackend`. Todos salen de **ejecutar el `.asm` en MARS 4.5**. No se dibujan a partir del grafo de llamadas estático. `tests/person2_mips/test_activation_tree.py` vuelve a ejecutar cada ejemplo y falla si los árboles de este archivo dejan de coincidir con la ejecución.

## Cómo se obtiene la traza

`TracingBackend` (en `tests/person2_mips/support.py`) es una subclase **de prueba** de `CoreMipsBackend`. El backend del producto no cambia: la subclase sobrescribe solo dos handlers y agrega syscalls de impresión.

| Momento | Quién imprime | Línea |
|---|---|---|
| justo después del prólogo del llamado (`FUNC_BEGIN`) | el llamado, leyendo sus parámetros de `offset($fp)` | `enter fn::fib 4` |
| a continuación | el llamado: su `$fp` y, si tiene, el static link (`8($fp)`) | `frame fn::fib 2147479528` |
| al volver del `jal` (`CALL`) | el que llama, leyendo `$v0` | `exit fn::fib 3` |

Las syscalls de MARS no tocan los registros `$t`, así que la traza no altera el allocator ni el resultado. `activation_tree()` reconstruye el árbol con una pila: cada `enter` abre un nodo hijo del nodo abierto y cada `exit` lo cierra con su valor de retorno. Si un `exit` no corresponde al nodo abierto, el test falla.

```bash
pytest tests/person2_mips/test_activation_tree.py -q
```

## Registro de activación de `fib`

`FramePlanner` calcula el layout y `ActivationEmitter` arma el prólogo y el epílogo (base del backend, ver `docs/BACKEND_MIPS.md` §3-§5). Para `fib(n)`:

| Offset desde `$fp` | Contenido | Quién lo escribe |
|---|---|---|
| `+8` | `n` (argumento 0) | el que llama, antes del `jal` |
| `+4` | `$ra` guardado | prólogo |
| `0` | `$fp` del que llama | prólogo |
| `-4 .. -16` | home de `t0..t3` | el allocator, solo si un temporal sigue vivo a través de una llamada o un salto |
| `-20` | casilla de argumento pendiente | `ARG` |

Cada nivel de recursión ocupa **32 bytes** de pila: 4 del argumento, 8 de `$ra`/`$fp` y 20 del frame. Para `fib`, el tramo central del código generado es:

```
fn_fib:
    addi $sp, $sp, -8
    sw $ra, 4($sp)
    sw $fp, 0($sp)
    move $fp, $sp
    addi $sp, $sp, -20
    ...
    jal fn_fib
    addi $sp, $sp, 4
    move $t0, $v0
    sw $t0, -8($fp)    # guarda t1
    bne $v1, $zero, fn_fib_exit
    ...
    lw $t1, -8($fp)    # recarga t1
    addu $t2, $t1, $t0
```

`fib(n-1)` tiene que sobrevivir a la segunda llamada. Por eso se guarda en su home (`-8($fp)`) y se recarga después: los `$t` son *caller-saved*.

## Ejemplo 1 — recursión: `fib(4)`

```
function fib(n: integer): integer {
    if (n < 2) { return n; }
    return fib(n - 1) + fib(n - 2);
}
print(fib(4));
```

Salida del programa: `3`. Árbol reconstruido de la ejecución:

```
main
    fn::fib(4) -> 3
        fn::fib(3) -> 2
            fn::fib(2) -> 1
                fn::fib(1) -> 1
                fn::fib(0) -> 0
            fn::fib(1) -> 1
        fn::fib(2) -> 1
            fn::fib(1) -> 1
            fn::fib(0) -> 0
```

La ejecución hace 9 activaciones de `fib` y llega a una profundidad máxima de 5 contando `main`. El `$fp` de cada activación, tomado de la misma ejecución:

| Activación | `$fp` |
|---|---|
| `fib(4)` | `0x7fffefe8` |
| `fib(3)` / `fib(2)` (hermanos) | `0x7fffefc8` |
| `fib(2)`, `fib(1)`, `fib(0)` en el tercer nivel | `0x7fffefa8` |
| `fib(1)` / `fib(0)` en el cuarto nivel | `0x7fffef88` |

- Cada hijo vive 32 bytes por debajo de su padre.
- Dos llamadas **hermanas** obtienen el **mismo** `$fp`. Cuando la primera retorna, el que llama ya limpió su bloque de argumentos, así que la segunda arranca con el mismo `$sp`.
- Al terminar, `$fp` vuelve a `0x7fffeffc`, el valor inicial de MARS, y `$sp` queda donde lo dejó el prólogo de `main`. La pila queda balanceada.

## Ejemplo 2 — función anidada: static link

```
function potencia(base: integer, exp: integer): integer {
    function paso(k: integer): integer {
        if (k == 0) { return 1; }
        return base * paso(k - 1);
    }
    return paso(exp);
}
print(potencia(2, 3));
```

Salida: `8`. `paso` lee `base` del frame de `potencia` (`base@frame^1[0]`). Por eso recibe un static link como argumento implícito 0 (`8($fp)`), y su parámetro `k` pasa a `12($fp)`.

```
main
    fn::potencia(2, 3) -> 8
        fn::potencia.paso(3) -> 8
            fn::potencia.paso(2) -> 4
                fn::potencia.paso(1) -> 2
                    fn::potencia.paso(0) -> 1
```

| Activación | `$fp` | static link recibido |
|---|---|---|
| `potencia(2, 3)` | `0x7fffefe0` | — (top-level) |
| `paso(3)` | `0x7fffefc8` | `0x7fffefe0` |
| `paso(2)` | `0x7fffefa4` | `0x7fffefe0` |
| `paso(1)` | `0x7fffef80` | `0x7fffefe0` |
| `paso(0)` | `0x7fffef5c` | `0x7fffefe0` |

Esta tabla separa la **cadena dinámica** de la **cadena estática**. `paso(2)` la llama `paso(3)` (enlace dinámico: su `$fp` viejo es `0x7fffefc8`). Su static link, en cambio, es el frame de `potencia`, donde vive `base`. El `CALL` recursivo lleva `link=1`: el backend sigue un enlace desde el frame actual antes de pasarlo. Cada nivel de `paso` ocupa 36 bytes: el static link, `k`, `$ra`/`$fp` y un frame de 20.

## Ejemplo 3 — varias funciones en secuencia

```
function cuadrado(x: integer): integer { return x * x; }
function sumaCuadrados(a: integer, b: integer): integer { return cuadrado(a) + cuadrado(b); }
function factorial(n: integer): integer { if (n <= 1) { return 1; } return n * factorial(n - 1); }
print(sumaCuadrados(3, 4));
print(factorial(3));
```

Salida: `25` y `6`.

```
main
    fn::sumaCuadrados(3, 4) -> 25
        fn::cuadrado(3) -> 9
        fn::cuadrado(4) -> 16
    fn::factorial(3) -> 6
        fn::factorial(2) -> 2
            fn::factorial(1) -> 1
```

## Otras pruebas del registro de activación (MARS)

| Qué se verifica | Test |
|---|---|
| aridades 0, 1, 4 y 5, y orden de los argumentos | `test_functions_mars.py::test_aridades_y_orden_de_los_argumentos` |
| argumentos que son llamadas (`f(g(1), g(g(2)))`) | `test_argumentos_con_llamadas_anidadas` |
| recursión directa, mutua (`esPar`/`esImpar`) y de Ackermann | `test_factorial_y_fibonacci_recursivos`, `test_recursion_mutua`, `test_ackermann_...` |
| 2000 niveles de recursión sin corromper la pila | `test_recursion_profunda_no_corrompe_la_pila` |
| static link de profundidad 3 y escritura a variables de otro frame | `test_static_link_de_profundidad_tres`, `test_anidadas_leen_y_escriben_...` |
| `$sp` y `$fp` balanceados después de 30 niveles con llamadas anidadas | `test_sp_y_fp_quedan_como_los_dejo_el_prologo_de_main` |
| valores vivos que sobreviven a varias llamadas | `test_valores_vivos_se_conservan_a_traves_de_llamadas` |
| un error de runtime (`$v1 = 1`) atraviesa dos frames hasta `main_error` | `test_error_se_propaga_por_dos_funciones_y_corta_la_ejecucion` |
