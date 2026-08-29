let total: integer = 0;

for (let i: integer = 0; i < 5; i = i + 1) {
  if (i == 3) {
    continue;
  }
  total = total + i;
}

let j: integer = 0;
while (j < 3) {
  j = j + 1;
}

do {
  j = j - 1;
} while (j > 0);

switch (total) {
  case 1:
    print("uno");
  case 2:
    print("dos");
  default:
    print("otro");
}

try {
  let riesgo: integer = total;
  print(riesgo);
} catch (err) {
  print(err);
}
