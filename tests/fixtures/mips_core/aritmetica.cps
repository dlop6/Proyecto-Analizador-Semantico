// + - * / % con precedencia, negativos (truncan hacia cero) y desborde de 32 bits
let a: integer = 17;
let b: integer = 5;
print(a + b * 2);
print((a + b) * 2);
print(a - b - 2);
print(a / b);
print(a % b);
print(-a / b);
print(-a % b);
print(a * -b);
print(-(a - 20));
print(2147483647 + 1);
print(1000 * 1000 * 1000 * 3);
let promedio: integer = (a + b + 12) / 3;
print(promedio);
