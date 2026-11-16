// recursion directa, mutua y con dos llamadas recursivas por activacion
function factorial(n: integer): integer {
    if (n <= 1) {
        return 1;
    }
    return n * factorial(n - 1);
}
function fibonacci(n: integer): integer {
    if (n < 2) {
        return n;
    }
    return fibonacci(n - 1) + fibonacci(n - 2);
}
function esPar(n: integer): boolean {
    if (n == 0) {
        return true;
    }
    return esImpar(n - 1);
}
function esImpar(n: integer): boolean {
    if (n == 0) {
        return false;
    }
    return esPar(n - 1);
}
function mcd(a: integer, b: integer): integer {
    if (b == 0) {
        return a;
    }
    return mcd(b, a % b);
}
function hanoi(n: integer): integer {
    if (n == 0) {
        return 0;
    }
    return hanoi(n - 1) * 2 + 1;
}
for (let i: integer = 0; i <= 10; i = i + 2) {
    print("fib(" + i + ") = " + fibonacci(i));
}
print(factorial(10));
print(esPar(15));
print(esImpar(15));
print(mcd(1071, 462));
print(hanoi(10));
