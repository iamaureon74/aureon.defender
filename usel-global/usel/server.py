"""Local-use interactive UI. Do not expose publicly without production security review."""
from __future__ import annotations
from fastapi import FastAPI,HTTPException,Request
from fastapi.responses import FileResponse,JSONResponse,StreamingResponse
from pydantic import BaseModel
from pathlib import Path
from tempfile import TemporaryDirectory
from io import BytesIO
import zipfile, json
from .registry import load_engines,load_countries
from .models import read_spec,SpecError
from .compiler import compile_site
from .auditor import audit_site

ROOT=Path(__file__).resolve().parents[1]
app=FastAPI(title='USEL local studio',docs_url=None,redoc_url=None)

class Payload(BaseModel):
    source:str

@app.get('/')
def home():return FileResponse(ROOT/'ui/index.html',media_type='text/html')
@app.get('/style.css')
def style():return FileResponse(ROOT/'ui/style.css',media_type='text/css')
@app.get('/app.js')
def script():return FileResponse(ROOT/'ui/app.js',media_type='text/javascript')
@app.get('/api/example')
def example():return FileResponse(ROOT/'examples/bosley.usel.yaml',media_type='text/plain')
@app.get('/api/summary')
def summary():
    engines=load_engines();countries=load_countries()
    return {'countries_and_jurisdictions':len(countries),'engine_and_crawler_profiles':len(engines),
            'documented_profiles':sum(e['verification']=='documented' for e in engines),
            'unresearched_country_markets':sum(c['search_engine_discovery_status']=='not_audited' for c in countries),
            'verification':'documentation reviewed only; not live indexing/traffic validation'}
@app.get('/api/engines')
def engines():return load_engines()
@app.get('/api/countries')
def countries():return load_countries()
@app.post('/api/compile')
def compile_endpoint(data:Payload):
    try:
        spec=read_spec(data.source)
        with TemporaryDirectory() as folder:
            summary=compile_site(spec,folder)
            audit=audit_site(folder)
            if not audit['ok']:
                raise HTTPException(status_code=422,detail=audit)
            blob=BytesIO()
            with zipfile.ZipFile(blob,'w',zipfile.ZIP_DEFLATED) as zf:
                for p in Path(folder).rglob('*'):
                    if p.is_file():zf.write(p,p.relative_to(folder).as_posix())
            blob.seek(0)
            return StreamingResponse(blob,media_type='application/zip',headers={'Content-Disposition':'attachment; filename="usel-output.zip"',
                'X-USEL-Indexed-Pages':str(summary['indexed_pages']),'X-USEL-Verified':'static-output-audit'})
    except SpecError as ex:raise HTTPException(400,str(ex))
