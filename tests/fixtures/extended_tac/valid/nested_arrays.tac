  t0 = NEW_ARR 2
  t1 = NEW_ARR 2
  ARR_SET t1, 0, 1
  ARR_SET t1, 1, 2
  ARR_SET t0, 0, t1
  t1 = NEW_ARR 2
  ARR_SET t1, 0, 3
  ARR_SET t1, 1, 4
  ARR_SET t0, 1, t1
  MOV matriz@global[0], t0
  t0 = ARR_GET matriz@global[0], 1
  t1 = ARR_GET matriz@global[0], 0
  t2 = ARR_GET t1, 1
  t3 = BIN +, t2, 5
  ARR_SET t0, 0, t3
  t0 = ARR_GET matriz@global[0], 1
  MOV fila@global[1], t0
  t2 = ARR_GET fila@global[1], 0
  PRINT t2
