  MOV i@global[0], 0
  MOV suma@global[1], 0
  t0 = BIN ==, i@global[0], 0
  IF_FALSE t0, L_if_else_0
  PRINT "cero"
  GOTO L_if_end_1
LABEL L_if_else_0
  PRINT "otro"
LABEL L_if_end_1
  t0 = BIN >, suma@global[1], 100
  IF_FALSE t0, L_if_end_2
  PRINT "grande"
LABEL L_if_end_2
LABEL L_while_cond_3
  t0 = BIN <, i@global[0], 5
  IF_FALSE t0, L_while_end_4
  t1 = BIN +, suma@global[1], i@global[0]
  MOV suma@global[1], t1
  t1 = BIN +, i@global[0], 1
  MOV i@global[0], t1
  GOTO L_while_cond_3
LABEL L_while_end_4
LABEL L_do_body_5
  t1 = BIN -, i@global[0], 1
  MOV i@global[0], t1
LABEL L_do_cond_6
  t0 = BIN >, i@global[0], 0
  IF_TRUE t0, L_do_body_5
LABEL L_do_end_7
  MOV k@global[2], 0
LABEL L_for_cond_8
  t0 = BIN <, k@global[2], 3
  IF_FALSE t0, L_for_end_10
  PRINT k@global[2]
LABEL L_for_step_9
  t1 = BIN +, k@global[2], 1
  MOV k@global[2], t1
  GOTO L_for_cond_8
LABEL L_for_end_10
  MOV i@global[0], 0
LABEL L_for_cond_11
  t0 = BIN >, i@global[0], 2
  IF_FALSE t0, L_if_end_14
  GOTO L_for_end_13
LABEL L_if_end_14
LABEL L_for_step_12
  t1 = BIN +, i@global[0], 1
  MOV i@global[0], t1
  GOTO L_for_cond_11
LABEL L_for_end_13
