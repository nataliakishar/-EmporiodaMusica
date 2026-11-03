"""Download retomável do ZIP oficial, em até quatro partes; SHA final obrigatório."""

from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib
from pathlib import Path
import re
import shutil
import subprocess

from prepare_ollama import RUNTIME, URL, ARCHIVE_SHA256


def curl(arguments):
    subprocess.run(["curl.exe", "--fail", "--location", "--silent", "--show-error", "--retry", "2",
                    "--connect-timeout", "30", "--max-time", "120", "--speed-limit", "1024", "--speed-time", "30", *arguments, URL], check=True)


def digest(path):
    checksum = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            checksum.update(block)
    return checksum.hexdigest()


def main():
    RUNTIME.mkdir(exist_ok=True)
    archive = RUNTIME / "ollama-windows-amd64.zip"
    headers = RUNTIME / "download-headers.txt"
    curl(["--range", "0-0", "--max-filesize", "1024", "--dump-header", str(headers),
          "--output", str(RUNTIME / "download-byte.bin")])
    ranges = re.findall(r"content-range:\s*bytes\s+0-0/(\d+)", headers.read_text(encoding="latin1"), re.IGNORECASE)
    if not ranges:
        raise ValueError("Servidor não confirmou suporte à retomada; download interrompido.")
    total = int(ranges[-1])
    existing = archive.stat().st_size if archive.is_file() else 0
    if existing > total:
        raise ValueError("Arquivo local maior que o pacote oficial; download recusado.")
    remaining = total - existing
    chunk = (remaining + 3) // 4 if remaining else 1
    jobs = []
    for start in range(existing, total, chunk):
        end = min(start + chunk, total) - 1
        target = RUNTIME / f"ollama-part-{start}-{end}.bin"
        jobs.append((start, end, target))

    blocks = []
    groups = []
    for start, end, target in jobs:
        current = target.stat().st_size if target.is_file() else 0
        if current > end - start + 1:
            raise ValueError("Parte local maior que o esperado; retomada recusada.")
        group = []
        for offset in range(start + current, end + 1, 4 * 1024 * 1024):
            stop = min(offset + 4 * 1024 * 1024 - 1, end)
            block = (offset, stop, RUNTIME / f"ollama-block-{offset}-{stop}.bin")
            blocks.append(block)
            group.append(block)
        groups.append((target, end - start + 1, group))

    def download(block):
        start, end, target = block
        expected = end - start + 1
        if not target.is_file() or target.stat().st_size != expected:
            curl(["--range", f"{start}-{end}", "--max-filesize", str(expected + 1), "--output", str(target)])
        if target.stat().st_size != expected:
            raise ValueError("Bloco incompleto; não será incorporado ao pacote.")
    print(f"Pacote: {total} bytes; já recebidos: {existing}; partes restantes: {len(jobs)}.", flush=True)
    with ThreadPoolExecutor(max_workers=4) as pool:
        for completed, future in enumerate(as_completed([pool.submit(download, block) for block in blocks]), start=1):
            future.result()
            if completed % 16 == 0 or completed == len(blocks):
                print(f"Blocos recebidos: {completed}/{len(blocks)}.", flush=True)
    for target, expected, group in groups:
        if group:
            with target.open("ab") as output:
                for _, _, block_path in group:
                    with block_path.open("rb") as source:
                        shutil.copyfileobj(source, output, length=1024 * 1024)
        if target.stat().st_size != expected:
            raise ValueError("Parte incompleta; nada será executado.")
    if jobs:
        with archive.open("ab") as output:
            for _, _, target in jobs:
                with target.open("rb") as source:
                    shutil.copyfileobj(source, output, length=1024 * 1024)
    if archive.stat().st_size != total or digest(archive) != ARCHIVE_SHA256:
        raise ValueError("SHA-256 final não corresponde ao pacote oficial; execução recusada.")
    print("Download completo e SHA-256 oficial verificado.", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
