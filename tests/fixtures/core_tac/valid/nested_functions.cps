// funciones anidadas: alcance lexico con static link (NONLOCAL @frame^k y link=k)
function externa(base: integer): integer {
    let acumulado: integer = 0;
    function sumar(n: integer): integer {
        acumulado = acumulado + n;
        function escalar(): integer {
            return acumulado * base;
        }
        return escalar();
    }
    function doble(n: integer): integer {
        return n * 2;
    }
    sumar(1);
    return sumar(doble(base));
}
print(externa(3));
