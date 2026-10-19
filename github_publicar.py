"""Metatron generado por 6abinsky. No almacena datos en commits."""
import os,json,urllib.request,zipfile,io
from pathlib import Path
from datetime import datetime,timedelta,timezone

def get(url,accept='application/vnd.github+json'):
    req=urllib.request.Request(url,headers={'Authorization':'Bearer '+os.environ['GH_TOKEN'],'Accept':accept,'X-GitHub-Api-Version':'2022-11-28'})
    with urllib.request.urlopen(req,timeout=90) as r: return r.read()
base='https://api.github.com/repos/'+os.environ['REPO']; releases=json.loads(get(base+'/releases?per_page=100'))
assets=[a for r in releases if r['tag_name'].startswith('datos-') for a in r['assets'] if a['name']=='metatron-web.zip']
if not assets: raise SystemExit('No hay lote recibido')
asset=max(assets,key=lambda a:a['created_at']); raw=get(asset['url'],'application/octet-stream'); out=Path('public'); out.mkdir(exist_ok=True)
with zipfile.ZipFile(io.BytesIO(raw)) as z:
    for name in z.namelist():
        p=Path(name)
        if p.is_absolute() or '..' in p.parts: raise ValueError('Archivo inseguro')
    z.extractall(out)
p=out/'data.json'; data=json.loads(p.read_text()); now=datetime.now(timezone.utc)
if os.environ.get('MONTO',''):
    # Solo reutiliza información ya pública; nunca libera el lote en espera.
    pageinfo=json.loads(get(base+'/pages'))
    with urllib.request.urlopen(pageinfo['html_url'].rstrip('/')+'/data.json',timeout=60) as response:
        previous=json.load(response)
    amount=float(os.environ['MONTO'])
    if not 0<=amount<1e12: raise ValueError('Monto inválido')
    data=previous; data['donaciones']['recaudado']=amount
    data['publicar_desde']=now.isoformat()

if now<datetime.fromisoformat(data['publicar_desde']):
    with open(os.environ['GITHUB_OUTPUT'],'a') as f: f.write('publicar=false\n')
    raise SystemExit('Lote recibido: espera hasta las 20:00 de Bolivia')
data['publicaciones']=[r for r in data['publicaciones'] if now-timedelta(days=7)<=datetime.fromisoformat(r['fecha'])<=now]
if data.get('reporte') and now-datetime.fromisoformat(data['reporte']['fin'])>timedelta(hours=24): data['reporte']=None
p.write_text(json.dumps(data,ensure_ascii=False),encoding='utf-8')
# Reducir también el archivo privado de recepción; las copias/cachés del proveedor
# están sujetas a su propia retención y no pueden borrarse desde este programa.
if not os.environ.get('MONTO',''):
    archive=io.BytesIO()
    with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED) as z:
        for file in out.rglob('*'):
            if file.is_file(): z.write(file,str(file.relative_to(out)))
    owner_release=next(r for r in releases if any(a['id']==asset['id'] for a in r['assets']))
    def mutation(method,url,body=None,content_type='application/json'):
        req=urllib.request.Request(url,data=body,method=method,headers={'Authorization':'Bearer '+os.environ['GH_TOKEN'],'Content-Type':content_type,'Accept':'application/vnd.github+json'})
        with urllib.request.urlopen(req,timeout=90) as response:
            raw=response.read(); return json.loads(raw) if raw else None
    uploaded=mutation('POST',owner_release['upload_url'].split('{')[0]+'?name=metatron-pruned.zip',archive.getvalue(),'application/zip')
    mutation('DELETE',asset['url'])
    mutation('PATCH',uploaded['url'],json.dumps({'name':'metatron-web.zip'}).encode())

with open(os.environ['GITHUB_OUTPUT'],'a') as f: f.write('publicar=true\n')
