  MOV i@global[0], 0
LABEL L_while_cond_0
  t0 = BIN <, i@global[0], 10
  IF_FALSE t0, L_while_end_1
  t1 = BIN +, i@global[0], 1
  MOV i@global[0], t1
  t1 = BIN %, i@global[0], 2
  t0 = BIN ==, t1, 0
  IF_FALSE t0, L_if_end_2
  GOTO L_while_cond_0
LABEL L_if_end_2
  MOV j@global[1], 0
LABEL L_for_cond_3
  t0 = BIN <, j@global[1], i@global[0]
  IF_FALSE t0, L_for_end_5
  t0 = BIN ==, j@global[1], 3
  IF_FALSE t0, L_if_end_6
  GOTO L_for_end_5
LABEL L_if_end_6
  t0 = BIN ==, j@global[1], 1
  IF_FALSE t0, L_if_end_7
  GOTO L_for_step_4
LABEL L_if_end_7
  PRINT j@global[1]
LABEL L_for_step_4
  t1 = BIN +, j@global[1], 1
  MOV j@global[1], t1
  GOTO L_for_cond_3
LABEL L_for_end_5
LABEL L_do_body_8
  t0 = BIN >, i@global[0], 7
  IF_FALSE t0, L_if_end_11
  GOTO L_do_end_10
LABEL L_if_end_11
  GOTO L_do_cond_9
LABEL L_do_cond_9
  IF_TRUE false, L_do_body_8
LABEL L_do_end_10
  t0 = BIN >, i@global[0], 8
  IF_FALSE t0, L_if_end_12
  GOTO L_while_end_1
LABEL L_if_end_12
  GOTO L_while_cond_0
LABEL L_while_end_1
