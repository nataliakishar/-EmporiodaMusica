"""Publica o snapshot no esquema privado do Supabase, nunca no GitHub/frontend."""
import base64
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from emporio_agent.cloud_runtime import CloudRPC, PrivateAssets
from emporio_agent.config import resolve_data_dir
from emporio_agent.data import FILENAMES, load_snapshot
from emporio_agent.policies import FILENAME


def main():
    source = resolve_data_dir()
    load_snapshot(source)  # reconfirma os seis CSVs antes do envio
    files = {}
    for name in list(FILENAMES.values()) + [FILENAME]:
        content = (source / name).read_bytes()
        files[name] = {'sha256': hashlib.sha256(content).hexdigest(),
                       'base64': base64.b64encode(content).decode('ascii')}
    rpc = CloudRPC()
    if rpc.call('agent_assets_set', {'p_bundle': {'files': files}}) is not True:
        raise RuntimeError('Não foi possível guardar as fontes privadas.')
    restored = PrivateAssets(rpc).data_dir()
    matches = all(hashlib.sha256((restored / name).read_bytes()).hexdigest() == entry['sha256']
                  for name, entry in files.items())
    print(json.dumps({'passed': matches, 'private_files_verified': len(files), 'public_files_created': 0}))
    return 0 if matches else 1


if __name__ == '__main__':
    raise SystemExit(main())
