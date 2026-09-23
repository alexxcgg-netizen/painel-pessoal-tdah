# AGENTS.md — regras operacionais + padrões descobertos (painel-pessoal-tdah)

Este arquivo é complementar ao `CLAUDE.md` (que tem as regras gerais do projeto, incluindo
o isolamento em relação ao `financeiro-construtora`). `CLAUDE.md` é a regra principal;
este arquivo guarda duas coisas específicas:

1. **Regras operacionais obrigatórias pra qualquer história/tarefa a partir da Fase 5**
   (seção abaixo).
2. **Padrões, pegadinhas e convenções descobertos durante o trabalho** — uma seção viva
   que cada história deve alimentar, não só `TODO.md`/`progress.txt`. Se você (agente)
   tropeçou em algo não-óbvio do código, descobriu uma convenção implícita, ou bateu numa
   pegadinha que outro agente provavelmente vai bater de novo — anote aqui, curto, com o
   arquivo/linha de referência quando fizer sentido.

## Regras obrigatórias a partir da Fase 5 (pedido explícito do Alex, 2026-09-23)

Valem pra toda história daqui pra frente. Histórias que já passaram (`"passes": true` no
`prd.json` antes desta regra existir) não precisam ser refeitas.

### 1. Atualizar este arquivo (AGENTS.md) a cada história
Além de `TODO.md`/`CHANGELOG.md`/`progress.txt`, toda história que terminar deve deixar
uma linha na seção "Padrões descobertos" abaixo se encontrou algo que vale a pena um
próximo agente saber antes de mexer na mesma área do código. Não precisa forçar uma
entrada se não descobriu nada novo — é pra ser útil, não burocracia por burocracia.

### 2. Checagem de segredo antes de cada commit
Antes de QUALQUER `git commit` (não só no fim da história), rodar:
```
gitleaks detect --source . --no-banner --redact
```
(`gitleaks` já está instalado e no PATH). Se detectar algo, **não commitar** — investigar
primeiro (pode ser falso positivo, ex: uma chave de exemplo claramente fake num `.env.example`
já existente; se for, ok seguir, mas confirme que é isso mesmo antes). Se for credencial
real ou dado sensível de teste (CPF real, número de cartão, etc) que acabou de ser
digitado/gerado num teste, remover do arquivo antes de commitar — nunca "commitar e
remover depois", porque já fica no histórico do git.

### 3. Auditoria de dependência nova antes de fechar a história
Se a história adicionou uma biblioteca nova:
- **Python** (`requirements.txt` mudou): rodar
  `.venv/bin/pip install -r requirements.txt && .venv/bin/pip-audit` (pip-audit já
  instalado no venv compartilhado) antes de marcar `"passes": true`. Vulnerabilidade
  crítica/alta encontrada → trocar de versão/lib se der, ou documentar no `notes` da
  história por que foi aceita mesmo assim (ex: sem fix disponível, risco não se aplica ao
  nosso uso).
- **JS/Node** (novo `package.json` ou dependência nova nele - hoje o projeto NÃO usa npm,
  é JS vanilla + Node só como test runner; se alguma história introduzir isso de fato):
  rodar `npm audit` no diretório com o `package.json` antes de fechar a história.
- História sem lib nova nenhuma: esta regra não se aplica, pode pular.

### 4. Smoke-test depois de integrar cada grupo (não é por história individual)
Isso é responsabilidade de quem faz a integração de um grupo inteiro na `main` (não de
cada história isolada) — depois do merge de um grupo (A, B, C ou D) e da suíte de testes
completa passando, também confirmar que o app de fato sobe e a tela principal carrega:
```
.venv/bin/python -c "import app" 2>&1   # confirma que importa sem erro (pega erro de sintaxe/import quebrado que testes unitarios podem nao cobrir)
.venv/bin/python app.py &
sleep 2
curl -sf -o /dev/null -w "%{http_code}\n" http://localhost:5000/ || curl -sf -o /dev/null -w "%{http_code}\n" http://localhost:5000/login
kill %1
```
(ajustar porta/rota de login conforme o que `app.py` já usa — o objetivo é só confirmar
"o processo sobe e responde HTTP 200/302 na rota inicial", não um teste completo de UI).
Se o smoke-test falhar, é bloqueador — não considerar a integração daquele grupo concluída
até resolver.

## Padrões descobertos (viva - cada história acrescenta aqui quando relevante)

_(vazio até agora - primeira história a rodar sob esta regra preenche.)_
