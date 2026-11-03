# API local — Empório da Música

A API FastAPI reutiliza o agente Python, as ferramentas de catálogo/políticas e a conferência cadastral no Supabase. A CLI continua disponível. Esta etapa prepara a integração com uma interface; não publica um site nem cria autenticação de clientes.

## Executar

Abra o terminal na pasta do desafio, onde estão `run_api.py`, `run_agent.py` e `data/`. Reutilize `python-agent/.env` com `DATA_DIR`, as configurações Groq e `SUPABASE_URL`/`SUPABASE_SECRET_KEY` já usadas pela CLI. Não copie essas chaves para uma interface.

```powershell
# Instalação reproduzível no ambiente virtual do projeto, incluindo o cliente dos testes:
.\python-agent\.venv\Scripts\python.exe -m pip install -r python-agent\requirements-api.lock
.\python-agent\.venv\Scripts\python.exe -X utf8 run_api.py
```

Se ainda não existir ambiente virtual, crie-o com `python -m venv python-agent\.venv`. Não recrie um ambiente existente.

A API escuta somente `127.0.0.1:8000`, em um processo. Abra `http://127.0.0.1:8000/docs` para o contrato interativo ou `/openapi.json` para os schemas de entrada. `GET /health` verifica o processo sem consultar Groq ou Supabase. Use `Ctrl+C` para encerrar; `--port 8001` seleciona outra porta.

## Fluxo e rotas

| Método e caminho | Entrada | Resultado |
| --- | --- | --- |
| `GET /health` | — | `200`, estado do processo; não verifica serviços externos |
| `POST /sessions` | Sem corpo | `201`, `session_id`, `session_token`, saudação e aviso de finalidade/LGPD |
| `POST /sessions/{id}/messages` | `{"message":"pergunta em português"}` | `202 registration_required` antes do cadastro; `200 answered` depois |
| `POST /sessions/{id}/registration` | Nome, telefone, e-mail e `confirmed:true` | Confere/cadastra e responde à pergunta pendente automaticamente |
| `POST /sessions/{id}/registration` | `{"confirmed":false}` | Encerra sem envio cadastral nesta solicitação |
| `POST /sessions/{id}/clear` | Sem corpo | Limpa contexto/pergunta pendente e mantém o cadastro conferido |
| `DELETE /sessions/{id}` | Sem corpo | Encerra a sessão; não exclui o cadastro na loja |

Todas as rotas de uma sessão exigem `Authorization: Bearer <session_token>`. O token é entregue somente na abertura; o servidor guarda seu hash. Não coloque tokens em URLs, Git ou logs. O token permite usar aquela conversa; **não comprova a identidade do cliente e não libera pedidos privados**.

A primeira pergunta fica pendente e não é enviada ao LLM antes da conferência. A interface deverá mostrar o aviso e coletar os contatos em campos próprios, apresentar os dados para revisão e enviar `confirmed:true` somente após a confirmação do cliente. Nenhum campo `registered` enviado pelo navegador pode liberar o atendimento. Uma pergunta diferente enquanto houver outra pendente recebe `409`; conclua a etapa ou limpe o contexto.

O cadastro usa a mesma operação já existente: telefone normalizado **e** e-mail devem corresponder ao mesmo registro para reconhecer um retorno. Um cadastro existente não é atualizado, e seu protocolo anterior não é exposto. Os campos estruturados de cadastro não entram no contexto do LLM. As mensagens livres da conversa continuam sendo enviadas à Groq; não use a mensagem como campo de cadastro.

## Exemplo no PowerShell

Mantenha o servidor aberto e use outro terminal. Os contatos abaixo são fictícios; executar a confirmação com uma configuração real cria um cadastro de teste no Supabase.

```powershell
$apiBase = 'http://127.0.0.1:8000'
$conversation = Invoke-RestMethod -Method Post -Uri "$apiBase/sessions"
$sessionHeaders = @{ Authorization = "Bearer $($conversation.session_token)" }
$sessionUrl = "$apiBase/sessions/$($conversation.session_id)"

# A primeira resposta solicita o cadastro e guarda esta pergunta.
$questionBody = @{ message = 'Quanto custa o Takamine GD20?' } | ConvertTo-Json
Invoke-RestMethod -Method Post -Uri "$sessionUrl/messages" -Headers $sessionHeaders `
  -ContentType 'application/json; charset=utf-8' -Body ([Text.Encoding]::UTF8.GetBytes($questionBody))

# Somente depois de mostrar o aviso e obter a confirmação explícita do cliente:
$registrationBody = @{
  name = 'Cliente Exemplo'
  phone = '(85) 90000-0000'
  email = 'cliente-exemplo@example.invalid'
  confirmed = $true
} | ConvertTo-Json
$reply = Invoke-RestMethod -Method Post -Uri "$sessionUrl/registration" -Headers $sessionHeaders `
  -ContentType 'application/json; charset=utf-8' -Body ([Text.Encoding]::UTF8.GetBytes($registrationBody))
$reply.registration.message
$reply.answer.text

# Próxima pergunta: a mesma sessão conserva o contexto do agente.
$followupBody = @{ message = 'Esse modelo está disponível?' } | ConvertTo-Json
$reply = Invoke-RestMethod -Method Post -Uri "$sessionUrl/messages" -Headers $sessionHeaders `
  -ContentType 'application/json; charset=utf-8' -Body ([Text.Encoding]::UTF8.GetBytes($followupBody))
$reply.answer.text

Invoke-RestMethod -Method Delete -Uri $sessionUrl -Headers $sessionHeaders
```

## Respostas e recuperação de falhas

Uma resposta `answered` contém `answer.text`, `answer.tools` e `answer.sources`, preservando o formato do núcleo. A confirmação cadastral contém também `registration.code` (`registration_saved` ou `registration_existing`) e `registration.message`; somente um novo cadastro devolve `registration_id`. Sem pergunta pendente, o código de topo é `registration_confirmed`, sem chamada ao modelo.

Os erros devolvem JSON com `code` e `message`, sem ecoar contatos, mensagens de exceção ou chaves. Dados de entrada inválidos usam `422`; ausência de token, `401`; sessão desconhecida, expirada ou token incorreto, `404`; operação concorrente/pergunta pendente, `409`; corpo acima de 32 KiB, `413`; cota da Groq, `429`; falha no cadastro ou na resposta, `502`; capacidade local de sessões esgotada, `503`. A mensagem é limitada a 4.000 caracteres e as confirmações aceitam booleanos reais, sem conversão de strings.

Se o banco falhar, o atendimento continua bloqueado. Repita os mesmos dados: o UUID da tentativa é preservado na sessão e a operação do Supabase trata a repetição. Para trocar dados após uma tentativa incerta, encerre a sessão e abra outra; isso não desfaz uma eventual gravação anterior.

Se o modelo falhar após o cadastro, a resposta de erro informa `registration_confirmed:true` e `pending_message_saved:true`. Repita a pergunta original ou a confirmação cadastral: o banco não será gravado novamente. Em caso de cota, respeite `Retry-After`, quando presente. A API não troca de provedor nem amplia o plano.

Repetir uma confirmação já concluída devolve a confirmação, sem nova consulta ao LLM se não houver pergunta pendente. As mensagens, em geral, não têm idempotência: repetir uma pergunta já respondida conta como outro turno e pode gerar outra chamada à Groq.

## Limites desta etapa

- Sessões e histórico ficam **em memória por processo**, com expiração após 30 minutos sem atividade e limite de 100 sessões. A remoção das expiradas ocorre nas próximas operações de sessão. Cada conversa tem seu próprio agente e aceita uma operação por vez; outras sessões podem continuar.
- Reiniciar o servidor apaga as conversas e a conferência daquela sessão. Os cadastros no Supabase permanecem. Esta versão usa um único processo; compartilhar sessões entre instâncias ou persistir histórico precisa ser tratado antes da publicação do backend.
- CORS permite `http://localhost:3000` e `http://127.0.0.1:3000`. Para outra origem, configure `API_ALLOWED_ORIGINS` no **ambiente do processo**, com origens separadas por vírgula; `*` é recusado. Essa variável da API não é carregada do `.env`. CORS não substitui autenticação.
- O servidor local usa HTTP em loopback. HTTPS, hospedagem do backend, proteção contra abuso e configuração de produção pertencem à fase de publicação, ainda não realizada. Nenhuma alteração foi feita na Vercel ou no esquema do Supabase nesta etapa.
- O aviso de finalidade/LGPD reutiliza o fluxo aprovado. Cadastro não equivale a login, autorização para publicidade ou autenticação de pedidos. A API não executa compras, exclusões de cadastro ou alterações de pedidos.

## Validação e decisões

```powershell
# Somente os novos testes locais de API; nenhuma chamada à Groq/Supabase:
.\python-agent\.venv\Scripts\python.exe -X utf8 python-agent\scripts\validate_api.py
```

Passaram 23 testes focados de HTTP, confirmação, falhas, concorrência, expiração e isolamento. Também foi validado um servidor HTTP real: cadastro sintético novo, retomada de uma pergunta à Groq com preço/fonte do CSV e reconhecimento dos mesmos contatos em outra sessão. O registro sintético foi removido. As 28 conversas anteriores não foram repetidas.

As evidências detalhadas ficam localmente em `python-agent/reports/api_validation.json`, `api_tests.txt` e `api_live_validation.json`, ignorados no Git. O script `validate_api_live.py` faz gravação e inferência reais; não o execute automaticamente em cada mudança. Seu cadastro sintético exige limpeza administrativa por ID e marcador, descrita no próprio script.

Foram usados FastAPI e Uvicorn na camada HTTP; chamadas bloqueantes do núcleo executam nos handlers síncronos, no pool de threads. Nenhuma migração para outro framework de agentes foi necessária. As versões de dependências foram fixadas em `requirements-api.lock` para o ambiente Python 3.10 validado. O cliente HTTPX é usado somente pelos testes; a versão atual do Starlette emite aviso de depreciação desse adaptador, sem falha nos testes.

Referências oficiais: [handlers síncronos e concorrência](https://fastapi.tiangolo.com/async/), [testes com TestClient](https://fastapi.tiangolo.com/tutorial/testing/) e [CORS](https://fastapi.tiangolo.com/tutorial/cors/). Implementação e documentação elaboradas com assistência do Codex, com resultados locais e reais distinguidos nos relatórios.
