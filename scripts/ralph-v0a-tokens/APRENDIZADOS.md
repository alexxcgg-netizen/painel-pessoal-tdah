# Aprendizados V0a

- Variavel composta no :root congela os var() de dentro (mesma pegadinha do --glass-tint
  documentada no style.css). Os tokens da V0a so dependem de variaveis fixas do :root;
  borda tingida pela aba = var(--glass-border), que cada #tab-X ja redeclara.
- getComputedStyle(root).getPropertyValue('--x') devolve a string crua; pra saber se o
  navegador ACEITOU o valor, aplique num elemento-sonda e leia a propriedade real
  (verificar.py faz isso: box-shadow, background, raio, fonte, transicao, z-index).
- No sandbox, o Chromium nao confia no CA do proxy: Google Fonts falha
  (ERR_CERT_AUTHORITY_INVALID) e as fontes caem no fallback. /api/summary/today da 502
  com a chave falsa da IA. Os dois sao ambiente e ficam filtrados no verificar.py.
- ui-ux-pro-max --design-system --persist sugeriu paleta/fonte novas (HUD, Exo, Roboto Mono):
  descartado por regra do Alex. Aproveitado so o checklist (foco visivel, reduced-motion,
  sem emoji como icone, 150-300ms).
- Gitleaks instalado nao aceita -q: use `gitleaks detect --no-git --source <dir> --no-banner -l warn`.
