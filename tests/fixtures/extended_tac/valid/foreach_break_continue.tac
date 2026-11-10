  t0 = NEW_ARR 2
  t1 = NEW_ARR 3
  ARR_SET t1, 0, 1
  ARR_SET t1, 1, 2
  ARR_SET t1, 2, 3
  ARR_SET t0, 0, t1
  t1 = NEW_ARR 3
  ARR_SET t1, 0, 4
  ARR_SET t1, 1, 5
  ARR_SET t1, 2, 6
  ARR_SET t0, 1, t1
  MOV tabla@global[0], t0
  MOV total@global[1], 0
  MOV t0, tabla@global[0]
  MOV t2, 0
  t3 = LEN t0
LABEL L_foreach_cond_0
  t4 = BIN <, t2, t3
  IF_FALSE t4, L_foreach_end_2
  t1 = ARR_GET t0, t2
  MOV fila@global[2], t1
  MOV t1, fila@global[2]
  MOV t5, 0
  t6 = LEN t1
LABEL L_foreach_cond_3
  t4 = BIN <, t5, t6
  IF_FALSE t4, L_foreach_end_5
  t7 = ARR_GET t1, t5
  MOV valor@global[3], t7
  t4 = BIN ==, valor@global[3], 2
  IF_FALSE t4, L_if_end_6
  GOTO L_foreach_step_4
LABEL L_if_end_6
  t4 = BIN >, valor@global[3], 5
  IF_FALSE t4, L_if_end_7
  GOTO L_foreach_end_5
LABEL L_if_end_7
  t7 = BIN +, total@global[1], valor@global[3]
  MOV total@global[1], t7
LABEL L_foreach_step_4
  t5 = BIN +, t5, 1
  GOTO L_foreach_cond_3
LABEL L_foreach_end_5
LABEL L_foreach_step_1
  t2 = BIN +, t2, 1
  GOTO L_foreach_cond_0
LABEL L_foreach_end_2
  PRINT total@global[1]
