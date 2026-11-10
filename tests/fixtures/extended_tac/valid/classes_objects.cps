// clase con constructor, atributos y metodos; new, GET_FIELD, SET_FIELD y CALL_METHOD
class Punto {
  let x: integer;
  let y: integer;
  function constructor(x: integer, y: integer) {
    this.x = x;
    this.y = y;
  }
  function suma(): integer {
    return this.x + this.y;
  }
  function mover(dx: integer) {
    this.x = this.x + dx;
  }
}
let p: Punto = new Punto(3, 4);
p.mover(2);
p.y = 10;
print(p.suma());
print(p.x);
