"""Metatron generado por 6abinsky: portal público con ventana móvil de siete días.

Extrae TODOS los archivos del ZIP (index.html, style.css, render.js, data.json,
etc.) a public/, en lugar de copiar site/ — el ZIP siempre está al día porque
lo genera paquete_web() desde web/ local.
"""
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

def main():
    now = datetime.now(timezone.utc)
    repo = os.environ['REPO']
    token = os.environ['GH_TOKEN']
    base = 'https://api.github.com/repos/' + repo

    # 1) Buscar el ZIP más reciente en todos los releases
    releases = json.loads(request(base + '/releases?per_page=100', token))
    candidates = []
    for release in releases:
        if not release.get('tag_name', '').startswith('datos-'):
            continue
        for asset in release.get('assets', []):
            if asset['name'] == 'metatron-web.zip':
                candidates.append(asset)

    if not candidates:
        raise SystemExit('No hay lote recibido')

    asset = max(candidates, key=lambda a: a['created_at'])
    print(f'[MET4TRON] Asset elegido: {asset["name"]} · creado: {asset["created_at"]}')

    # 2) Descargar el ZIP
    req = urllib.request.Request(asset['url'], headers={
        'Authorization': 'Bearer ' + token,
        'Accept': 'application/octet-stream',
    })
    with urllib.request.urlopen(req, timeout=90) as r:
        raw = r.read(50 * 1024 * 1024 + 1)
    if len(raw) > 50 * 1024 * 1024:
        raise ValueError('Lote demasiado grande')

    # 3) Verificar estructura y extraer TODOS los archivos a public/
    out = Path('public')
    out.mkdir(exist_ok=True)
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        names = z.namelist()
        print(f'[MET4TRON] Archivos en el ZIP: {names}')
        if 'data.json' not in names:
            raise ValueError('El ZIP no contiene data.json')
        for name in names:
            p = Path(name)
            if p.is_absolute() or '..' in p.parts:
                raise ValueError('Archivo inseguro: ' + name)
        # Verificar que el ZIP contiene los archivos web clave
        faltantes = [r for r in ['index.html','style.css','render.js'] if r not in names]
        if faltantes:
            print(f'[MET4TRON] ADVERTENCIA: el ZIP no contiene {faltantes}. '
                  f'Se intentará el fallback desde site/ (puede estar desactualizado).')
        z.extractall(out)

    # 4) Fallback solo si el ZIP no trajo el archivo (para ZIP podados antiguos)
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        for required in ['index.html','style.css','render.js','search.js','app.js']:
            if required not in z.namelist() and Path('site', required).exists():
                shutil.copy2(Path('site', required), out / required)
                print(f'[MET4TRON] Fallback desde site/: {required}')

    # 5) Leer y podar data.json
    data = json.loads((out / 'data.json').read_text(encoding='utf-8'))

    # 6) Preservar reportes históricos del data.json público anterior
    try:
        previous = json.loads(request(os.environ['SITE_URL'].rstrip('/') + '/data.json'))
    except urllib.error.HTTPError as e:
        if e.code != 404:
            raise
        previous = {}
    incoming = data
    if previous:
        prev_reportes = list(previous.get('reportes', []))
        if previous.get('reporte'):
            prev_reportes.append(previous['reporte'])
        # Deduplicar por id o por fin
        seen = set()
        merged = []
        for r in prev_reportes + ([incoming['reporte']] if incoming.get('reporte') else []):
            k = r.get('id') or r.get('fin')
            if k in seen: continue
            seen.add(k); merged.append(r)
        data['reportes'] = merged

    # 7) Aplicar monto si viene
    if os.environ.get('MONTO', ''):
        amount = float(os.environ['MONTO'])
        if not 0 <= amount < 1e12:
            raise ValueError('Monto inválido')
        data.setdefault('donaciones', {})['recaudado'] = amount

    # 8) Podar y guardar
    data = prune(data, now)
    (out / 'data.json').write_text(json.dumps(data, ensure_ascii=False), encoding='utf-8')
    (out / '.nojekyll').touch()

    print(f'[MET4TRON] Portal preparado: {len(data["publicaciones"])} publicaciones; {len(data["reportes"])} informes.')

if __name__ == '__main__':
    main()
