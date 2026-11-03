# Empório da Música — protótipo em Python

O código fica isolado em [`python-agent/`](python-agent/README.md). Execute os comandos **a partir desta pasta do desafio**; os dados originais permanecem em `data/`.

No GitHub, documentos internos, credenciais, CSVs de clientes/pedidos e relatórios locais não são publicados. Veja a [preparação do repositório](docs/GITHUB.md) e as [quatro conversas públicas de catálogo](docs/EXEMPLOS_CATALOGO.md). Os links para evidências locais abaixo são acessíveis no workspace do responsável.

**Estado atual: núcleo de IA pela CLI, com Groq e o modelo remoto `qwen/qwen3.8-27b`.** O terminal recebe perguntas em português, o LLM escolhe ferramentas e o Python consulta os CSVs e as seções do PDF de políticas. Configure `GROQ_API_KEY` somente em `python-agent/.env`; a inferência não exige carregar um modelo na RAM local. As políticas têm fontes com páginas e cálculos em Python. FastAPI, Supabase e a interface ficam para fases posteriores.

```powershell
# Após configurar a chave Groq no .env local:
.\python-agent\.venv\Scripts\python.exe run_agent.py chat
.\python-agent\.venv\Scripts\python.exe run_agent.py chat --message "Quanto custa o Takamine GD20?"
# As consultas determinísticas continuam disponíveis:
.\python-agent\.venv\Scripts\python.exe run_agent.py products --query "Takamine GD20"
.\python-agent\.venv\Scripts\python.exe run_agent.py products --category "Violões" --max-price 1000
.\python-agent\.venv\Scripts\python.exe python-agent\scripts\validate.py
.\python-agent\.venv\Scripts\python.exe python-agent\scripts\validate_chat.py
.\python-agent\.venv\Scripts\python.exe -X utf8 python-agent\scripts\validate_policies.py
```

**135 testes locais, 28 perguntas reais e consulta ao PDF pela CLI aprovados**, com o PDF e os seis CSVs intactos. Consulte as [instruções](python-agent/README.md), o [relatório de políticas](python-agent/reports/FASE_POLITICAS.md), as [28 respostas executadas](python-agent/examples/conversas_28_executadas.md) e o [caderno atualizado](python-agent/examples/conversas_groq.md). As [evidências anteriores com Groq](python-agent/reports/FASE_GROQ.md) e os roteiros de referência foram preservados.
