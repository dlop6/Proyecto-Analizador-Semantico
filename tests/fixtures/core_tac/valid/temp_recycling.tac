  MOV a@global[0], 1
  MOV b@global[1], 2
  MOV c@global[2], 3
  MOV d@global[3], 4
  t0 = BIN *, a@global[0], b@global[1]
  t1 = BIN *, c@global[2], d@global[3]
  t2 = BIN +, t0, t1
  MOV x@global[4], t2
  t0 = BIN +, a@global[0], b@global[1]
  t1 = BIN +, c@global[2], d@global[3]
  t2 = BIN *, t0, t1
  t0 = BIN -, a@global[0], d@global[3]
  t1 = BIN -, t2, t0
  MOV y@global[5], t1
  t0 = BIN *, a@global[0], b@global[1]
  t1 = BIN *, t0, c@global[2]
  t0 = BIN *, t1, d@global[3]
  MOV z@global[6], t0
  t3 = BIN <, a@global[0], b@global[1]
  IF_FALSE t3, L_and_end_0
  t4 = BIN <, c@global[2], d@global[3]
  MOV t3, t4
LABEL L_and_end_0
  MOV w@global[7], t3
