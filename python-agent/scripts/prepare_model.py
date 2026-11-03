"""Prepara Qwen3 1.7B no diretório local do Ollama com verificação SHA-256.

Usa o manifesto público do registro oficial, sem executar conteúdo baixado.
Alternativa ao pull via servidor para preparar o modelo durante a instalação.
"""

import hashlib
import json
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / ".runtime"
REGISTRY = "https://registry.ollama.ai/v2/library/qwen3"


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def download(url, target, resume=False):
    command = ["curl.exe", "--fail", "--location", "--silent", "--show-error", "--retry", "3",
               "--connect-timeout", "30", "--max-time", "1800", "--output", str(target)]
    if resume:
        command += ["--continue-at", "-"]
    subprocess.run(command + [url], check=True)


def main():
    RUNTIME.mkdir(exist_ok=True)
    manifest_path = RUNTIME / "qwen3-manifest.json"
    if not manifest_path.is_file():
        download(REGISTRY + "/manifests/1.7b", manifest_path)
    manifest = json.loads(manifest_path.read_bytes())
    if manifest.get("schemaVersion") != 2 or not isinstance(manifest.get("layers"), list):
        raise ValueError("Manifesto de modelo inválido.")
    entries = [manifest["config"], *manifest["layers"]]
    blobs = RUNTIME / "models" / "blobs"
    blobs.mkdir(parents=True, exist_ok=True)
    verified = []
    for entry in entries:
        digest, size = entry["digest"], entry["size"]
        if not re.fullmatch(r"sha256:[0-9a-f]{64}", digest) or type(size) is not int or not 0 < size < 2_000_000_000:
            raise ValueError("Entrada de manifesto inválida.")
        destination = blobs / digest.replace(":", "-")
        if not destination.is_file() or destination.stat().st_size != size or sha256(destination) != digest[7:]:
            print(f"Baixando camada {entry['mediaType']}: {size} bytes.", flush=True)
            download(REGISTRY + "/blobs/" + digest, destination, resume=True)
        if destination.stat().st_size != size or sha256(destination) != digest[7:]:
            raise ValueError("Camada de modelo incompleta ou com SHA-256 incorreto.")
        verified.append({"digest": digest, "size": size, "verified": True})
        print("Camada verificada: " + entry["mediaType"], flush=True)
    target = RUNTIME / "models" / "manifests" / "registry.ollama.ai" / "library" / "qwen3"
    target.mkdir(parents=True, exist_ok=True)
    (target / "1.7b").write_bytes(manifest_path.read_bytes())
    report = {"model": "qwen3:1.7b", "registry": REGISTRY, "verified_layers": verified,
              "model_location": "python-agent/.runtime/models"}
    (ROOT / "reports" / "ollama_model.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print("Modelo local pronto para o Ollama.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
