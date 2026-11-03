# Cadastro mínimo de clientes

Esta etapa adiciona nome, telefone e e-mail ao Supabase/PostgreSQL, mantendo o
agente de catálogo e políticas existente. Não importa os clientes/pedidos dos
CSVs nem altera esses arquivos. Não cria login, autentica pedidos ou autoriza
publicidade.

## Usar pela CLI

Na raiz do desafio, com as chaves configuradas em `python-agent/.env`:

```powershell
.\python-agent\.venv\Scripts\python.exe run_agent.py register
```

Também é possível digitar `/cadastro` no chat. O fluxo solicita os três campos,
mostra os dados para conferência e pede confirmação; a resposta padrão é não.
Cancelar ou interromper antes da confirmação não solicita gravação.

```powershell
# Valida sem conexão ou gravação; não requer chave Supabase nem Groq.
.\python-agent\.venv\Scripts\python.exe run_agent.py register --dry-run

# Executa somente os testes novos, sem serviços remotos.
.\python-agent\.venv\Scripts\python.exe -X utf8 python-agent\scripts\validate_registration.py
```

Em automações, `--json register --confirm` recebe somente `name`, `phone` e
`email` como JSON pela entrada padrão. `--confirm` é obrigatório para gravar;
não são aceitos ID, permissão, senha ou flag de autenticação no JSON. Evite
colocar contatos pessoais em argumentos do terminal e no histórico do shell.

Os campos coletados pelo fluxo de cadastro não entram no histórico do agente
nem nas requisições à Groq. Mensagens livres do chat continuam sendo enviadas ao
LLM como antes; use `/cadastro` para fornecer contatos nesse fluxo separado.

## Configuração

```dotenv
SUPABASE_URL=https://SEU_PROJETO.supabase.co
SUPABASE_SECRET_KEY=
```

Use uma chave `sb_secret_...` somente no backend e no `.env` local, ignorado
pelo Git. Nunca a exponha ao navegador, em `NEXT_PUBLIC_`, nos exemplos ou nos
relatórios. A URL exige HTTPS e o domínio oficial do projeto. Redirecionamentos
não são seguidos. A implementação usa a biblioteca padrão do Python e a API
REST oficial; não adiciona SDKs ou modelos locais.

## Regras e persistência

- O nome é normalizado, mantém acentos e aceita de 2 a 120 caracteres.
- O telefone exige DDD brasileiro e é armazenado no formato `+55...`.
- O e-mail é validado sintaticamente e normalizado, com domínios IDNA aceitos.
- Cada submissão recebe um UUID. Uma repetição técnica reutiliza o mesmo UUID
  com `ON CONFLICT DO NOTHING`, sem sobrescrever outro cadastro.
- E-mail compartilhado não une clientes nem serve como prova de identidade.
- Uma falha temporária de gravação pode ser repetida uma vez com a mesma
  submissão. Se não houver confirmação da gravação, o erro apresenta somente
  o protocolo, orientando conferência antes de um novo envio.

Os únicos campos pessoais são `name`, `phone` e `email`; `id` e `created_at`
são metadados técnicos da tabela nova `public.customer_registrations`.
Há RLS habilitada e nenhum acesso para `anon` ou `authenticated`. O backend
recebe apenas INSERT nas quatro colunas enviadas e SELECT do UUID de protocolo;
não recebe leitura dos campos pessoais ou alteração/exclusão dessa tabela.

O aviso informativo `RLS Enabled No Policy` é esperado: esta tabela não oferece
políticas públicas, e a chave de backend executa o cadastro. As permissões e o
bloqueio de leitura pública foram verificados no banco. Não se cria uma política
pública apenas para eliminar esse aviso.

## Código e banco

- `registration.py`: validação e submissão imutável.
- `registration_store.py`: configuração protegida, endpoint fixo e persistência.
- `registration_cli.py`: coleta, conferência, confirmação e recibo sem contatos.
- `supabase/migrations/20261103150834_customer_registrations.sql`: migração
  aplicada no projeto dedicado, na região São Paulo. O arquivo foi criado pela
  CLI Supabase 3.0.0 e alinhado à versão registrada no banco remoto.

Esses módulos de validação/persistência podem ser chamados pela futura FastAPI.
O cadastro atual usa o comando explícito; não extrai automaticamente os dados
de mensagens livres nem oferece acesso a pedidos privados.

## Validação desta etapa

Foram aprovados 18 testes novos: formatos, confirmação/cancelamento, ausência de
chamadas ao LLM, configuração, proteção de chave, repetição idempotente,
redirecionamentos e erros sem exposição de dados. Foram usados dados fictícios
com domínio `example.invalid` para verificar a gravação real, repetição do mesmo
UUID, e-mail compartilhado e CLI real. Os três registros de teste foram removidos
pelos IDs e marcador exatos, com limpeza conferida no banco.

O PDF e os seis CSVs mantiveram os hashes. O núcleo do agente e suas ferramentas
não foram alterados. A suíte anterior de 28 conversas não foi repetida. Relatórios
locais: `python-agent/reports/registration_validation.json` e
`python-agent/reports/registration_live_validation.json`.

Código e migração são versionados no GitHub. O acesso Python → Supabase usa a
URL/chave local; não foi ativado branching pago nem implantação automática de
migrações a partir do GitHub. FastAPI e interface ficam para a próxima fase.

Codex, da OpenAI, auxiliou na implementação, testes e documentação.
