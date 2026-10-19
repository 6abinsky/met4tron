"""Entregas explícitamente configuradas, sin secretos en los activos públicos."""
import io,json,zipfile,uuid,datetime,subprocess,sys
from pathlib import Path
import requests
from .config import ROOT,DATA,configuracion,ahora,TZ
from .db import conectar_db,consultar
from .exportar import exportar
PUBLIC_FIELDS={'id','fecha','mensaje','titulo','resumen','link','red','perfil','interaccion_total','categoria_principal','categorias_secundarias','palabras_clave','sentimiento','departamento_principal','departamentos_secundarios','municipios','instituciones','autoridades','territorio_carga','tipo_metrica','estado_ia'}
def datos_publicos(rows): return [{k:v for k,v in r.items() if k in PUBLIC_FIELDS} for r in rows]
def paquete_web(report):
    import copy
    report=copy.deepcopy(report)
    for s in report['secciones']: s['bloques']=[b for b in s['bloques'] if not b.get('privado')]
    now=ahora(); rows=consultar(now-datetime.timedelta(days=7),now)
    payload={'contacto':configuracion().get('github',{}).get('contacto',''),'version':str(uuid.uuid4()),'generado':now.isoformat(),'publicar_desde':now.replace(hour=20,minute=0,second=0,microsecond=0).isoformat(),'reporte':report,'publicaciones':datos_publicos(rows),'donaciones':{'recaudado':configuracion().get('github',{}).get('recaudado',0),'meta':4000}}
    out=io.BytesIO()
    with zipfile.ZipFile(out,'w',zipfile.ZIP_DEFLATED) as z:
        for p in (ROOT/'web').iterdir():
            if p.is_file(): z.write(p,p.name)
        z.writestr('data.json',json.dumps(payload,ensure_ascii=False)); z.writestr('.nojekyll','')
    return out.getvalue()

def gh_request(method,path,**kwargs):
    cfg=configuracion()['github']; token=cfg.get('token','')
    if not token: raise ValueError('Falta token GitHub')
    resp=requests.request(method,'https://api.github.com'+path,headers={'Authorization':'Bearer '+token,'Accept':'application/vnd.github+json','X-GitHub-Api-Version':'2022-11-28'},timeout=60,**kwargs)
    resp.raise_for_status(); return resp.json() if resp.content else {}
def verificar_repo():
    cfg=configuracion()['github']; repo=cfg.get('repo','')
    import re
    if not re.fullmatch(r'[\w.-]+/[\w.-]+',repo): raise ValueError('Usa propietario/repositorio')
    result=gh_request('GET','/repos/'+repo)
    # Los lotes se guardan siempre como borradores autenticados de Releases.
    return result

def publicar(report):
    cfg=configuracion()['github']; verificar_repo(); repo=cfg['repo']; base='/repos/'+repo
    # Un release privado es área de recepción: no se escribe data.json en el historial Git.
    releases=gh_request('GET',base+'/releases?per_page=100')
    release=gh_request('POST',base+'/releases',json={'tag_name':'datos-'+report['id'],'name':'MET4TRON '+report['id'],'body':'Paquete temporal de 7 días. Metatron generado por 6abinsky','draft':True,'prerelease':True})
    url=release['upload_url'].split('{')[0]
    response=requests.post(url,params={'name':'metatron-web.zip'},headers={'Authorization':'Bearer '+cfg['token'],'Content-Type':'application/zip'},data=paquete_web(report),timeout=120); response.raise_for_status()
    # Solo tras subir íntegramente el nuevo archivo se eliminan los lotes antiguos.
    for old in releases:
        if old.get('tag_name','').startswith('datos-'):
            gh_request('DELETE',base+'/releases/'+str(old['id']))
            if not old.get('draft'):
                gh_request('DELETE',base+'/git/refs/tags/'+old['tag_name'])
    gh_request('POST',base+'/actions/workflows/publicar.yml/dispatches',json={'ref':cfg.get('rama','main')})
    return 'Lote recibido; el workflow respeta las 20:00 de Bolivia antes de desplegar.'

def entregado(key):
    with conectar_db() as c: return c.execute("SELECT 1 FROM entregas WHERE clave=? AND estado='enviado'",(key,)).fetchone() is not None

def registrar(key,estado,detalle):
    with conectar_db() as c: c.execute('INSERT OR REPLACE INTO entregas VALUES (?,?,?,?)',(key,ahora().isoformat(),estado,detalle))

def enviar_web(canal,destino,path,perfil,selectores):
    """Sesión web local ya autenticada. Los selectores se configuran ante cambios del servicio."""
    from playwright.sync_api import sync_playwright
    from urllib.parse import urlsplit
    allowed={'whatsapp':'web.whatsapp.com','telegram':'web.telegram.org'}
    if urlsplit(destino).hostname!=allowed[canal]: raise ValueError('Destino web no válido')
    required=('adjuntar','archivo','enviar','confirmacion')
    if any(not selectores.get(k) for k in required): raise ValueError('Configura selectores de adjuntar, archivo, enviar y confirmación de entrega')
    with sync_playwright() as p:
        context=p.chromium.launch_persistent_context(str(perfil),headless=False)
        try:
            page=context.new_page(); page.goto(destino,wait_until='domcontentloaded'); page.wait_for_timeout(4000)
            if selectores.get('buscar'):
                search=page.locator(selectores['buscar']).first
                search.fill(selectores['titulo_chat']); page.wait_for_timeout(2000)
                candidates=page.get_by_text(selectores['titulo_chat'],exact=True)
                if candidates.count()!=1: raise ValueError('Destino ambiguo: se requiere exactamente una coincidencia')
                candidates.click()
            # Exige título exacto del chat para no enviar a homónimos o al chat previo.
            page.get_by_text(selectores['titulo_chat'],exact=True).first.wait_for(timeout=30000)
            page.locator(selectores['adjuntar']).click(); page.locator(selectores['archivo']).set_input_files(str(path))
            # Un selector de confirmación debe identificar ESTE archivo, no un mensaje antiguo.
            confirm=selectores['confirmacion'].replace('{archivo}',path.name)
            before=page.locator(confirm).count()
            page.locator(selectores['enviar']).last.click()
            page.wait_for_function('(x)=>document.querySelectorAll(x.selector).length>x.before',arg={'selector':confirm,'before':before},timeout=30000)
        finally: context.close()

def abrir_sesion(canal):
    # Proceso independiente: la interfaz no bloquea durante el escaneo del QR.
    return subprocess.Popen([sys.executable,str(ROOT/'sesion_web.py'),canal],cwd=ROOT)

def distribuir(report):
    cfg=configuracion(); status=[]; DATA.mkdir(exist_ok=True,parents=True)
    if cfg.get('github',{}).get('automatico'):
        key=report['id']+':github'
        if not entregado(key):
            try: msg=publicar(report); registrar(key,'enviado',msg); status.append(msg)
            except Exception as e: registrar(key,'error',type(e).__name__); status.append('GitHub pendiente: '+type(e).__name__)
    for i,d in enumerate(cfg.get('mensajeria',{}).get('destinos',[])):
        if not d.get('activo'): continue
        key=report['id']+':'+d['canal']+':'+str(i)
        if entregado(key): continue
        try:
            data,ext=exportar(report,d.get('formato','PDF')); path=DATA/(report['id']+'.'+ext); path.write_bytes(data)
            enviar_web(d['canal'],d['url'],path,DATA/('sesion_'+d['canal']),d['selectores'])
            registrar(key,'enviado','Entrega confirmada en interfaz'); status.append(d['canal']+': enviado')
        except Exception as e: registrar(key,'error',type(e).__name__); status.append(d['canal']+': pendiente ('+type(e).__name__+')')
    return status

def crear_repositorio(nombre):
    """El usuario pulsa este botón en su instalación; no se ejecuta al iniciar."""
    import re
    if not re.fullmatch(r'[A-Za-z0-9_.-]+',nombre): raise ValueError('Nombre de repositorio inválido')
    result=gh_request('POST','/user/repos',json={'name':nombre,'private':True,'auto_init':True,'description':'MET4TRON — recepción privada y despliegue de datos públicos'})
    cfg=configuracion(); cfg['github']['repo']=result['full_name']; cfg['github']['rama']=result['default_branch']
    from .config import guardar
    guardar('configuracion_v5.json',cfg); return result['full_name']

def instalar_workflow():
    import base64
    verificar_repo(); cfg=configuracion()['github']; base='/repos/'+cfg['repo']
    for source,dest in [(ROOT/'github/.github/workflows/publicar.yml','.github/workflows/publicar.yml'),(ROOT/'github/github_publicar.py','github_publicar.py')]:
        payload={'message':'Instalar publicación MET4TRON','content':base64.b64encode(source.read_bytes()).decode(),'branch':cfg.get('rama','main')}
        try: payload['sha']=gh_request('GET',base+'/contents/'+dest+'?ref='+cfg.get('rama','main'))['sha']
        except requests.HTTPError as e:
            if e.response.status_code!=404: raise
        gh_request('PUT',base+'/contents/'+dest,json=payload)
    try: gh_request('POST',base+'/pages',json={'build_type':'workflow'})
    except requests.HTTPError as e:
        if e.response.status_code==409: gh_request('PUT',base+'/pages',json={'build_type':'workflow'})
        else: raise
    return 'Workflow instalado y Pages configurado. Las políticas de la cuenta pueden requerir habilitar el entorno github-pages.'

def actualizar_donacion():
    cfg=configuracion()['github']; verificar_repo()
    gh_request('POST','/repos/'+cfg['repo']+'/actions/workflows/publicar.yml/dispatches',json={'ref':cfg.get('rama','main'),'inputs':{'monto':str(cfg.get('recaudado',0))}})
    return 'Actualización de donaciones enviada; conserva el informe ya público y no anticipa el lote en espera.'
