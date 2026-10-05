// break y continue siempre saltan al bucle mas interno
let i: integer = 0;
while (i < 10) {
    i = i + 1;
    if (i % 2 == 0) {
        continue;
    }
    for (let j: integer = 0; j < i; j = j + 1) {
        if (j == 3) {
            break;
        }
        if (j == 1) {
            continue;
        }
        print(j);
    }
    do {
        if (i > 7) {
            break;
        }
        continue;
    } while (false);
    if (i > 8) {
        break;
    }
}
