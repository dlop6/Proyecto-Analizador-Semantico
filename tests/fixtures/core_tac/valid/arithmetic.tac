  MOV a@global[0], 10
  MOV b@global[1], 3
  MOV c@global[2], 2
  t0 = BIN *, b@global[1], c@global[2]
  t1 = BIN +, a@global[0], t0
  t0 = BIN /, a@global[0], b@global[1]
  t2 = BIN %, t0, c@global[2]
  t0 = BIN -, t1, t2
  MOV r1@global[3], t0
  t0 = BIN -, a@global[0], b@global[1]
  t1 = UN -, t0
  t0 = UN -, c@global[2]
  t2 = BIN *, t1, t0
  MOV r2@global[4], t2
  t3 = BIN <, a@global[0], b@global[1]
  MOV menor@global[5], t3
  t0 = BIN +, a@global[0], 1
  t1 = BIN *, b@global[1], c@global[2]
  t3 = BIN !=, t0, t1
  MOV distinto@global[6], t3
  t3 = BIN >=, a@global[0], c@global[2]
  MOV mayorIgual@global[7], t3
  t4 = BIN +, "hola ", "mundo"
  MOV saludo@global[8], t4
  t3 = UN !, menor@global[5]
  MOV negado@global[9], t3
