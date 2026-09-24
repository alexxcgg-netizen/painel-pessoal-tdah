# ia/adapters/ — implementacoes concretas de ia.contrato.Adapter, uma por
# provedor (Anthropic, OpenAI...). Pacote propositalmente vazio: quem precisa
# de um adapter importa direto do modulo (ex: `from ia.adapters.anthropic
# import AdapterAnthropic`), pra nao carregar SDK de provedor que nao vai
# usar so por importar o pacote.
