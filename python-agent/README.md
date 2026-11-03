# Empório da Música — chatbot com LLM em Python

**API FastAPI local disponível:** execute `run_api.py` a partir da raiz do desafio e abra `http://127.0.0.1:8000/docs`. A camada HTTP reutiliza o núcleo e o cadastro, com sessões isoladas e confirmação antes de responder. Veja [API: execução, contrato e limites](../docs/API.md). Foram aprovados 23 testes focados e um fluxo HTTP real com Supabase e uma pergunta à Groq, sem repetir as 28 conversas. Instale as dependências fixadas com `.\python-agent\.venv\Scripts\python.exe -m pip install -r python-agent\requirements-api.lock`.

**Cadastro mínimo implementado:** use `/cadastro` no chat ou `run_agent.py register` para coletar nome, telefone e e-mail, conferir e confirmar a gravação no Supabase. O fluxo não envia esses campos ao LLM. Foram aprovados 18 testes focados e a integração real, sem repetir as 28 conversas anteriores. Veja [cadastro e configuração](../docs/CADASTRO.md).

**Fluxo inicial atualizado:** o chat agora exige a conferência cadastral antes da primeira resposta. Ele guarda a pergunta, coleta os contatos com aviso de finalidade/LGPD, reconhece o retorno ou cadastra e retoma a pergunta. A validação focada de entrada/cadastro passou com 36 testes e integração real, sem novas chamadas à Groq. Veja [FLUXO_INICIAL.md](../docs/FLUXO_INICIAL.md).

**O chat recebe perguntas em linguagem natural e as encaminha ao LLM configurado.** O modelo entende a necessidade e escolhe ferramentas; o Python valida os argumentos, consulta os CSVs originais em `data/` e devolve resultados para o modelo responder em PT-BR. Os comandos determinísticos anteriores continuam disponíveis para inspeção.

**Provedor atual: GroqCloud, com `qwen/qwen3.8-27b` remoto.** A CLI precisa de internet e de uma chave local; não exige carregar um modelo na RAM local. Os modelos GPT-OSS 120B e 20B atingiram cotas durante esta fase; as tentativas e falhas foram preservadas. O Qwen está listado no plano gratuito e usa a mesma Groq, sem alteração de conta/plano. É um modelo em preview, sujeito a mudanças do provedor. Testes com dublês não comprovam inferência real.

**O PDF de políticas é consultado pelo agente: 135 testes locais, 28 perguntas reais e a consulta de políticas pela CLI aprovados.** As oito perguntas anteriores e as vinte novas foram verificadas com o Qwen na Groq. Consulte o [relatório de políticas](reports/FASE_POLITICAS.md), os [resultados por pergunta](reports/policies_live_validation.json) e as [28 respostas reais](examples/conversas_28_executadas.md). O [caderno](examples/conversas_groq.md) contém as vinte novas respostas executadas, com as referências anteriores preservadas em outro arquivo. O [relatório anterior](reports/FASE_GROQ.md) mantém as evidências históricas com o modelo 120B. Autenticação de clientes permanece para uma fase posterior.

## Conversar com o chatbot

Se o terminal estiver em `CTE-IA`, entre primeiro na pasta do desafio:

```powershell
Set-Location -LiteralPath "D:\Edital e Cursos\UFC\CTE-IA\Desafio Técnico AI Engineer 2026 - Natália"
```

Reutilize o ambiente `.venv` já criado. A configuração local `python-agent/.env` deve conter:

```dotenv
DATA_DIR=../data
LLM_PROVIDER=groq
LLM_MODEL=qwen/qwen3.8-27b
LLM_BASE_URL=https://api.groq.com/openai/v1
LLM_TIMEOUT_SECONDS=90
GROQ_API_KEY=
```

Crie a chave em [Groq API Keys](https://console.groq.com/keys), cole o valor depois de `GROQ_API_KEY=` no `.env` local e salve. Nunca envie a chave no chat nem a copie para `.env.example`. O `.env` e `.runtime/` estão ignorados no Git; uma chave existente é preservada ao editar as demais opções. O plano gratuito tem [cotas por modelo/conta](https://console.groq.com/docs/rate-limits); o projeto não faz upgrade de plano nem troca de provedor automaticamente. Cada pergunta pode exigir mais de uma chamada. Erros de cota são informados, com no máximo uma repetição por requisição quando `Retry-After` indicar até 60 segundos.

Para conferir conexão, aceitação da chave e disponibilidade do modelo, sem imprimir a credencial nem enviar os CSVs:

```powershell
.\python-agent\.venv\Scripts\python.exe -X utf8 python-agent\scripts\check_groq.py
```

As chamadas usam ferramentas nativas, execução sequencial e `tool_choice=required` antes da primeira resposta. No Qwen, usa-se `reasoning_effort=none`, `reasoning_format=hidden` e até 512 tokens de saída para respeitar a cota observada. Para GPT-OSS, mantêm-se `reasoning_effort=low` e `include_reasoning=false`. Raciocínio interno não é apresentado ao cliente. Uma geração de ferramenta recusada pela Groq pode ser corrigida dentro do limite de seis rodadas. Referências: [function calling](https://console.groq.com/docs/tool-use/local-tool-calling) e [parâmetros de reasoning](https://console.groq.com/docs/reasoning).

<details>
<summary>Ollama opcional — preparação histórica preservada</summary>

A configuração ativa usa Groq. Os downloads anteriores foram preservados, e nenhum processo Ollama de outro projeto é encerrado automaticamente. Para escolher Ollama novamente, altere explicitamente provedor, modelo e URL no `.env`; essa opção volta a exigir recursos locais.

Com Ollama já instalado e em execução, prepare o modelo com `ollama pull qwen3:1.7b`. A variante menor foi escolhida para a máquina de aproximadamente 8 GB de RAM; a qualidade precisa ser verificada nas conversas reais. A capacidade de usar ferramentas é documentada em [Ollama tool calling](https://docs.ollama.com/capabilities/tool-calling); o modelo está no [catálogo oficial](https://ollama.com/library/qwen3:1.7b).

O runtime portátil e as camadas do modelo foram baixados das fontes oficiais e verificados por SHA-256; os registros estão em `reports/ollama_installation.json` e `reports/ollama_model.json`. Em uma nova preparação, `scripts/prepare_ollama.py` confere o SHA-256 publicado e recusa pacotes incompletos. `scripts/start_ollama.ps1 -PullModel` inicia o serviço quando necessário. Para um servidor novo, o script configura executáveis, modelos e logs em `.runtime/`, localhost e recursos de nuvem desativados, sem alterar o PATH global. Se já existir serviço na porta configurada, ele é reutilizado sem reconfiguração; foi o que ocorreu nesta validação. O Ollama cria seu par de chaves padrão em `%USERPROFILE%/.ollama` na primeira inicialização; essa escrita fora do workspace deve passar pelo controle de autorização do editor. Não se altera HOME, não se exige administrador e nenhuma chave privada é lida pelo projeto. Para encerrar um servidor iniciado por este projeto, use `scripts/stop_ollama.ps1`, que verifica o executável antes de encerrar o PID registrado.

Também é possível iniciar o servidor em primeiro plano com Python, sem executar um arquivo PowerShell ou alterar sua política de execução:

```powershell
.\python-agent\.venv\Scripts\python.exe python-agent\scripts\serve_ollama.py
```

Nesse caso, deixe esse terminal aberto e use outro terminal na pasta do desafio para iniciar o chat. `Ctrl+C` encerra o servidor. O script `prepare_model.py` pode preparar o modelo diretamente do registro oficial antes do servidor iniciar, verificando cada camada; `download_ollama.py` retoma somente o pacote oficial fixado, com conferência obrigatória do SHA-256 completo.

</details>

```powershell
# Conversa interativa: digite suas perguntas depois de iniciar.
.\python-agent\.venv\Scripts\python.exe run_agent.py chat
# Sem subcomando, também abre o chat:
.\python-agent\.venv\Scripts\python.exe run_agent.py
# Pergunta única:
.\python-agent\.venv\Scripts\python.exe run_agent.py chat --message "Quanto custa o Takamine GD20?"
# Sem sessão cadastrada, este modo retorna registration_required, sem chamar o LLM:
.\python-agent\.venv\Scripts\python.exe run_agent.py --json chat --message "Quais violões disponíveis custam até R$ 1.000?"
```

Na conversa, `/limpar` reinicia o contexto e mantém a conferência cadastral da sessão; `/sair` encerra. Use `--show-tools` para ver os nomes das consultas executadas. O histórico mantém até seis turnos completos em memória, sem gravação das mensagens por padrão. Após a entrada cadastral, você pode perguntar “Quanto custa o Takamine GD20?” e depois “Esse modelo está disponível?”, sem escrever nomes de comandos internos.

Também há adaptadores para APIs OpenAI e compatíveis, caso sejam escolhidas depois. Configure `LLM_PROVIDER=openai`, um modelo com function calling em `LLM_MODEL` e `OPENAI_API_KEY` somente no `.env` local. Para outro endpoint, use `openai_compatible`, `LLM_BASE_URL` e `LLM_API_KEY`. Endpoints remotos exigem HTTPS; redirecionamentos são recusados. O protocolo segue a [documentação oficial de function calling](https://developers.openai.com/api/docs/guides/function-calling). Com APIs externas, mensagens da conversa e resultados públicos das ferramentas são enviados ao provedor; os registros dos CSVs privados de clientes e pedidos não são enviados.

## Ambiente e execução

Python 3.10 ou superior. O transporte de saída para o LLM usa `urllib` da biblioteca padrão; a leitura do PDF requer `pypdf==6.21.4`, já instalado no ambiente virtual deste workspace. A API local adiciona FastAPI/Uvicorn, com instalação descrita em [API.md](../docs/API.md). **O chat requer um LLM real acessível; consultas determinísticas e testes com dublês funcionam sem API externa.** Os comandos abaixo partem da **raiz do desafio**, onde ficam `run_agent.py` e `data/`.

```powershell
# Use o executável Python 3.10+ disponível no seu computador.
python -m venv python-agent\.venv
.\python-agent\.venv\Scripts\python.exe -m pip install pypdf==6.21.4
.\python-agent\.venv\Scripts\python.exe run_agent.py --help
.\python-agent\.venv\Scripts\python.exe run_agent.py audit
.\python-agent\.venv\Scripts\python.exe run_agent.py categories
.\python-agent\.venv\Scripts\python.exe run_agent.py products --query "Takamine GD20"
.\python-agent\.venv\Scripts\python.exe run_agent.py products --category "Violões" --max-price "R$ 1.000,00"
.\python-agent\.venv\Scripts\python.exe run_agent.py products --category "Guitarras" --limit 3 --offset 0
.\python-agent\.venv\Scripts\python.exe run_agent.py products --category "Violões" --sort price_asc --limit 1
.\python-agent\.venv\Scripts\python.exe run_agent.py products --category "Ukuleles"
.\python-agent\.venv\Scripts\python.exe run_agent.py promotions --limit 20
.\python-agent\.venv\Scripts\python.exe run_agent.py product 96 --alternative-max 1000
.\python-agent\.venv\Scripts\python.exe run_agent.py order-status 1
```

Se `python` não estiver no PATH, substitua-o pelo caminho do executável instalado para a criação do ambiente. Depois, use o Python local de `.venv` como nos comandos acima. Não é necessário ativar o ambiente nem modificar a política de execução do PowerShell.

Para JSON com arquivos-fonte, IDs e identificação do snapshot, coloque `--json` **antes** do subcomando:

```powershell
.\python-agent\.venv\Scripts\python.exe run_agent.py --json products --query "Takamine GD20"
.\python-agent\.venv\Scripts\python.exe run_agent.py --json audit
```

A execução também funciona dentro de `python-agent/` usando `.venv\Scripts\python.exe -m emporio_agent ...`. Caminhos de código e dados são resolvidos a partir dos arquivos do projeto, não do diretório corrente.

## Configuração dos dados

1. `DATA_DIR` do ambiente do processo, se definido.
2. `DATA_DIR` em `python-agent/.env`; depois, `.env` da raiz do desafio.
3. `data/` da raiz do desafio; depois, `data/` do workspace pai e `python-agent/data/`.
4. Somente como último fallback de desenvolvimento, a localização Windows fornecida pelo proprietário, se existir. O único literal absoluto fica na configuração de infraestrutura, fora da lógica de negócio.

Sem configuração, a pasta `data/` já existente é encontrada automaticamente. Caso deseje configurar, copie `python-agent/.env.example` para `python-agent/.env`. O exemplo usa `DATA_DIR=../data`. Caminhos relativos em `.env` são relativos ao próprio `.env`; `DATA_DIR` do processo é relativo à raiz do desafio. Uma configuração explícita inválida produz erro, sem trocar silenciosamente de dataset. O leitor de `.env` aceita apenas atribuições simples de `DATA_DIR`; não executa comandos nem expande variáveis.

São obrigatórios os seis arquivos com os nomes originais `desafio_tecnico_ai_eng - {categories,customers,products,orders,order_items,promotions}.csv`. Mensagens de erro indicam arquivo/campo/linha, sem imprimir valores privados ou caminhos pessoais.

## Arquitetura e decisões

- `config.py`: resolução de diretório e `.env` sem dependência externa.
- `data.py`: leitura UTF-8/UTF-8 com BOM e vírgula, validação de estrutura, campos obrigatórios, chaves, relacionamentos, inteiros, datas ISO, JSON de especificações e valores monetários. Colunas extras são auditadas e ignoradas. Os seis CSVs são lidos para auditoria; registros de clientes e pedidos são descartados depois da validação.
- `models.py`: tipos explícitos e valores monetários em `Decimal`.
- `catalog.py`: ferramentas públicas para categorias, busca, detalhe, alternativas e promoções. Não executa SQL, `eval` nem código fornecido pelo usuário. Respostas incluem proveniência.
- `cli.py`: entrada do chat e comandos determinísticos, paginação e resposta JSON.
- `agent.py`: persona, ciclo de function calling, memória por sessão, limites de chamadas e verificação adicional de preços monetários.
- `tools.py`: schemas e lista fechada de funções; argumentos são validados novamente no Python. O LLM não recebe acesso livre ao sistema de arquivos ou SQL.
- `policies.py`: leitura do PDF operacional com pypdf, índice por seções, cache invalidado pelo conteúdo e fontes com páginas, versão e SHA-256. O modelo escolhe o tema; recebe os trechos correspondentes em vez de respostas prontas do caderno.
- `policy_calculations.py`: quatro calculadoras com Decimal para parcelamento, pagamento misto, desconto e frete local; as regras numéricas são extraídas do PDF. São simulações, sem executar transações.
- `policy_guards.py`: conferência posterior dos valores calculados, divergências de contatos e distinções necessárias nas políticas, com pedido de correção ao modelo quando necessário.
- Em devolução personalizada, se o modelo insistir em uma conclusão sem fundamento após correção, o agente exibe os trechos efetivamente recuperados e pede análise da equipe. Essa saída conservadora não confirma nem nega automaticamente a devolução e não substitui o PDF por uma resposta cadastrada.
- As ferramentas do LLM são menores que a API interna do catálogo: busca por nome/modelo, listagem disponível por categoria, mais barato e promoções têm interfaces separadas. `constraints.py` confere tetos numéricos explícitos como “até R$ 1.000” no Python, sem decidir intenção ou substituir o LLM. Essa proteção foi acrescentada após um teste real em que o modelo inverteu mínimo e máximo.
- A consulta por ID só é oferecida ao LLM depois de o produto aparecer nas consultas da conversa; IDs são limitados por enum e conferidos novamente no Python. Uma resposta que mencione o nome completo de outro produto do catálogo exige nova consulta antes de ser liberada. A busca por nome de um único produto indisponível já inclui até três alternativas verificadas. Listagens incompletas recebem aviso de paginação calculado pelo Python.
- `llm.py` e `llm_config.py`: transporte HTTP para Ollama e APIs compatíveis, configuração de modelo e mensagens sanitizadas de erro.
- No Ollama, a primeira chamada de cada pergunta usa [saída estruturada por JSON Schema](https://docs.ollama.com/capabilities/structured-outputs) para que o próprio LLM escolha obrigatoriamente uma ferramenta e seus argumentos. O Python valida e executa a escolha; a chamada seguinte recebe as evidências e gera a resposta em linguagem natural, podendo consultar mais ferramentas. Isso evita responder apenas pela memória de uma conversa anterior. Em APIs compatíveis, usa-se `tool_choice=required` na primeira chamada.
- `chat_cli.py`: conversa interativa e pergunta única. O LLM escolhe ferramentas pelo significado; não é um menu de palavras-chave.
- `tests/` e `scripts/validate.py`: testes de integração, dados inválidos em cópias temporárias, execução real da CLI e evidências de preservação dos originais.

**Disponibilidade:** somente `status == active` **e** `stock_quantity > 0`. `coming_soon` e `discontinued` não são vendidos mesmo com estoque positivo. A busca inclui apenas disponíveis por padrão; `--include-unavailable` permite consultar o catálogo completo e mantém a disponibilidade explícita.

**Busca no catálogo:** a ferramenta determinística combina todos os termos de nome/modelo, ignorando caixa e acentos. Categoria vem da tabela, com alguns aliases de singular; IDs não são fixados na regra de categoria. Uma categoria ambígua exige nome completo ou ID. A interpretação da pergunta em linguagem natural e a escolha de ferramentas e filtros ficam com o LLM; a busca interna não usa embeddings nem correção automática de erros de digitação.

**Preços e paginação:** filtros usam preço de tabela. Promoção é uma consulta separada. Aceitam-se `1000`, `1000.50`, `1000,50` e `R$ 1.000,50`; use duas casas ou vírgula para evitar ambiguidades de separador. Ordenação por preço/nome tem desempate estável por ID. Limite padrão 5, máximo 20, com `offset` e `next_offset`.

**Promoções:** cruza os dois CSVs, exige `is_active == 1` e produto disponível. Calcula o preço final com `Decimal` e `ROUND_HALF_UP`, apresentando original, percentual e final. Não infere vigência pelo nome da campanha ou pela data atual, pois não existem datas de validade. Não soma promoções nem desconto PIX. Se futuramente houver múltiplas promoções ativas no mesmo produto, adota o maior percentual, com desempate pelo menor ID; essa é uma decisão do protótipo, não um campo do dataset.

**Alternativas:** até três produtos disponíveis na mesma categoria. Sem limites fornecidos, usa faixa de 70% a 130% do preço do produto indisponível, por proximidade de preço; é uma heurística documentada. Limites explícitos substituem essa faixa; se apenas um for informado, o outro fica aberto dentro do intervalo suportado (zero a um bilhão de reais). Se não houver candidato, retorna lista vazia, sem inventar sugestões.

**Divergência do baseline fornecido:** a alegação de ausência de violões até R$ 1.000,00 não corresponde aos CSVs locais. Existem opções disponíveis, incluindo o Tagima Memphis AC-39 por R$ 429,90, com estoque 15. A consulta usa os registros locais; o produto 96 continua excluído por estoque zero. A verificação e os IDs encontrados constam em `reports/audit.json`.

**Privacidade:** `order-status` sempre exige verificação segura e retorna a mesma negativa para qualquer ID; nem sequer lê os CSVs. Não há parâmetro que permita autenticar por nome, e-mail, telefone ou por uma flag booleana. O catálogo público não contém objetos de clientes/pedidos. A auditoria administrativa registra somente contagens, hashes, campos e IDs de grupos com e-mail ambíguo, nunca os e-mails ou telefones.

**Snapshots:** cada execução lê os arquivos. `loaded_at_utc` é o instante de leitura, não a data de atualização do estoque; `snapshot_sha256` identifica o conteúdo. A resposta sempre informa que não representa dados em tempo real. Fontes, filtros e IDs permitem conferir os resultados.

## Políticas e critérios do desafio

O enunciado foi lido na auditoria. **O manual `data/políticas_da_loja.pdf` é uma fonte consultada em execução:** o LLM seleciona `consultar_politicas` e o Python recupera as seções correspondentes entre as 29 entradas indexadas. A resposta cita páginas e seções. Essa abordagem de retrieval usa a estrutura deste PDF curto, sem embeddings ou banco vetorial. Um arquivo ausente, inválido ou sem texto gera erro seguro; não há OCR.

Com autorização expressa da proprietária, apenas os trechos necessários do manual fictício são enviados à Groq. Cadastros privados de clientes e pedidos não são enviados. Divergências de telefone/e-mail e lacunas sobre PIX parcial, frete exatamente em R$ 500,00 e personalização são preservadas para confirmação com a equipe. Regras de troca não substituem a garantia legal descrita no manual. A política de exclusão é explicada sem afirmar que dados foram apagados.

O README cobre decisões, comandos, limitações e uso de assistente. O Git público continua pendente. Os cinco exemplos antigos são execuções determinísticas; as oito perguntas históricas com Groq estão em `examples/conversas_groq_executadas.md`. O caderno `examples/conversas_groq.md` mantém essas transcrições e agora contém as vinte novas respostas reais. As referências preparadas foram preservadas em `examples/conversas_groq_roteiros_referencia.md`; a rodada atual inteira está em `examples/conversas_28_executadas.md`. As tentativas anteriores com Ollama são históricas e não comprovam a qualidade do provedor atual. Dublês e roteiros preparados não são apresentados como inferência real.

## Validação e resultados

```powershell
.\python-agent\.venv\Scripts\python.exe -X utf8 -m unittest discover -s python-agent\tests -v
.\python-agent\.venv\Scripts\python.exe -X utf8 python-agent\scripts\validate.py
.\python-agent\.venv\Scripts\python.exe -X utf8 python-agent\scripts\validate_chat.py
.\python-agent\.venv\Scripts\python.exe -X utf8 python-agent\scripts\validate_policies.py
# Com a chave Groq configurada, validações reais:
.\python-agent\.venv\Scripts\python.exe -X utf8 python-agent\scripts\live_all_questions.py
.\python-agent\.venv\Scripts\python.exe -X utf8 python-agent\scripts\validate_policy_cli.py
```

O segundo comando registra `reports/audit.json`, `reports/validation.json`, `reports/tests.txt` e `examples/consultas_cli.md`. As evidências incluem resultados reais, oito cenários da CLI e hashes antes/depois dos seis CSVs. Os testes de baseline verificam este conjunto específico; outra base válida pode exigir ajuste dos testes de integração, sem mudar as consultas. Os testes de corrupção usam cópias temporárias, jamais os originais.

`validate_chat.py` registra testes controlados e hashes em `reports/chat_validation.json`. A suíte real da Groq registra oito perguntas em cinco conversas, fontes, ferramentas, duração e critérios calculados dos CSVs em `reports/groq_live_validation.json`; completar requisições não basta para aprovação. A verificação por subprocesso da CLI registra cinco casos em `reports/groq_cli_live.json`. Uma revisão semântica das respostas ainda é necessária: esses critérios não provam qualquer comportamento possível do LLM.

`validate_policies.py` registra os testes atuais e a preservação do PDF e dos seis CSVs em `reports/policies_validation.json`. `live_all_questions.py` verifica as oito perguntas anteriores e as vinte de políticas; somente uma rodada completa aprovada gera `examples/conversas_28_executadas.md`. Use `--resume` para continuar com a mesma implementação, fontes e modelo, reaproveitando casos aprovados. `validate_policy_cli.py` confirmou o PDF pela CLI real e gravou `reports/policies_cli_live.json`. `publish_validated_examples.py` atualiza o caderno local com as vinte respostas reais, preservando as referências. `review_policy_artifacts.py` confere fontes, implementação e hashes das evidências; não chama o provedor.

Na Groq, os scripts de avaliação usam um intervalo de 60 segundos entre perguntas para respeitar cotas gratuitas; ajuste com `--pause-seconds 0..60` quando necessário. Esse intervalo não é aplicado fixamente ao chat interativo. A resposta comercial não pode prometer prontidão de envio ou entrega imediata a partir do estoque CSV; o agente pede correção se o modelo acrescentar essas afirmações.

## Limitações e próximas fases supervisionadas

O funcionamento atual depende da Groq e de internet, sujeito a cotas e disponibilidade do serviço. Cadastro no Supabase e API FastAPI local estão implementados; autenticação real, persistência do histórico, publicação do backend e interface permanecem para fases seguintes. As sessões da API ficam em memória em um único processo e expiram; consulte [os limites](../docs/API.md). O índice depende dos títulos e da numeração deste manual; mudanças de estrutura exigem revisão. Não há cotação externa por CEP ou calendário de feriados. O guard de teto reconhece formas numéricas explícitas com moeda/reais; outras expressões dependem da interpretação do LLM. A proteção de preços e nomes/prefixos únicos confere evidências, mas não prova fidelidade semântica completa. Existem limites de seis rodadas, oito chamadas de ferramentas e tamanho das mensagens, além de timeout. Turnos antigos podem ser retirados do contexto enviado; guardar seis turnos não implica envio integral de todos eles. O adaptador Ollama preservado usa 4.096 tokens e pode ser lento nesta máquina de 8 GB. Somente Groq tem a nova validação remota; outros adaptadores continuam com testes HTTP controlados.

Não há reserva de estoque, escrita nos CSVs, compra, alteração de pedido, verificação de validade de promoção nem reconciliação de total de pedido com preço histórico: os campos necessários não foram fornecidos.

## Uso de assistente de código

Foi utilizado **Codex, da OpenAI**, para inspecionar arquivos locais, ler o enunciado/manual, implementar as Fases 0, 1, a camada conversacional, a consulta ao PDF com calculadoras, o cadastro e a API local, escrever testes e executar as validações registradas. As decisões e limitações ficam disponíveis para revisão. Não se afirma autoria exclusivamente humana nem inferência real onde só houve teste controlado. Os resultados registrados distinguem execução determinística, dublês HTTP/LLM e validação com modelo real.
