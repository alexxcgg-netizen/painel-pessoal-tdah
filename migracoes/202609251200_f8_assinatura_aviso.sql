-- Fase 8, faixa F3: interruptor por assinatura "avisar antes de cobrar".
-- Desligado por padrao (0) - so avisa quem o Alex ligar explicitamente na
-- tela de assinaturas. O calculo da proxima cobranca continua vindo de
-- financas_recorrentes.proxima_cobranca_assinatura (nao duplicado aqui).
ALTER TABLE assinatura ADD COLUMN avisar_antes_cobrar INTEGER NOT NULL DEFAULT 0;
