// switch sin fallthrough: una sola rama, cada rama termina en GOTO al final
let opcion: integer = 2;
switch (opcion) {
    case 1:
        print("uno");
    case 2:
        print("dos");
        break;
    default:
        print("otro");
}
switch (opcion * 2) {
    case 4:
        print("cuatro");
}
let i: integer = 0;
while (i < 3) {
    i = i + 1;
    switch (i) {
        case 2:
            continue;
        default:
            print(i);
    }
}
