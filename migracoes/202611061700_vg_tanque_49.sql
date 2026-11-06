-- 2026-11-06: o Alex disse que o tanque do XC40 e de 49 L ("acho que e 49"), nao 48. So troca se ainda estiver no
-- padrao (48, nao conferido); valor que ele ja tenha mudado fica como esta.
UPDATE veiculo SET tanque_l = 49 WHERE id = 1 AND tanque_l = 48 AND tanque_conferido = 0;
