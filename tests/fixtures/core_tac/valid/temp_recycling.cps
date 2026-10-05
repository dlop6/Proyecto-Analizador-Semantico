// reciclaje: cada sentencia reutiliza los temporales liberados por la anterior
let a: integer = 1;
let b: integer = 2;
let c: integer = 3;
let d: integer = 4;
let x: integer = a * b + c * d;
let y: integer = (a + b) * (c + d) - (a - d);
let z: integer = a * b * c * d;
let w: boolean = a < b && c < d;
