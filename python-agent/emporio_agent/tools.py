"""Lista fechada de ferramentas: o LLM propõe; o Python valida e executa."""

import json
from copy import deepcopy

from .catalog import Catalog, order_status
from .models import QueryError, parse_price
from .policies import PolicyStore, PolicyError, TOPICS
from .policy_calculations import simulate
from .config import resolve_data_dir


def tool(name, description, properties=None, required=None):
    properties = deepcopy(properties or {})
    for key, prop in properties.items():
        if key not in (required or []):
            prop["type"] = [prop["type"], "null"]
    return {"type": "function", "function": {"name": name, "description": description,
            "parameters": {"type": "object", "properties": properties,
                           "required": required or [], "additionalProperties": False}}}


PRICE = {"type": "string", "description": "Valor decimal, por exemplo 1000.00; nunca float."}
TOOLS = [
    tool("listar_categorias", "Lista as categorias reais e seus IDs; use para resolver dúvidas de categoria."),
    tool("buscar_modelo", "Busca nome/modelo citado, incluindo indisponíveis; retorna preço, estoque e até três alternativas se indisponível. query só nome/modelo.", {
        "query": {"type": "string", "description": "Somente nome/modelo: Takamine GD20. Sem palavras da pergunta."},
        "preco_maximo_alternativas_brl": PRICE,
    }, ["query"]),
    tool("consultar_produtos", "Lista disponíveis por categoria, preço crescente, cinco por página. preco_maximo_brl é teto inclusivo, opcional.", {
        "categoria": {"type": "string", "description": "Categoria: Violões, Guitarras ou Ukuleles, por exemplo."},
        "preco_maximo_brl": {"type": "string", "description": "TETO inclusivo: para ATÉ 1000 reais, use 1000.00. Omita se não solicitado."},
        "pagina": {"type": "integer", "minimum": 1, "maximum": 200000},
    }, ["categoria"]),
    tool("mais_barato", "Retorna somente o instrumento MAIS BARATO DISPONÍVEL da categoria. Use para pedidos de mais barato, inclusive em continuação da conversa.", {
        "categoria": {"type": "string"}, "preco_maximo_brl": PRICE,
    }, ["categoria"]),
    tool("consultar_produto", "Consulta um ID conhecido no catálogo: preço, status, estoque, especificações e até 3 alternativas elegíveis quando indisponível. Nunca invente IDs.", {
        "product_id": {"type": "integer", "minimum": 1}, "preco_maximo_alternativas_brl": PRICE,
    }, ["product_id"]),
    tool("consultar_promocoes", "Lista promoções ativas de produtos disponíveis, com original, percentual e final calculados. Sem vigência informada e sem cumulatividade; até cinco resultados."),
    tool("consultar_pedido", "SOMENTE status/rastreio de pedido específico: exige autenticação indisponível. Para explicações gerais sobre envio/rastreamento/avarias, consulte políticas de entregas."),
    tool("consultar_escopo_loja", "Use quando perguntarem se vendemos palhetas, pedais, amplificadores, cordas, cabos ou cases. É uma dúvida de atendimento da loja. Consulta o manual revisado e informa que vendemos somente instrumentos musicais, sem acessórios."),
    tool("informacoes_loja", "Consulta o PDF sobre identidade/escopo. Para regras específicas, use consultar_politicas.", {
        "topic": {"type": "string", "enum": ["identidade", "escopo", "politicas"]},
    }, ["topic"]),
    tool("consultar_politicas", "Recupera seções do PDF com páginas. Use para empresa/endereço, horários, pagamentos, trocas, devoluções, frete, entregas/rastreio geral, promoções, garantia ou privacidade. Para cálculos, use diretamente a ferramenta calcular_*: ela também lê as regras do PDF.", {
        "topico": {"type": "string", "enum": list(TOPICS)},
    }, ["topico"]),
    tool("calcular_parcelamento", "Simula parcelamento sem juros por regras lidas do PDF; use diretamente para valores e número de parcelas informados.", {
        "valor_brl": PRICE, "parcelas": {"type": "integer", "minimum": 1, "maximum": 120},
    }, ["valor_brl", "parcelas"]),
    tool("calcular_pagamento_misto", "Simula PIX parcial + cartão, consultando o limite no PDF. Não aplica desconto PIX parcial sem regra explícita.", {
        "valor_brl": PRICE, "valor_pix_brl": PRICE,
    }, ["valor_brl", "valor_pix_brl"]),
    tool("calcular_desconto", "Simula desconto sobre valor informado, lendo a regra PIX/não cumulatividade do PDF. Não confirma campanha ativa.", {
        "valor_brl": PRICE, "desconto_percentual": PRICE, "usar_pix": {"type": "boolean"},
    }, ["valor_brl"]),
    tool("calcular_frete_local", "Simula frete/total para região metropolitana de Campo Grande pelo PDF; não faz cotação por CEP nem garante entrega.", {
        "valor_brl": PRICE,
    }, ["valor_brl"]),
    tool("fora_do_escopo", "Use SOMENTE para assuntos alheios ao atendimento musical, como futebol, política ou receitas. Perguntas sobre acessórios que não vendemos pertencem ao atendimento: use consultar_escopo_loja. Retorna orientação para voltar à loja."),
]


class ToolRegistry:
    def __init__(self, catalog: Catalog, price_ceiling=None, policy_store=None):
        self.catalog = catalog
        self.price_ceiling = price_ceiling
        self.policies = policy_store if policy_store is not None else PolicyStore(resolve_data_dir())
        self.schemas = {t["function"]["name"]: t["function"]["parameters"] for t in TOOLS}

    def execute(self, name: str, raw_arguments: str) -> dict:
        if name not in self.schemas:
            return {"code": "unknown_tool", "message": "Ferramenta não permitida. Use somente a lista fornecida."}
        try:
            arguments = json.loads(raw_arguments)
            schema = self.schemas[name]
            if not isinstance(arguments, dict) or set(arguments) - set(schema["properties"]):
                raise QueryError("Argumentos desconhecidos ou estrutura inválida.")
            if set(schema["required"]) - set(arguments):
                raise QueryError("Faltam argumentos obrigatórios da ferramenta.")
            for key in list(arguments):
                prop = schema["properties"][key]
                types = prop["type"] if isinstance(prop["type"], list) else [prop["type"]]
                if arguments[key] is None and key not in schema["required"] and "null" in types:
                    del arguments[key]
            for key, value in arguments.items():
                prop = schema["properties"][key]
                types = prop["type"] if isinstance(prop["type"], list) else [prop["type"]]
                expected = {"integer": int, "boolean": bool, "string": str}[next(t for t in types if t != "null")]
                if type(value) is not expected:
                    raise QueryError(f"O campo {key} deve ter tipo {prop['type']}; siga o schema, sem alterar o valor por suposição.")
                if isinstance(value, str) and len(value) > 200:
                    raise QueryError("Argumento textual excedeu o limite.")
                if "enum" in prop and value not in prop["enum"]:
                    raise QueryError("Valor não permitido pelo schema.")
                if "minimum" in prop and value < prop["minimum"]:
                    raise QueryError("Argumento abaixo do mínimo permitido.")
                if "maximum" in prop and value > prop["maximum"]:
                    raise QueryError("Argumento acima do máximo permitido.")
            for key in ("preco_maximo_brl", "preco_maximo_alternativas_brl"):
                if key in arguments:
                    arguments[key] = parse_price(arguments[key])
            if name == "consultar_politicas":
                return self.policies.lookup(arguments["topico"])
            if name.startswith("calcular_"):
                return simulate(self.policies, name, arguments)
            if name == "listar_categorias":
                return self.catalog.categories()
            if name == "buscar_modelo":
                if not arguments["query"].strip():
                    raise QueryError("Informe somente o nome ou modelo para buscar.")
                result = self.catalog.products(query=arguments["query"], available_only=False)
                if result["total"] == 1 and not result["items"][0]["available"]:
                    maximum = self.price_ceiling if self.price_ceiling is not None else arguments.get("preco_maximo_alternativas_brl")
                    detail = self.catalog.product(result["items"][0]["product_id"], alternative_max=maximum)
                    for field in ("alternatives", "alternative_price_range_brl", "source"):
                        result[field] = detail[field]
                return result
            if name == "consultar_produtos":
                maximum = self.price_ceiling if self.price_ceiling is not None else arguments.get("preco_maximo_brl")
                return self.catalog.products(category=arguments["categoria"], max_price=maximum,
                                             limit=5, offset=(arguments.get("pagina", 1) - 1) * 5)
            if name == "mais_barato":
                maximum = self.price_ceiling if self.price_ceiling is not None else arguments.get("preco_maximo_brl")
                return self.catalog.products(category=arguments["categoria"], max_price=maximum, limit=1)
            if name == "consultar_produto":
                maximum = self.price_ceiling if self.price_ceiling is not None else arguments.get("preco_maximo_alternativas_brl")
                return self.catalog.product(arguments["product_id"], alternative_max=maximum)
            if name == "consultar_promocoes":
                return self.catalog.promotions()
            if name == "consultar_pedido":
                return order_status()
            if name == "fora_do_escopo":
                return {"code": "out_of_scope", "message": "Posso ajudar com os instrumentos da Empório da Música, seus preços, disponibilidade e promoções. Vamos voltar ao atendimento da loja?"}
            topic = "escopo" if name == "consultar_escopo_loja" else arguments["topic"]
            if topic == "politicas":
                return {"code": "policy_topics", "message": "Escolha o tema em consultar_politicas e consulte o PDF antes de responder.", "topics": list(TOPICS)}
            return self.policies.lookup("empresa" if topic == "identidade" else "escopo")
        except PolicyError as exc:
            return {"code": "policy_source_unavailable", "message": str(exc)}
        except QueryError as exc:
            return {"code": "invalid_tool_arguments", "message": str(exc)}
        except (json.JSONDecodeError, ValueError, TypeError):
            # Não inclui argumentos recebidos na mensagem de erro: podem conter dados pessoais.
            return {"code": "invalid_tool_arguments", "message": "Argumentos inválidos. Consulte o schema e corrija a chamada; não invente resultados."}
