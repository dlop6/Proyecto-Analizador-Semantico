// errores semanticos de clases: miembro inexistente, aridad del constructor y override
class A {
  function constructor(n: integer) {}
  function m(): integer { return 1; }
}
class B : A {
  function m(): string { return "x"; }
}
let a: A = new A();
print(a.noExiste);
a.m(1);
