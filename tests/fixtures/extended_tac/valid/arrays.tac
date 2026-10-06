  t0 = NEW_ARR 3
  ARR_SET t0, 0, 10
  ARR_SET t0, 1, 20
  ARR_SET t0, 2, 30
  MOV numeros@global[0], t0
  MOV i@global[1], 1
  t1 = ARR_GET numeros@global[0], i@global[1]
  t2 = ARR_GET numeros@global[0], 0
  t3 = BIN +, t1, t2
  MOV x@global[2], t3
  t1 = BIN *, x@global[2], 2
  ARR_SET numeros@global[0], 2, t1
  t0 = NEW_ARR 0
  MOV vacio@global[3], t0
  t1 = ARR_GET numeros@global[0], 2
  PRINT t1
