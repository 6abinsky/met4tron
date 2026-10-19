"""Metatron generado por 6abinsky: portal público con ventana móvil de siete días."""
import copy, io, json, os, shutil, urllib.request, urllib.error, zipfile, uuid
from pathlib import Path
from datetime import datetime, timedelta, timezone

FIELDS = set('id fecha mensaje titulo resumen link red perfil interaccion_total categoria_principal categorias_secundarias palabras_clave sentimiento departamento_principal departamentos_secundarios municipios instituciones autoridades territorio_carga tipo_metrica estado_ia'.split())
def date(value):
    d = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if d.tzinfo is None: raise ValueError('Fecha sin zona horaria')
    return d

def prune(data, now):
    data = copy.deepcopy(data)
    cut = now - timedelta(days=7)
    unique = {}
    for row in data.get('publicaciones', []):
        if cut <= date(row['fecha']) <= now:
            key = row.get('link') or row.get('id')
            if not key: continue
            clean = {k:v for k,v in row.items() if k in FIELDS}
            if key not in unique or float(clean.get('interaccion_total',0)) >= float(unique[key].get('interaccion_total',0)):
                unique[key] = clean
    data['publicaciones'] = list(unique.values())
    reports = {}
    for report in data.get('reportes', []) + ([data['reporte']] if data.get('reporte') else []):
        # Un informe no debe conservar publicaciones de fuera de la ventana.
        if cut <= date(report['inicio']) <= date(report['fin']) <= now:
            for section in report.get('secciones', []):
                section['bloques'] = [b for b in section.get('bloques',[]) if not b.get('privado') and 'foda' not in b.get('titulo','').lower() and 'cuentas' not in b.get('titulo','').lower()]
            reports[report.get('id') or report['fin']] = report
    data['reportes'] = sorted(reports.values(),key=lambda r:date(r['fin']),reverse=True)
    data['reporte'] = next((r for r in data['reportes'] if date(r['fin']) >= now-timedelta(hours=24)),None)
    data['depurado'] = now.isoformat()
    data['version'] = str(uuid.uuid4())
    return data

def request(url, token=None):
    headers = {'Accept':'application/vnd.github+json','User-Agent':'MET4TRON'}
    if token: headers['Authorization'] = 'Bearer '+token
    with urllib.request.urlopen(urllib.request.Request(url,headers=headers),timeout=90) as r: return r.read()

def compact_asset(asset, incoming, token, now, base):
    """Recorta también el lote de recepción, sin conservar datos viejos en Git."""
    clean=prune(incoming,now)
    if clean['publicaciones']==incoming.get('publicaciones',[]) and clean['reportes']==incoming.get('reportes',[]): return
    archive=io.BytesIO()
    with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED) as z:
        z.writestr('data.json',json.dumps(clean,ensure_ascii=False))
    def mutate(method,url,body=None,ctype='application/json'):
        req=urllib.request.Request(url,data=body,method=method,headers={'Authorization':'Bearer '+token,'Accept':'application/vnd.github+json','Content-Type':ctype})
        with urllib.request.urlopen(req,timeout=90) as r:
            raw=r.read(); return json.loads(raw) if raw else None
    url=asset['_upload_url'].split('{')[0]+'?name=pruned-'+str(uuid.uuid4())+'.zip'
    uploaded=mutate('POST',url,archive.getvalue(),'application/zip')
    mutate('DELETE',asset['url'])
    mutate('PATCH',uploaded['url'],json.dumps({'name':'metatron-web.zip'}).encode())

def main():
    now=datetime.now(timezone.utc)
    repo=os.environ['REPO']; token=os.environ['GH_TOKEN']; base='https://api.github.com/repos/'+repo
    data={'generado':None,'publicar_desde':now.isoformat(),'publicaciones':[],'reportes':[],'reporte':None,'donaciones':{'recaudado':0,'meta':4000},'contacto':''}
    # Recuperar únicamente la versión pública; nunca escribir los datos en commits.
    site=os.environ['SITE_URL'].rstrip('/')
    try:
        data=json.loads(request(site+'/data.json'))
    except urllib.error.HTTPError as e:
        if e.code != 404: raise
    previous=copy.deepcopy(data)
    releases=json.loads(request(base+'/releases?per_page=100',token))
    candidates=[]
    for release in releases:
        if not release.get('tag_name','').startswith('datos-'): continue
        for asset in release.get('assets',[]):
            if asset['name']=='metatron-web.zip':
                asset['_upload_url']=release['upload_url']
                candidates.append(asset)
    for asset in sorted(candidates,key=lambda a:a['created_at'],reverse=True):
        req=urllib.request.Request(asset['url'],headers={'Authorization':'Bearer '+token,'Accept':'application/octet-stream'})
        with urllib.request.urlopen(req,timeout=90) as r: raw=r.read(50*1024*1024+1)
        if len(raw)>50*1024*1024: raise ValueError('Lote demasiado grande')
        with zipfile.ZipFile(io.BytesIO(raw)) as z:
            if z.getinfo('data.json').file_size>100*1024*1024: raise ValueError('JSON demasiado grande')
            incoming=json.loads(z.read('data.json'))
        if date(incoming['publicar_desde']) > now: continue
        compact_asset(asset,incoming,token,now,base)
        if incoming.get('generado') and (not data.get('generado') or date(incoming['generado']) > date(data['generado'])):
            data=incoming
            data['reportes']=previous.get('reportes',[])+([previous['reporte']] if previous.get('reporte') else [])
        break
    if os.environ.get('MONTO',''):
        # Las donaciones no adelantan la publicación de lotes pendientes.
        amount=float(os.environ['MONTO'])
        if not 0<=amount<1e12: raise ValueError('Monto inválido')
        data.setdefault('donaciones',{})['recaudado']=amount
    data=prune(data,now)
    shutil.copytree('site','public',dirs_exist_ok=True)
    Path('public/data.json').write_text(json.dumps(data,ensure_ascii=False),encoding='utf-8')
    Path('public/.nojekyll').touch()
    print('Portal preparado:',len(data['publicaciones']),'publicaciones;',len(data['reportes']),'informes.')

if __name__=='__main__': main()
