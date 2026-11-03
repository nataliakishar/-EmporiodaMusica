# Empório da Música — protótipo em Python

O núcleo Python fica em [`python-agent/`](python-agent/README.md) e a interface em [`frontend/`](frontend/README.md). Execute os comandos do backend **a partir desta pasta do desafio**; os dados originais permanecem em `data/`.

**Publicado e validado:** [abra a Empório da Música](https://emporio-da-musica-five.vercel.app). A [API de produção](https://emporio-da-musica-api.vercel.app/health) usa sessões compartilhadas e fontes privadas no Supabase. Foi validado no navegador um atendimento completo com uma pergunta real à Groq, preço conferido no CSV, reconhecimento de retorno cadastral e layout de celular; o cadastro sintético foi removido. Veja [configuração da publicação](docs/PUBLICACAO_VERCEL.md). O site publicado funciona sem o VS Code ou o computador do desenvolvedor ligados.

No GitHub, documentos internos, credenciais, CSVs de clientes/pedidos e relatórios locais não são publicados. Veja a [preparação do repositório](docs/GITHUB.md) e as [quatro conversas públicas de catálogo](docs/EXEMPLOS_CATALOGO.md). Os links para evidências locais abaixo são acessíveis no workspace do responsável.

**Estado atual: interface Next.js/React e API FastAPI publicadas na Vercel, com Groq e cadastro mínimo no Supabase.** O LLM consulta catálogo e políticas; o Python coleta nome, telefone e e-mail pelo fluxo explícito de cadastro, confirma o envio e grava no PostgreSQL. As chaves ficam como segredos no backend Vercel; o `.env` local é usado no desenvolvimento. A inferência permanece remota, sujeita às cotas do provedor. Autenticação de clientes para pedidos privados continua fora deste protótipo. A CLI e `run_api.py` permanecem disponíveis para execução local.

**Interface disponível em `frontend/`:** página própria com instrumentos flutuantes, cursor de palheta, movimento reduzido e chat conectado à API existente. A pergunta inicia o fluxo de revisão/confirmação cadastral e é retomada automaticamente. Veja [como abrir a interface e validar os novos fluxos](frontend/README.md). Com a API aberta, execute `npm.cmd run dev` dentro de `frontend/` e acesse `http://127.0.0.1:3000`.

**API implementada e validada:** sessões isoladas, pergunta pendente até confirmar o cadastro e retomada automática do atendimento. Foram executados 23 testes focados e um fluxo HTTP real com Supabase e uma pergunta à Groq. Execute `.\python-agent\.venv\Scripts\python.exe -X utf8 run_api.py` e abra `http://127.0.0.1:8000/docs`. Consulte [rotas, exemplos e limites da API](docs/API.md). As sessões desta etapa ficam em memória, em um único processo.

**Entrada atualizada:** antes da primeira resposta, o chat solicita e confirma os contatos, explica a finalidade com referência à LGPD e confere telefone + e-mail juntos no Supabase. Reconhece o retorno ou cria o cadastro, depois retoma a pergunta original. Veja o [fluxo inicial](docs/FLUXO_INICIAL.md). As demais consultas e cálculos foram preservados.

```powershell
# Após configurar a chave Groq no .env local:
.\python-agent\.venv\Scripts\python.exe run_agent.py chat
# O chat solicita o cadastro antes de responder; /cadastro pode antecipá-lo.
# Entrada alternativa: confere os contatos primeiro e continua no chat:
.\python-agent\.venv\Scripts\python.exe run_agent.py register
# Validação sem gravação:
.\python-agent\.venv\Scripts\python.exe run_agent.py register --dry-run
.\python-agent\.venv\Scripts\python.exe run_agent.py chat --message "Quanto custa o Takamine GD20?"
# As consultas determinísticas continuam disponíveis:
.\python-agent\.venv\Scripts\python.exe run_agent.py products --query "Takamine GD20"
.\python-agent\.venv\Scripts\python.exe run_agent.py products --category "Violões" --max-price 1000
.\python-agent\.venv\Scripts\python.exe -X utf8 python-agent\scripts\validate_registration.py
```

**135 testes locais, 28 perguntas reais e consulta ao PDF pela CLI aprovados**, com o PDF e os seis CSVs intactos. Consulte as [instruções](python-agent/README.md), o [relatório de políticas](python-agent/reports/FASE_POLITICAS.md), as [28 respostas executadas](python-agent/examples/conversas_28_executadas.md) e o [caderno atualizado](python-agent/examples/conversas_groq.md). As [evidências anteriores com Groq](python-agent/reports/FASE_GROQ.md) e os roteiros de referência foram preservados.

Na etapa nova, foram executados **somente 18 testes focados**, mais a integração real do cadastro pela CLI e pelo Supabase. Não foram repetidas as 28 conversas com a Groq. Os três registros sintéticos de integração foram removidos. Veja [cadastro e decisões](docs/CADASTRO.md).

Na mudança de entrada, passaram **36 testes focados** (18 novos e os 18 de cadastro), além da integração real. O núcleo anterior, o PDF e os CSVs continuam com os mesmos hashes; não houve chamada à Groq nesta validação.

Correção da entrada `register`: agora usa a mesma conferência do chat e permanece aberto para perguntas. Passaram **39 testes focados e um único caso real completo com Supabase e Groq**. O modo JSON também reconhece contatos existentes, mas continua devolvendo somente o resultado da operação, sem abrir conversa interativa.
