// optimizacion por mirilla sobre codigo real: x + 0 deja un addiu r, s, 0 (R3) y los
// switch / if sin else dejan saltos a la etiqueta siguiente (R6)
let x: integer = 5;
let y: integer = x + 0;
let z: integer = y - 0;
print(z);
switch (z) {
  case 5:
    print("cinco");
  case 6:
    print("seis");
  default:
    print("otro");
}
if (z > 3) {
  print("mayor");
} else {
  print("menor");
}
