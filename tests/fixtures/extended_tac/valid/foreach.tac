  t0 = NEW_ARR 3
  ARR_SET t0, 0, "ana"
  ARR_SET t0, 1, "beto"
  ARR_SET t0, 2, "carla"
  MOV nombres@global[0], t0
  MOV saludo@global[1], ""
  MOV t0, nombres@global[0]
  MOV t1, 0
  t2 = LEN t0
LABEL L_foreach_cond_0
  t3 = BIN <, t1, t2
  IF_FALSE t3, L_foreach_end_2
  t4 = ARR_GET t0, t1
  MOV nombre@global[2], t4
  t4 = BIN +, saludo@global[1], nombre@global[2]
  MOV saludo@global[1], t4
  PRINT nombre@global[2]
LABEL L_foreach_step_1
  t1 = BIN +, t1, 1
  GOTO L_foreach_cond_0
LABEL L_foreach_end_2
  PRINT saludo@global[1]
