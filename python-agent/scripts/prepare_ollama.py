"""Valida o pacote oficial fixado e extrai o runtime portátil no projeto."""

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import stat
import zipfile

MODULE_ROOT = Path(__file__).resolve().parents[1]
RUNTIME = MODULE_ROOT / ".runtime"
VERSION = "0.40.13"
ARCHIVE_SHA256 = "7afa38624fa62ee5d8293422d0ab084c1bb4603134c7f4dafce11a033b57cc19"
URL = f"https://github.com/ollama/ollama/releases/download/v{VERSION}/ollama-windows-amd64.zip"


def main():
    archive = RUNTIME / "ollama-windows-amd64.zip"
    if not archive.is_file():
        print("Baixe o pacote oficial para python-agent/.runtime/ollama-windows-amd64.zip:\n" + URL)
        return 2
    digest = hashlib.sha256()
    with archive.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    if digest.hexdigest() != ARCHIVE_SHA256:
        print("Pacote incompleto ou SHA-256 diferente do oficial. Nenhum executável foi extraído.")
        return 2
    destination = (RUNTIME / "ollama").resolve()
    destination.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(archive) as package:
        for member in package.infolist():
            target = (destination / member.filename).resolve()
            if not target.is_relative_to(destination) or stat.S_ISLNK(member.external_attr >> 16):
                raise ValueError("Entrada insegura no pacote; extração recusada.")
        for member in package.infolist():
            target = destination / member.filename
            if member.is_dir():
                target.mkdir(parents=True, exist_ok=True)
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                with package.open(member) as source, target.open("wb") as output:
                    shutil.copyfileobj(source, output, length=1024 * 1024)
    if not (destination / "ollama.exe").is_file():
        raise ValueError("Pacote sem o executável esperado ollama.exe.")
    report = {"installed_at_utc": datetime.now(timezone.utc).isoformat(), "version": VERSION,
              "source": URL, "archive_sha256": digest.hexdigest(), "sha256_verified": True,
              "runtime_location": "python-agent/.runtime/ollama", "global_install": False}
    (MODULE_ROOT / "reports" / "ollama_installation.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print("Pacote oficial verificado e extraído em python-agent/.runtime/ollama.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
