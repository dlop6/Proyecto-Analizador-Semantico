// mas de 8 temporales vivos a la vez: el allocator hace spill y reload sin perder valores
let a: integer = 2;
let b: integer = 3;
let r: integer = (a * 1) + ((b * 2) + ((a * 3) + ((b * 4) + ((a * 5) + ((b * 6) + ((a * 7) + ((b * 8) + ((a * 9) + ((b * 10) + ((a * 11) + (b * 12)))))))))));
print(r);
function f(x: integer): integer {
    return x + 1;
}
print((a + 1) * ((b + 2) * ((a + 3) * ((b + 4) * ((a + f(5)) * ((b + f(6)) * ((a + 7) * ((b + 8) * (a + 9)))))))));
