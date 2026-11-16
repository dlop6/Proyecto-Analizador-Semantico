// funciones anidadas: lectura y escritura de variables de frames que las encierran (static link)
function banco(inicial: integer): integer {
    let saldo: integer = inicial;
    function depositar(monto: integer) {
        saldo = saldo + monto;
    }
    function retirar(monto: integer): boolean {
        function alcanza(): boolean {
            return saldo >= monto;
        }
        if (alcanza()) {
            saldo = saldo - monto;
            return true;
        }
        return false;
    }
    depositar(50);
    print(retirar(30));
    print(retirar(500));
    depositar(5);
    return saldo;
}
function contarHasta(limite: integer): integer {
    let total: integer = 0;
    function paso(k: integer) {
        if (k > limite) {
            return;
        }
        total = total + k;
        paso(k + 1);
    }
    paso(1);
    return total;
}
print(banco(100));
print(contarHasta(10));
