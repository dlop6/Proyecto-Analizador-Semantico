"""clases, objetos y herencia en mars: campos, constructor, this, vtable, override y despacho."""
from .support import output


def test_constructor_this_campos_y_metodos():
    assert output("""
    class Cuenta {
        let saldo: integer = 100;
        let duenio: string;
        function constructor(duenio: string) { this.duenio = duenio; }
        function depositar(monto: integer): integer { this.saldo = this.saldo + monto; return this.saldo; }
        function resumen(): string { return this.duenio + ": " + this.saldo; }
    }
    let c: Cuenta = new Cuenta("ana");
    print(c.depositar(50));
    print(c.resumen());
    """) == ["150", "ana: 150"]


def test_cada_objeto_tiene_sus_propios_campos():
    assert output("""
    class P { let v: integer = 0; }
    let a: P = new P();
    let b: P = new P();
    a.v = 1;
    b.v = 2;
    print(a.v);
    print(b.v);
    """) == ["1", "2"]


def test_campos_heredados_conservan_su_offset_en_la_subclase():
    assert output("""
    class Base { let a: integer = 1; let b: integer = 2; }
    class Hija : Base { let c: integer = 3; function total(): integer { return this.a + this.b + this.c; } }
    let h: Hija = new Hija();
    h.a = 10;
    print(h.total());
    """) == ["15"]


def test_override_sobre_instancia_hija_referenciada_como_padre():
    assert output("""
    class Animal {
        function sonido(): string { return "..."; }
        function hablar(): string { return "dice " + this.sonido(); }
    }
    class Perro : Animal { function sonido(): string { return "guau"; } }
    class Gato : Animal { function sonido(): string { return "miau"; } }
    let animales: Animal[] = [new Animal(), new Perro(), new Gato()];
    foreach (a in animales) { print(a.hablar()); }
    """) == ["dice ...", "dice guau", "dice miau"]


def test_metodo_heredado_sin_override_y_tres_niveles():
    assert output("""
    class A { function nombre(): string { return "A"; } function saludo(): string { return "hola " + this.nombre(); } }
    class B : A { function nombre(): string { return "B"; } }
    class C : B { }
    let c: A = new C();
    print(c.saludo());
    let b: B = new C();
    print(b.nombre());
    """) == ["hola B", "B"]


def test_constructor_heredado_del_padre():
    # decision documentada en BASELINE_P3.md: el proyecto hereda constructores (program.cps oficial)
    assert output("""
    class Animal { let nombre: string; function constructor(nombre: string) { this.nombre = nombre; } }
    class Perro : Animal { function ladrar(): string { return this.nombre + " ladra"; } }
    let p: Perro = new Perro("Rex");
    print(p.ladrar());
    """) == ["Rex ladra"]


def test_metodo_recursivo_y_con_varios_argumentos():
    assert output("""
    class Mat {
        function fact(n: integer): integer { if (n <= 1) { return 1; } return n * this.fact(n - 1); }
        function suma(a: integer, b: integer, c: integer, d: integer, e: integer): integer { return a + b + c + d + e; }
    }
    let m: Mat = new Mat();
    print(m.fact(6));
    print(m.suma(1, 2, 3, 4, 5));
    """) == ["720", "15"]


def test_objeto_null_al_leer_escribir_y_llamar():
    assert output("""
    class A { let x: integer = 1; function m(): integer { return 2; } }
    let a: A = null;
    try { print(a.x); } catch (e) { print("leer: " + e); }
    try { a.x = 5; } catch (e) { print("escribir: " + e); }
    try { print(a.m()); } catch (e) { print("llamar: " + e); }
    """) == ["leer: acceso a null", "escribir: acceso a null", "llamar: acceso a null"]


def test_imprimir_una_referencia():
    assert output("""
    class A {}
    let a: A = new A();
    let b: A = null;
    print(a);
    print(b);
    """) == ["<A>", "null"]
