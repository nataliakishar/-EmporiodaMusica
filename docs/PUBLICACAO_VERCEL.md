# Publicação completa na Vercel

O atendimento local usa `run_api.py`, com sessões em memória. A entrada de produção é **`app.py`**, com FastAPI e sessões compartilhadas no Supabase. Os dois modos reutilizam o agente, catálogo, políticas e cadastro existentes. Preparação e testes concluídos; a criação dos projetos/deploys depende do acesso autorizado ao espaço Vercel.

## Dois projetos, um repositório

| Projeto sugerido | Root Directory | Framework | Configuração |
| --- | --- | --- | --- |
| `emporio-da-musica-api` | Raiz do repositório | FastAPI | `vercel.json`, `requirements.txt`, `app.py` |
| `emporio-da-musica` | `frontend` | Next.js | `frontend/vercel.json`, `package-lock.json` |

Ambos devem apontar ao repositório já usado, na branch `main`. O frontend mantém instalação `npm ci`, build `npm run build` e Node 24.x. Não há compra de domínio ou mudança de plano prevista. Usar os limites do plano existente; verificar a conta antes de criar recursos.

## Variáveis do backend

Configure no **projeto da API**, nos ambientes que serão publicados:

```dotenv
LLM_PROVIDER=groq
LLM_MODEL=qwen/qwen3.8-27b
LLM_BASE_URL=https://api.groq.com/openai/v1
LLM_TIMEOUT_SECONDS=90
GROQ_API_KEY=
SUPABASE_URL=https://edrszblatsadoidzquyh.supabase.co
SUPABASE_SECRET_KEY=
API_ALLOWED_ORIGINS=https://DOMINIO-PUBLICADO-DO-FRONTEND
```

As duas chaves vazias são segredos de backend e devem ser configuradas diretamente em ambiente protegido, nunca no chat, no GitHub ou como `NEXT_PUBLIC_*`. Os valores já usados localmente ficam em `python-agent/.env`. Origens adicionais de preview devem ser incluídas explicitamente, separadas por vírgula; não use `*`. Uma URL de preview protegida exige o mecanismo de acesso da própria Vercel para testes automatizados, sem desativar a proteção.

## Variável do frontend

Somente depois de conhecer e verificar a URL da API:

```dotenv
NEXT_PUBLIC_API_URL=https://DOMINIO-PUBLICADO-DA-API
```

Esse endereço é público e é incorporado durante o build. Mudar a variável exige novo build. `127.0.0.1`, `localhost` e a URL do Supabase não substituem a URL do backend do agente. Sem configuração correta em um site público, a interface mostra que o atendimento está em preparação e não tenta acessar a máquina do visitante.

## Sessões e fontes privadas

A migração `supabase/migrations/20261103182459_cloud_runtime_sessions.sql` adiciona o esquema **não exposto** `emporio_agent_private`, com RLS e acesso apenas por `service_role`. As RPCs públicas são `SECURITY INVOKER`, com execução revogada de `PUBLIC`, `anon` e `authenticated`; o navegador não as chama diretamente.

- `sessions`: hash do token, estado cadastral daquela conversa, pergunta pendente, rascunho de tentativa incerta, protocolo novo e até seis turnos/referências. O token em claro não é salvo no banco. O frontend continua mantendo o seu token somente em memória.
- Uma lease de 330 segundos impede duas instâncias de alterar a mesma sessão simultaneamente. A função Vercel tem duração máxima configurada de 300 segundos. Falhas/timeout podem exigir aguardar a liberação da lease antes de repetir, sem reenvio automático pelo frontend.
- A sessão expira logicamente após 30 minutos sem atividade. Registros expirados são removidos nas novas aberturas de sessão; encerrar a conversa remove seu estado imediatamente quando a operação é confirmada. O cadastro da loja é preservado. Não há arquivamento duradouro do histórico nesta implementação.
- `assets`: um snapshot pequeno dos seis CSVs e do PDF, em um único objeto JSON com conteúdo base64 e hashes. Esse conteúdo nunca é versionado no Git nem servido pelo frontend. O backend recupera as fontes por RPC autenticada e confere SHA-256 antes de usá-las em seu diretório temporário. A consulta mantém as regras de snapshot do agente.

O script abaixo atualiza o snapshot **privado**, usando a configuração local de backend. Depois de atualizar dados, reimplante a API para renovar o cache das instâncias:

```powershell
.\python-agent\.venv\Scripts\python.exe -X utf8 python-agent\scripts\prepare_cloud_sources.py
```

Os sete arquivos originais foram conferidos após o envio e preservados localmente. A migração não altera cadastros existentes, tabelas de pedidos ou autenticação. Os campos estruturados coletados no cadastro continuam fora do contexto do LLM. Mensagens livres e trechos consultados continuam seguindo a política já aprovada de uso da Groq.

## Validação executada e restante

```powershell
# Da raiz do desafio; somente testes novos e quatro fluxos de API afetados:
.\python-agent\.venv\Scripts\python.exe -X utf8 python-agent\scripts\validate_cloud_runtime.py
# Acrescenta o teste de sessões no Supabase real, sem Groq/cadastro reais:
.\python-agent\.venv\Scripts\python.exe -X utf8 python-agent\scripts\validate_cloud_runtime.py --live
```

Passaram 14 testes focados, a integração de duas instâncias com RPCs reais, exclusão mútua, token incorreto, continuidade/limpeza do histórico e encerramento da sessão sintética. Não foram criados cadastros reais nem consumida a Groq. Os sete arquivos de fonte e os seis módulos centrais mantiveram os hashes anteriores. Os privilégios foram conferidos: as tabelas e cinco novas RPCs não estão acessíveis aos papéis do navegador. Os avisos INFO de RLS sem políticas correspondem ao acesso exclusivo de backend, deliberado.

Também passaram o build Next.js/TypeScript e o teste focado de configuração pública: zero requisições a loopback em uma origem pública sem API configurada, mantendo a conexão de desenvolvimento local. As suítes remotas anteriores não foram repetidas.

Após criar os projetos e configurar suas variáveis, ainda é necessário verificar: deploy READY no commit correto; saúde da API com `session_storage: supabase`; origem CORS; fluxo do cadastro e uma única pergunta real no site; limpeza do cadastro sintético de validação; URLs definitivas. Esses itens **não estão declarados como concluídos** antes de evidência da publicação real.

Referências: [FastAPI na Vercel](https://vercel.com/docs/frameworks/backend/fastapi), [publicação com Git](https://vercel.com/docs/git) e [privilégios/RLS no Supabase](https://supabase.com/docs/guides/api/securing-your-api). Implementação e validação realizadas com assistência do Codex.
