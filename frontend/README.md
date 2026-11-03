# Empório da Música — interface

Interface em **Next.js 16, React 19, TypeScript e Tailwind CSS 4**, isolada do núcleo Python. Layout, marca vetorial, instrumentos, palheta/cursor e composição foram criados para este projeto, sem importar um template de landing page ou imagens de fabricantes.

## Abrir localmente

Requisitos: Node.js 20.9+ e o ambiente Python já preparado. O workspace foi validado com Node 24.13.0. No Windows, use `npm.cmd` se o PowerShell bloquear o script `npm.ps1`; não altere a política de execução.

No primeiro terminal, a partir da pasta do desafio:

```powershell
.\python-agent\.venv\Scripts\python.exe -X utf8 run_api.py
```

Se a API já estiver aberta em `http://127.0.0.1:8000`, reutilize o processo existente. No segundo terminal:

```powershell
Set-Location -LiteralPath 'D:\Edital e Cursos\UFC\CTE-IA\Desafio Técnico AI Engineer 2026 - Natália\frontend'
# Instale somente na primeira preparação ou após mudanças no package-lock.json:
npm.cmd ci
npm.cmd run dev
```

Abra **http://127.0.0.1:3000**. Para encerrar, use `Ctrl+C` no respectivo terminal. A API e o frontend são processos separados.

Por padrão, o navegador consulta `http://127.0.0.1:8000`. Para usar outro endereço, copie `.env.example` para `.env.local`, ajuste **somente** `NEXT_PUBLIC_API_URL` e reinicie o frontend. Em produção, essa URL é definida no build. Chaves Groq e Supabase continuam exclusivamente em `python-agent/.env`, nunca no frontend ou em variáveis `NEXT_PUBLIC_*`.

## Experiência e fluxo

- A página abre com saudação e sugestões. Carregá-la não inicia uma sessão nem consulta o modelo; a primeira pergunta abre o atendimento.
- A pergunta é guardada pela API. A tela mostra o aviso de finalidade/LGPD retornado pelo backend e solicita nome, telefone com DDD e e-mail.
- O cliente revisa os dados, marca a confirmação explícita e envia. O Supabase reconhece os contatos existentes ou recebe o cadastro novo; o agente retoma a pergunta original.
- A conversa exibe a resposta real recebida, as fontes consultadas quando disponíveis e o protocolo somente quando o backend o devolve para cadastro novo. Não há resposta de demonstração no código de produção.
- Perguntas seguintes mantêm a sessão. Limpar contexto preserva a conferência cadastral; encerrar fecha a conversa sem apagar o cadastro. Cadastro não autentica pedidos privados.
- Falhas não geram reenvios automáticos. Tentativas cadastrais incertas reutilizam os mesmos campos. Falha de resposta depois da conferência permite retomar a pergunta sem repetir o cadastro. Sessão expirada oferece nova conversa.

Tokens, histórico e campos de cadastro ficam no estado/memória da página, sem gravação pelo aplicativo em `localStorage`, `sessionStorage`, cookies ou analytics. Atualizar/fechar a aba perde o contexto; a sessão anterior expira no backend conforme sua política. Mensagens livres vão ao provedor do modelo, como na CLI; preencha contatos nos campos próprios. O aviso de LGPD reutiliza o texto aprovado no backend e não equivale a uma certificação de conformidade.

O visual usa fundo claro, contraste preto/laranja e fontes locais DM Sans e Instrument Serif, distribuídas pelos pacotes Fontsource sob suas licenças abertas. As ilustrações são SVGs escritos no projeto. Os movimentos são CSS, sem biblioteca pesada; há botão de pausa e respeito a `prefers-reduced-motion`. O cursor de palheta aplica-se a mouse, com cursor de texto nos campos; toque e teclado continuam utilizáveis. Não há áudio automático.

As licenças das fontes foram preservadas em `public/licenses/dm-sans.txt` e `public/licenses/instrument-serif.txt`.

## Validação focada

```powershell
npm.cmd run typecheck
npm.cmd run build
# Somente os novos fluxos da interface, sem Groq/Supabase reais:
npm.cmd run test:e2e
# Exemplo de repetição apenas de um fluxo alterado:
npm.cmd run test:e2e -- --grep "recupera envio cadastral"
```

O Playwright usa Edge headless e um único worker, com frontend na porta 3100 e API de teste na 8765. O arquivo `tests/serve_test_api.py` instancia a API Python real com modelo e cadastro substituídos em memória, exclusivamente nos testes. Ele não lê chaves nem grava no Supabase. Os testes não usam o backend normal da porta 8000 nem repetem as 28 conversas remotas. Em outra plataforma, adapte o canal do navegador e o caminho do Python no `playwright.config.ts`.

Os nove cenários cobrem apresentação e navegação, confirmação explícita/continuidade/fontes, retorno cadastral, cancelamento, falha de rede, cota, expiração, recuperação de envio incerto e celular/movimento reduzido. Artefatos ficam em `test-results/`, ignorado no Git.

Também foi conferida a versão compilada contra a API local real, até a solicitação de cadastro e o encerramento da sessão, sem confirmação de contatos ou inferência. As capturas desktop/celular e o relatório ficam em `python-agent/.runtime/frontend/`. Para repetir **somente** essa conferência, com API aberta e porta 3000 livre, use `node scripts/check-production.mjs` após o build. O script encerra apenas o servidor Next que ele próprio inicia.

## Publicação posterior

Esta fase entrega a interface local e o código versionado. Para conectar a Vercel depois, a raiz do projeto web será **`frontend`**, com build `npm run build`. Antes de publicar o atendimento completo, o backend Python precisa de uma URL HTTPS acessível, CORS com a origem exata do frontend e uma decisão sobre persistência/compartilhamento de sessões. O backend atual é local, em um processo e com sessões em memória; `127.0.0.1` não conecta um site público ao computador da loja.

Não foram criados recursos na Vercel nem alterado o esquema do Supabase nesta fase. A inferência continua na Groq; o PC executa apenas a interface e a API enquanto o desenvolvimento for local.

Implementação, ilustrações e validação realizadas com assistência do Codex. Foram consultadas a [instalação oficial do Next.js](https://nextjs.org/docs/app/getting-started/installation), a [integração oficial do Tailwind](https://tailwindcss.com/docs/installation/framework-guides/nextjs) e a documentação distribuída com a versão instalada do Next.js.
