"""Retrieval leve por seções do PDF operacional, com páginas e SHA-256."""

from bisect import bisect_right
from functools import lru_cache
import hashlib
from io import BytesIO
from pathlib import Path
import re
import unicodedata

from .models import QueryError

FILENAME = "políticas_da_loja.pdf"
HEADINGS = {
    "1": "Sobre a Empório da Música", "1.1": "Missão", "1.2": "Dados da Empresa",
    "2": "Horário de Funcionamento", "3": "Formas de Pagamento", "3.1": "Regras de Parcelamento",
    "4": "Política de Trocas e Devoluções", "4.1": "Direito de Arrependimento", "4.2": "Trocas por Defeito",
    "4.3": "Trocas por Preferência", "4.4": "Itens Não Elegíveis para Troca",
    "5": "Política de Frete e Entregas", "5.1": "Entregas na Região Metropolitana", "5.2": "Entregas para Outras Cidades",
    "5.3": "Código de Rastreamento", "6": "Promoções e Descontos", "6.1": "Tipos de Promoção", "6.2": "Regras de Promoções",
    "7": "Atendimento via WhatsApp", "7.1": "Diretrizes de Atendimento", "7.2": "Fluxo de Atendimento Padrão",
    "7.3": "Situações Especiais", "8": "Garantia", "8.1": "Garantia Legal", "8.2": "Garantia do Fabricante",
    "8.3": "O que Não Cobre a Garantia", "9": "Privacidade e Proteção de Dados", "10": "Disposições Finais",
}
TOPICS = {
    "empresa": ("1", "1.2", "7"), "horarios": ("2", "7"),
    "pagamentos": ("3", "3.1", "6.2"), "trocas": ("4.1", "4.2", "4.3", "4.4"),
    "devolucoes": ("4.1", "4.4", "10"), "frete": ("5.1", "5.2"),
    "entregas": ("5.2", "5.3"), "promocoes": ("6.1", "6.2", "7.3"),
    "garantia": ("8.1", "8.2", "8.3", "4.2"), "privacidade": ("9", "7", "1.2"),
    "escopo": ("1",),
}


class PolicyError(QueryError):
    pass


@lru_cache(maxsize=2)
def _extract(data: bytes):
    try:
        from pypdf import PdfReader
        reader = PdfReader(BytesIO(data))
        if reader.is_encrypted or not 1 <= len(reader.pages) <= 50:
            raise ValueError
        pages = []
        for page in reader.pages:
            contents = page.get_contents()
            if contents and len(contents.get_data()) > 5_000_000:
                raise ValueError
            text = unicodedata.normalize("NFKC", page.extract_text() or "")
            text = " ".join(text.split())
            text = re.sub(r"Empório da Música Manual de Políticas e Procedimentos", "", text)
            text = re.sub(r"Página \d+", "", text).strip()
            if len(text) < 30:
                raise ValueError
            pages.append(text)
    except ImportError:
        raise PolicyError("Instale a dependência pypdf no ambiente virtual para consultar políticas_da_loja.pdf.") from None
    except Exception:
        raise PolicyError("Não foi possível extrair políticas_da_loja.pdf. Confira o PDF configurado por DATA_DIR; a consulta requer texto legível.") from None
    joined = "\n".join(pages)
    offsets = []
    offset = 0
    for page in pages:
        offsets.append(offset)
        offset += len(page) + 1
    found = []
    for section, heading in HEADINGS.items():
        number = re.escape(section) + (r"\." if "." not in section else "")
        title = r"\s+".join(re.escape(word) for word in heading.split())
        matches = list(re.finditer(r"(?<![\d.])" + number + r"\s+" + title, joined, flags=re.IGNORECASE))
        if len(matches) != 1:
            raise PolicyError(f"A seção {section} de políticas_da_loja.pdf não pôde ser identificada sem ambiguidade. Confirme a versão do manual.")
        found.append((matches[0].start(), section, heading))
    found.sort()
    sections = {"capa": {"section": "capa", "title": "Capa e contatos", "pages": [1], "text": pages[0]}}
    for index, (start, section, heading) in enumerate(found):
        end = found[index + 1][0] if index + 1 < len(found) else len(joined)
        sections[section] = {"section": section, "title": heading,
                             "pages": list(range(bisect_right(offsets, start), bisect_right(offsets, max(start, end - 1)) + 1)),
                             "text": " ".join(joined[start:end].split())}
    return sections


class PolicyStore:
    def __init__(self, data_dir: Path):
        self.path = data_dir / FILENAME

    def load(self):
        try:
            if self.path.stat().st_size > 10_000_000:
                raise ValueError
            data = self.path.read_bytes()
        except (OSError, ValueError):
            raise PolicyError("Não foi possível ler políticas_da_loja.pdf. Confira o arquivo no diretório indicado por DATA_DIR.") from None
        return _extract(data), hashlib.sha256(data).hexdigest()

    def lookup(self, topic: str) -> dict:
        if topic not in TOPICS:
            raise PolicyError("Tema de políticas inválido. Escolha um tema do schema.")
        return self.retrieve(TOPICS[topic], topic)

    def retrieve(self, identifiers, topic="regras"):
        sections, digest = self.load()
        passages = [dict(sections[key]) for key in dict.fromkeys(identifiers)]
        notes = []
        if any(key in identifiers for key in ("capa", "1.2", "7", "9")):
            emails = {v for key in ("capa", "1.2") for v in re.findall(r"[\w.+-]+@[\w.-]+\.[a-zA-Z]{2,}", sections[key]["text"])}
            if len(emails) > 1:
                notes.append("O manual apresenta grafias diferentes de e-mail na capa e na seção 1.2; não escolha silenciosamente uma como confirmada. Oriente confirmar com a equipe pelo WhatsApp da seção 7.")
            notes.append("Para WhatsApp, a seção 7 identifica o canal principal; a tabela 1.2 apresenta outro telefone/WhatsApp. Preserve a distinção e sinalize a divergência quando relevante.")
        if topic == "empresa":
            notes.append("A descrição de mais de 300 instrumentos é institucional, do manual; não é a contagem do snapshot CSV operacional.")
        contacts = {}
        for key, label in (("7", "whatsapp_primary"), ("1.2", "company_telephone")):
            if key in identifiers:
                match = re.search(r"\((\d{2})\)\s*(\d{4,5})\s*-\s*(\d{4})", sections[key]["text"])
                if match:
                    contacts[label] = f"({match.group(1)}) {match.group(2)}-{match.group(3)}"
        version = re.search(r"Versão\s+([\d.]+)", sections["capa"]["text"])
        return {"code": "policy_evidence", "topic": topic, "passages": passages, "notes": notes, "contacts": contacts,
                "source": {"files": [FILENAME], "sections": list(dict.fromkeys(identifiers)),
                           "pages": sorted({p for chunk in passages for p in chunk["pages"]}),
                           "document_sha256": digest, "version": version.group(1) if version else None,
                           "method": "extração PDF em execução e retrieval por seção"}}
