  MOV p@global[0], true
  MOV q@global[1], false
  MOV x@global[2], 5
  MOV t0, p@global[0]
  IF_FALSE t0, L_and_end_0
  MOV t0, q@global[1]
LABEL L_and_end_0
  MOV y@global[3], t0
  MOV t0, p@global[0]
  IF_TRUE t0, L_or_end_1
  MOV t0, q@global[1]
LABEL L_or_end_1
  MOV z@global[4], t0
  t0 = BIN >, x@global[2], 0
  IF_FALSE t0, L_and_end_3
  t1 = BIN <, x@global[2], 10
  MOV t0, t1
LABEL L_and_end_3
  IF_TRUE t0, L_or_end_2
  t1 = UN !, p@global[0]
  MOV t0, t1
LABEL L_or_end_2
  MOV mixto@global[5], t0
  MOV t0, p@global[0]
  IF_TRUE t0, L_or_end_5
  MOV t0, q@global[1]
LABEL L_or_end_5
  IF_FALSE t0, L_and_end_4
  t1 = BIN ==, x@global[2], 5
  IF_TRUE t1, L_or_end_6
  MOV t1, q@global[1]
LABEL L_or_end_6
  MOV t0, t1
LABEL L_and_end_4
  MOV anidado@global[6], t0
