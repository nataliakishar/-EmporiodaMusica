"""Chat com LLM e comandos determinísticos de consulta e auditoria."""

import argparse
import json
import sys

from .catalog import Catalog, order_status
from .config import ConfigurationError, resolve_data_dir
from .data import DataValidationError, load_snapshot
from .models import QueryError, parse_price
from .llm import LLMError
from .registration import RegistrationError


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description="Empório da Música — chat com LLM e consultas verificáveis aos CSVs.")
    root.add_argument("--json", action="store_true", help="Resposta estruturada com fontes e IDs.")
    commands = root.add_subparsers(dest="command", required=True)
    chat = commands.add_parser("chat", help="Converse em português com um LLM que consulta os CSVs.")
    chat.add_argument("--message", help="Uma pergunta natural; omita para conversar interativamente.")
    chat.add_argument("--show-tools", action="store_true", help="Exibe os nomes das consultas executadas.")
    register=commands.add_parser('register',help='Confere os contatos e abre o chat; os dados de cadastro não são enviados ao LLM.')
    register.add_argument('--dry-run',action='store_true',help='Valida os dados sem gravar nem acessar serviços.')
    register.add_argument('--confirm',action='store_true',help='Confirma o envio no modo --json; os dados são lidos da entrada padrão.')
    commands.add_parser("audit", help="Auditoria administrativa sanitizada dos seis CSVs.")
    commands.add_parser("categories", help="Categorias existentes.")
    products = commands.add_parser("products", help="Busca por nome/modelo e filtros explícitos.")
    products.add_argument("--query", default="")
    products.add_argument("--category")
    products.add_argument("--min-price", type=parse_price)
    products.add_argument("--max-price", type=parse_price)
    products.add_argument("--include-unavailable", action="store_true")
    products.add_argument("--sort", choices=("price_asc", "price_desc", "name"), default="price_asc")
    product = commands.add_parser("product", help="Preço, disponibilidade e alternativas por ID.")
    product.add_argument("product_id", type=int)
    product.add_argument("--alternative-min", type=parse_price)
    product.add_argument("--alternative-max", type=parse_price)
    promotions = commands.add_parser("promotions", help="Promoções ativas de produtos elegíveis.")
    for command in (products, promotions):
        command.add_argument("--limit", type=int, default=5)
        command.add_argument("--offset", type=int, default=0)
    private = commands.add_parser("order-status", help="Explica a necessidade de autenticação; não consulta pedidos.")
    private.add_argument("order_id", type=int, nargs="?")
    return root


def render(result: dict) -> str:
    if "tables" in result:
        lines = ["Auditoria válida — fontes locais preservadas."]
        lines.extend(f"{name}: {info['rows']} registros" for name, info in result["tables"].items())
        lines.append(f"Relacionamentos válidos: {len(result['relationships'])}")
        lines.append(f"Promoções marcadas ativas: {result['findings']['active_promotions']}")
        lines.append("Relatório completo: execute --json audit.")
        return "\n".join(lines)
    lines = [result["message"]] if "message" in result else []
    items = [result["item"]] if "item" in result else result.get("items", [])
    for item in items:
        if "product_id" not in item:
            lines.append(f"[{item['category_id']}] {item['name']} — {item['description']}")
            continue
        line = f"[{item['product_id']}] {item['name']} — {item['price_formatted']} — {item['availability_message']}"
        if "final_price_formatted" in item:
            line += f" Original: {item['original_price_formatted']}; desconto: {item['discount_percent']}%; final: {item['final_price_formatted']}."
        lines.append(line)
    if "total" in result:
        lines.append(f"Exibidos: {len(items)} de {result['total']} resultados.")
        if result["next_offset"] is not None:
            lines.append(f"Próxima página: use --offset {result['next_offset']}.")
    if result.get("alternatives"):
        lines.append("Alternativas disponíveis na mesma categoria e faixa de preço:")
        lines.extend(f"[{p['product_id']}] {p['name']} — {p['price_formatted']}" for p in result["alternatives"])
    elif "item" in result and not result["item"]["available"]:
        lines.append("Não encontrei alternativas disponíveis nessa faixa de preço.")
    if result.get("notice"):
        lines.append(result["notice"])
    if result.get("source"):
        lines.append("Fontes: " + "; ".join(result["source"]["files"]))
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    if argv == [] or (argv is None and len(sys.argv) == 1):
        argv = ["chat"]
    args = parser().parse_args(argv)
    try:
        if args.command=='register':
            if not args.json and not args.dry_run:
                from .chat_cli import run_chat
                return run_chat(registration_first=True)
            from .registration_cli import run_registration
            return run_registration(args.json,args.dry_run,args.confirm)
        if args.command == "chat":
            from .chat_cli import run_chat
            return run_chat(args.message, args.json, args.show_tools)
        # A negativa independe de arquivos/IDs; nunca revela se um pedido existe.
        if args.command == "order-status":
            result = order_status(args.order_id)
        else:
            snapshot = load_snapshot(resolve_data_dir())
            catalog = Catalog(snapshot)
            if args.command == "audit":
                result = snapshot.audit
            elif args.command == "categories":
                result = catalog.categories()
            elif args.command == "products":
                result = catalog.products(query=args.query, category=args.category,
                                          min_price=args.min_price, max_price=args.max_price,
                                          available_only=not args.include_unavailable,
                                          sort=args.sort, limit=args.limit, offset=args.offset)
            elif args.command == "product":
                result = catalog.product(args.product_id, args.alternative_min, args.alternative_max)
            else:
                result = catalog.promotions(limit=args.limit, offset=args.offset)
        print(json.dumps(result, ensure_ascii=False, indent=2) if args.json else render(result))
        return 0
    except (ConfigurationError, DataValidationError, QueryError, LLMError, RegistrationError) as exc:
        code='registration_error' if isinstance(exc,RegistrationError) else ('llm_error' if isinstance(exc,LLMError) else 'invalid_configuration_or_query')
        error = {"code": code, "message": str(exc)}
        print(json.dumps(error, ensure_ascii=False) if args.json else f"Erro: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
