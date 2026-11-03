# Publicação completa na Vercel

O atendimento está publicado: **[site](https://emporio-da-musica-five.vercel.app)** e **[saúde da API](https://emporio-da-musica-api.vercel.app/health)**. A entrada de produção é **`app.py`**, com FastAPI e sessões compartilhadas no Supabase. O atendimento local usa `run_api.py`, com sessões em memória. Os dois modos reutilizam o agente, catálogo, políticas e cadastro existentes.

## Dois projetos, um repositório

| Projeto publicado | Root Directory | Framework | Configuração |
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
API_ALLOWED_ORIGINS=https://emporio-da-musica-five.vercel.app
```

As duas chaves foram configuradas como **Secret** para produção/preview no projeto da API, sem serem impressas. Os campos no exemplo ficam vazios deliberadamente. Os valores usados no desenvolvimento ficam em `python-agent/.env`. O envio inicial foi feito por `python-agent/scripts/configure_vercel_secrets.py`, usando stdin da CLI autenticada, sem valores em argumentos ou arquivos novos; o script não sobrescreve variáveis existentes. Origens adicionais de preview devem ser incluídas explicitamente, separadas por vírgula; não use `*`. Uma URL de preview protegida exige o mecanismo de acesso da própria Vercel para testes automatizados, sem desativar a proteção.

## Variável do frontend

Somente depois de conhecer e verificar a URL da API:

```dotenv
NEXT_PUBLIC_API_URL=https://emporio-da-musica-api.vercel.app
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

## Validação executada

```powershell
# Da raiz do desafio; somente testes novos e quatro fluxos de API afetados:
.\python-agent\.venv\Scripts\python.exe -X utf8 python-agent\scripts\validate_cloud_runtime.py
# Acrescenta o teste de sessões no Supabase real, sem Groq/cadastro reais:
.\python-agent\.venv\Scripts\python.exe -X utf8 python-agent\scripts\validate_cloud_runtime.py --live
```

Passaram 14 testes focados, a integração de duas instâncias com RPCs reais, exclusão mútua, token incorreto, continuidade/limpeza do histórico e encerramento da sessão sintética. Não foram criados cadastros reais nem consumida a Groq. Os sete arquivos de fonte e os seis módulos centrais mantiveram os hashes anteriores. Os privilégios foram conferidos: as tabelas e cinco novas RPCs não estão acessíveis aos papéis do navegador. Os avisos INFO de RLS sem políticas correspondem ao acesso exclusivo de backend, deliberado.

Também passaram o build Next.js/TypeScript e o teste focado de configuração pública: zero requisições a loopback em uma origem pública sem API configurada, mantendo a conexão de desenvolvimento local. As suítes remotas anteriores não foram repetidas.

Os dois deploys de produção chegaram a **READY** no commit `f0b7af2`, e a saúde da API retornou `200` com `session_storage: supabase`. No site público, sem sessão de login da Vercel, passaram: origem CORS, pergunta aguardando cadastro, revisão/confirmação explícita, gravação no Supabase e resposta real à pergunta sobre o Takamine GD20. O preço retornado foi conferido no CSV. Em uma segunda sessão, os mesmos contatos foram reconhecidos sem expor protocolo anterior e sem outra pergunta ao LLM. Também foram conferidos layout móvel e ausência de erros de execução no navegador.

O cadastro sintético foi removido por UUID, nome/e-mail marcados e telefone sintético, e as duas sessões de teste foram encerradas. As 28 conversas anteriores não foram repetidas. Os logs de erro/fatal dos dois deploys verificados não apresentaram ocorrências na janela consultada de 15 minutos. As proteções dos previews e as regras privadas do Supabase foram preservadas.

CLI 65.10.0 instalada e autenticada; plugin e MCP existentes reutilizados. Diretórios locais vinculados aos respectivos projetos, com arquivos `.vercel` e `.env.local` ignorados no Git. Os dois projetos já estão conectados ao GitHub. As evidências detalhadas ficam no relatório local `python-agent/reports/vercel_live_validation.json` e nas capturas `.runtime/frontend/vercel-live-*.png`.

Os limites de requisições/tokens da Groq e os limites de hospedagem do plano continuam existindo; publicar não aumenta essas cotas. Antes de atualizar o snapshot ou mudar o núcleo, repita somente as verificações afetadas. Não há monitoramento externo/alertas configurados nesta etapa.

Referências: [FastAPI na Vercel](https://vercel.com/docs/frameworks/backend/fastapi), [publicação com Git](https://vercel.com/docs/git) e [privilégios/RLS no Supabase](https://supabase.com/docs/guides/api/securing-your-api). Implementação e validação realizadas com assistência do Codex.
