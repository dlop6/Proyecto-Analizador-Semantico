// && y || con cortocircuito: nunca hay BIN && ni BIN ||
let p: boolean = true;
let q: boolean = false;
let x: integer = 5;
let y: boolean = p && q;
let z: boolean = p || q;
let mixto: boolean = x > 0 && x < 10 || !p;
let anidado: boolean = (p || q) && (x == 5 || q);
