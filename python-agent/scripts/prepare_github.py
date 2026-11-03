"""Pré-verificação local antes de versionar/enviar; nunca imprime segredos ou PII."""
import csv
import hashlib
import json
from pathlib import Path
import subprocess

ROOT=Path(__file__).resolve().parents[2]


def main():
    result=subprocess.run(['git','ls-files','--cached','--others','--exclude-standard','-z'],cwd=ROOT,capture_output=True,check=True)
    names=sorted(set(n for n in result.stdout.decode('utf-8').split('\0') if n))
    protected=[]
    for path in (ROOT/'.env',ROOT/'python-agent/.env'):
        if path.exists():
            for line in path.read_text(encoding='utf-8-sig').splitlines():
                key,sep,value=line.partition('=')
                if sep and any(word in key.upper() for word in ('KEY','TOKEN','PASSWORD','DATABASE_URL')):
                    value=value.strip().strip('\"\'')
                    if len(value)>12:
                        protected.append(value)
    customers=ROOT/'data/desafio_tecnico_ai_eng - customers.csv'
    if customers.exists():
        with customers.open(encoding='utf-8-sig',newline='') as handle:
            for row in csv.DictReader(handle):
                protected.extend(v for k in ('phone','email') if len(v:=row.get(k,'').strip())>=8)
    forbidden=[]
    hashes={}
    allowed_data={f'data/desafio_tecnico_ai_eng - {name}.csv' for name in ('categories','products','promotions')}
    for name in names:
        path=ROOT/name
        lower=name.lower()
        blocked=(lower.endswith('.pdf') or '/.runtime/' in lower or '/.venv/' in lower
                 or lower.startswith(('python-agent/reports/','python-agent/examples/'))
                 or (path.name.startswith('.env') and path.name!='.env.example')
                 or (lower.startswith('data/') and name not in allowed_data))
        data=path.read_bytes()
        text=data.decode('utf-8',errors='ignore')
        if blocked or any(value.casefold() in text.casefold() for value in protected):
            forbidden.append(name)
        hashes[name]=hashlib.sha256(data).hexdigest()
    report={'passed':not forbidden,'files':hashes,'blocked_files':forbidden,
            'credentials_and_private_contacts_checked':True}
    target=ROOT/'python-agent/.runtime/github_preflight.json'
    target.parent.mkdir(parents=True,exist_ok=True)
    target.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'passed':not forbidden,'file_count':len(names),'blocked_files':forbidden},ensure_ascii=False))
    return 0 if not forbidden else 1


if __name__=='__main__':
    raise SystemExit(main())
