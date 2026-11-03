# Empório da Música — protótipo em Python

O código fica isolado em [`python-agent/`](python-agent/README.md). Execute os comandos **a partir desta pasta do desafio**; os dados originais permanecem em `data/`.

No GitHub, documentos internos, credenciais, CSVs de clientes/pedidos e relatórios locais não são publicados. Veja a [preparação do repositório](docs/GITHUB.md) e as [quatro conversas públicas de catálogo](docs/EXEMPLOS_CATALOGO.md). Os links para evidências locais abaixo são acessíveis no workspace do responsável.

**Estado atual: núcleo de IA pela CLI, com Groq e cadastro mínimo no Supabase.** O LLM consulta catálogo e políticas; o Python coleta nome, telefone e e-mail pelo fluxo explícito de cadastro, confirma o envio e grava no PostgreSQL. Configure as chaves somente no `.env` local. A inferência permanece remota. FastAPI, autenticação de clientes e interface ficam para as próximas etapas.

**Entrada atualizada:** antes da primeira resposta, o chat solicita e confirma os contatos, explica a finalidade com referência à LGPD e confere telefone + e-mail juntos no Supabase. Reconhece o retorno ou cria o cadastro, depois retoma a pergunta original. Veja o [fluxo inicial](docs/FLUXO_INICIAL.md). As demais consultas e cálculos foram preservados.

```powershell
# Após configurar a chave Groq no .env local:
.\python-agent\.venv\Scripts\python.exe run_agent.py chat
# O chat solicita o cadastro antes de responder; /cadastro pode antecipá-lo.
# O cadastro avulso também continua disponível:
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
