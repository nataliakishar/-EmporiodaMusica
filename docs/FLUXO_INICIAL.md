# Entrada obrigatória do atendimento

Esta mudança afeta somente a entrada do chat. O núcleo do LLM, as ferramentas,
os cálculos, os CSVs e o PDF continuam iguais. Não foi criada interface web,
autenticação de pedidos ou importação dos clientes do CSV.

1. O cliente envia a primeira pergunta.
2. Antes de enviá-la ao LLM, o chat explica a finalidade da coleta, menciona a
   transparência prevista na LGPD e solicita nome, telefone e e-mail.
3. O cliente confere os dados e confirma o envio. Recusar ou cancelar encerra
   este atendimento sem enviar a pergunta ao modelo.
4. O backend confere telefone **e** e-mail no mesmo registro do Supabase:
   - Se houver correspondência, agradece o retorno, sem criar outro registro
     ou alterar o cadastro encontrado.
   - Sem correspondência do par, grava o novo cadastro, agradece e apresenta
     o protocolo. Uma coincidência isolada não identifica o cliente.
5. A pergunta original é encaminhada ao agente, sem pedir que seja digitada
   novamente. Os campos coletados não entram no contexto do LLM.

O cadastro fica conferido somente durante a sessão atual. `/limpar` apaga o
contexto da conversa e mantém essa conferência; uma nova execução solicita os
contatos novamente. A correspondência não autentica pedidos privados.

## Executar

Na raiz do desafio:

```powershell
.\python-agent\.venv\Scripts\python.exe run_agent.py chat
```

`/cadastro` pode antecipar a coleta. O comando avulso `register` continua
funcionando como antes. `chat --message` também exige a conferência interativa.
`--json chat --message` sem sessão cadastrada retorna `registration_required`
e código de saída 2, sem chamar o LLM. Não existe uma flag que dispense essa
etapa; a integração de sessões pela FastAPI será tratada na próxima fase.

## Consulta restrita

O novo módulo `conversation_registration.py` chama uma RPC fixa de backend,
que resolve a consulta e a eventual inclusão na mesma transação. Um bloqueio
por par de contatos evita duplicações entre duas sessões simultâneas. Repetir
a mesma submissão após uma falha de rede mantém o protocolo e o resultado de
cadastro novo; não sobrescreve dados.

A RPC pública usa `SECURITY INVOKER`. Sua implementação fica em esquema privado,
com `SECURITY DEFINER`, caminho de busca fixo, SQL parametrizado e execução
restrita ao backend. Ela não retorna contatos, nomes ou protocolo já armazenado
para um cliente existente. A chave de backend continua sem leitura direta de
telefone/e-mail da tabela. Nenhuma credencial foi incluída no GitHub.

A obrigatoriedade é uma regra deste fluxo. A menção à LGPD explica a finalidade
e a conferência dos dados; não representa uma alegação de que a lei obriga esse
cadastro ou de conformidade automática.

## Validação focada

```powershell
.\python-agent\.venv\Scripts\python.exe -X utf8 python-agent\scripts\validate_conversation_entry.py
```

Foram aprovados **36 testes focados**: 18 da nova entrada e 18 do cadastro
reutilizado. Nenhum teste das 28 conversas remotas foi repetido. A integração
real verificou retorno, novo cadastro, coincidências parciais, contatos em
registros diferentes, repetição técnica, concorrência, preservação do nome
existente e a CLI. Os cinco registros sintéticos criados foram removidos e a
limpeza foi conferida por seus IDs. Não foram feitas chamadas novas à Groq.

Os avisos de assessoria são somente informativos: [RLS sem política pública](https://supabase.com/docs/guides/database/database-linter?lint=0008_rls_enabled_no_policy)
é intencional para esta tabela exclusiva do backend; [índice ainda não utilizado](https://supabase.com/docs/guides/database/database-linter?lint=0005_unused_index)
é esperado na tabela pequena, em que o planejador pode preferir leitura sequencial.
Não foram desativadas proteções para eliminar esses avisos.

Relatórios locais: `python-agent/reports/conversation_gate_validation.json` e
`python-agent/reports/conversation_gate_live.json`. Os campos coletados não são
incluídos nesses relatórios. Codex auxiliou na implementação e validação.
