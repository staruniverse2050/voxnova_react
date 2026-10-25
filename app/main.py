from __future__ import annotations
import os, subprocess, tempfile
from pathlib import Path
from typing import Annotated
import httpx
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

API_KEY = os.getenv("ELEVENLABS_API_KEY", "").strip()
REPLICAVOX_API_KEY = os.getenv("REPLICAVOX_API_KEY", "").strip()
API = "https://api.elevenlabs.io/v1"
REPLICAVOX_API = "https://api.replicavox.com/v1"
MAX_MB = int(os.getenv("MAX_UPLOAD_MB", "40"))
app = FastAPI(title="VoxNova AI", version="1.1.0")

class SpeechRequest(BaseModel):
    voice_id: str = Field(min_length=3, max_length=128)
    text: str = Field(min_length=1, max_length=5000)
    model_id: str = "eleven_multilingual_v2"

def replicavox_key():
    if not REPLICAVOX_API_KEY:
        raise HTTPException(503, "Configura REPLICAVOX_API_KEY en Render con tu llave API de Replicavox.")
    return REPLICAVOX_API_KEY

def key():
    if not API_KEY:
        raise HTTPException(503, "El servidor necesita la variable ELEVENLABS_API_KEY en Render.")
    return API_KEY

def validate(file: UploadFile):
    if not file.filename: raise HTTPException(400, "Selecciona un archivo de audio.")
    ct=(file.content_type or "").lower()
    if not (ct.startswith("audio/") or ct in ("application/octet-stream","video/mp4")):
        raise HTTPException(415, "Formato no admitido. Sube MP3, WAV, M4A u OGG.")

async def read_file(file: UploadFile):
    data=await file.read(MAX_MB*1024*1024+1)
    if len(data)>MAX_MB*1024*1024: raise HTTPException(413, "El archivo supera el límite de "+str(MAX_MB)+" MB.")
    if not data: raise HTTPException(400, "El archivo está vacío.")
    return data

def upstream(r):
    try:
        j=r.json()
        detail=j.get("detail",j.get("message",j.get("error",j)))
        if isinstance(detail,dict):
            detail=detail.get("message",detail.get("detail",detail))
    except Exception: detail=r.text[:800]
    status=r.status_code if 400<=r.status_code<500 else 502
    return HTTPException(status, detail={"provider":"voice API","message":detail})

async def post_audio(url, headers, **kwargs):
    async with httpx.AsyncClient(timeout=180) as client:
        r=await client.post(url,headers=headers,**kwargs)
    if r.is_error: raise upstream(r)
    return Response(r.content,media_type="audio/mpeg",headers={"Content-Disposition":'attachment; filename="voxnova-audio.mp3"',"Cache-Control":"no-store"})

@app.get("/health")
def health(): return {"status":"ok","provider_configured":bool(REPLICAVOX_API_KEY),"elevenlabs_configured":bool(API_KEY),"replicavox_configured":bool(REPLICAVOX_API_KEY)}

@app.get("/api/voices")
async def voices():
    k=replicavox_key()
    headers={"Authorization":"Bearer "+k,"Accept":"application/json"}
    async with httpx.AsyncClient(timeout=60) as client:
        library=await client.get(REPLICAVOX_API+"/audio/voices",headers=headers)
        if library.is_error: raise upstream(library)
        clones=await client.get(REPLICAVOX_API+"/audio/clones",headers=headers)
        if clones.is_error: raise upstream(clones)
    library_data=library.json()
    clone_data=clones.json()
    library_list=library_data if isinstance(library_data,list) else library_data.get("data",[])
    clone_list=clone_data if isinstance(clone_data,list) else clone_data.get("data",[])
    result=[]
    for v in library_list:
        voice_id=v.get("id") or v.get("voice_id")
        if voice_id:
            result.append({"voice_id":voice_id,"name":v.get("name") or voice_id,"category":"Voz de biblioteca","provider":"Replicavox"})
    for v in clone_list:
        voice_id=v.get("id") or v.get("voice_id")
        if voice_id and v.get("status","ready")=="ready":
            result.append({"voice_id":voice_id,"name":v.get("name") or voice_id,"category":"Voz clonada","provider":"Replicavox","visibility":v.get("visibility")})
    return {"voices":result}

@app.post("/api/speech")
async def speech(body:SpeechRequest):
    k=replicavox_key()
    async with httpx.AsyncClient(timeout=240) as client:
        r=await client.post(
            REPLICAVOX_API+"/audio/speech",
            headers={"Authorization":"Bearer "+k,"Accept":"audio/mpeg","Content-Type":"application/json"},
            json={"model":"replicavox-expressive-v2","voice":body.voice_id,"input":body.text,"language":"es","response_format":"mp3"}
        )
    if r.is_error: raise upstream(r)
    return Response(r.content,media_type=r.headers.get("content-type","audio/mpeg"),headers={"Content-Disposition":'attachment; filename="voxnova-audio.mp3"',"Cache-Control":"no-store"})

@app.post("/api/voices/clone")
async def clone(name:Annotated[str,Form(min_length=1,max_length=80)],consent_confirmed:Annotated[bool,Form()],file:Annotated[UploadFile,File()]):
    k=replicavox_key()
    if not consent_confirmed: raise HTTPException(400,"Confirma que tienes permiso para clonar esta voz.")
    validate(file)
    data=await read_file(file)
    headers={"Authorization":"Bearer "+k,"Accept":"application/json"}
    async with httpx.AsyncClient(timeout=240) as client:
        r=await client.post(
            REPLICAVOX_API+"/audio/clones",
            headers=headers,
            data={"name":name.strip(),"language":"es"},
            files={"file":(file.filename or "voice-sample",data,file.content_type or "application/octet-stream")}
        )
    if r.is_error: raise upstream(r)
    payload=r.json()
    voice_id=payload.get("id") or payload.get("voice_id")
    if not voice_id: raise HTTPException(502,"Replicavox no devolvió el identificador de la voz clonada.")
    return {"voice_id":voice_id,"name":payload.get("name") or name.strip(),"provider":"Replicavox","language":payload.get("language","es"),"status":payload.get("status","ready")}

@app.post("/api/convert-voice")
async def convert(voice_id:Annotated[str,Form(min_length=3,max_length=128)],consent_confirmed:Annotated[bool,Form()],file:Annotated[UploadFile,File()]):
    k=key()
    if not consent_confirmed: raise HTTPException(400,"Confirma que tienes permiso para utilizar la voz seleccionada.")
    validate(file); data=await read_file(file)
    return await post_audio(API+"/speech-to-speech/"+voice_id,{"xi-api-key":k,"Accept":"audio/mpeg"},params={"output_format":"mp3_44100_128"},data={"model_id":"eleven_multilingual_sts_v2","remove_background_noise":"false"},files={"audio":(file.filename or "audio.wav",data,file.content_type or "application/octet-stream")})

def ffmpeg(args):
    try: r=subprocess.run(["ffmpeg","-hide_banner","-loglevel","error","-y",*args],capture_output=True,text=True,timeout=180)
    except FileNotFoundError: raise HTTPException(503,"FFmpeg no está instalado en el servidor.")
    except subprocess.TimeoutExpired: raise HTTPException(504,"El audio tardó demasiado en procesarse.")
    if r.returncode: raise HTTPException(422,"No se pudo procesar el audio. Revisa el archivo y los tiempos.")

@app.post("/api/replace-segment")
async def replace(voice_id:Annotated[str,Form(min_length=3,max_length=128)],start_seconds:Annotated[float,Form(ge=0)],end_seconds:Annotated[float,Form(gt=0)],replacement_text:Annotated[str,Form(min_length=1,max_length=2000)],consent_confirmed:Annotated[bool,Form()],file:Annotated[UploadFile,File()]):
    k=key()
    if not consent_confirmed: raise HTTPException(400,"Confirma que tienes autorización para editar este audio.")
    if end_seconds<=start_seconds or end_seconds-start_seconds>120: raise HTTPException(400,"El tiempo final debe superar al inicial y el fragmento no puede superar 120 segundos.")
    validate(file); raw=await read_file(file)
    with tempfile.TemporaryDirectory(prefix="voxnova-") as td:
        d=Path(td); src=d/"src"; src.write_bytes(raw); original=d/"original.wav"
        ffmpeg(["-i",str(src),"-vn","-ac","2","-ar","44100","-acodec","pcm_s16le",str(original)])
        p=subprocess.run(["ffprobe","-v","error","-show_entries","format=duration","-of","default=noprint_wrappers=1:nokey=1",str(original)],capture_output=True,text=True,timeout=30)
        try: duration=float(p.stdout.strip())
        except ValueError: raise HTTPException(422,"No se pudo leer la duración del audio.")
        if start_seconds>=duration or end_seconds>duration: raise HTTPException(400,"Los tiempos deben estar dentro de la duración del audio ("+str(round(duration,2))+" s).")
        async with httpx.AsyncClient(timeout=180) as c:
            r=await c.post(API+"/text-to-speech/"+voice_id,headers={"xi-api-key":k,"Accept":"audio/mpeg"},params={"output_format":"mp3_44100_128"},json={"text":replacement_text,"model_id":"eleven_multilingual_v2","voice_settings":{"stability":0.5,"similarity_boost":0.75}})
        if r.is_error: raise upstream(r)
        generated=d/"replacement.mp3"; generated.write_bytes(r.content); rep=d/"rep.wav"
        ffmpeg(["-i",str(generated),"-ac","2","-ar","44100","-acodec","pcm_s16le",str(rep)])
        probe=subprocess.run(["ffprobe","-v","error","-show_entries","format=duration","-of","default=noprint_wrappers=1:nokey=1",str(rep)],capture_output=True,text=True,timeout=30)
        try: repdur=float(probe.stdout.strip())
        except ValueError: raise HTTPException(502,"No se pudo leer la duración de la voz generada.")
        target=end_seconds-start_seconds; factor=repdur/target; filters=[]
        while factor>2: filters.append("atempo=2.0"); factor/=2
        while factor<0.5: filters.append("atempo=0.5"); factor/=0.5
        filters.append("atempo="+format(factor,".8f"))
        fit=d/"fit.wav"; ffmpeg(["-i",str(rep),"-filter:a",",".join(filters),"-t",format(target,".6f"),"-acodec","pcm_s16le",str(fit)])
        parts=[]
        if start_seconds>0:
            pre=d/"pre.wav"; ffmpeg(["-i",str(original),"-t",format(start_seconds,".6f"),"-acodec","pcm_s16le",str(pre)]); parts.append(pre)
        parts.append(fit)
        if end_seconds<duration:
            suf=d/"suf.wav"; ffmpeg(["-ss",format(end_seconds,".6f"),"-i",str(original),"-acodec","pcm_s16le",str(suf)]); parts.append(suf)
        listing=d/"concat.txt"; listing.write_text("\n".join("file '"+p.as_posix()+"'" for p in parts),encoding="utf-8")
        merged=d/"merged.wav"; out=d/"edited.mp3"
        ffmpeg(["-f","concat","-safe","0","-i",str(listing),"-acodec","pcm_s16le",str(merged)])
        ffmpeg(["-i",str(merged),"-codec:a","libmp3lame","-b:a","192k",str(out)])
        return FileResponse(out,media_type="audio/mpeg",filename="audio-editado.mp3",headers={"Cache-Control":"no-store"})

STATIC=Path(__file__).parent/"static"
if (STATIC/"assets").exists(): app.mount("/assets",StaticFiles(directory=STATIC/"assets"),name="assets")
@app.get("/",include_in_schema=False)
def root():
    index=STATIC/"index.html"
    if not index.exists(): return {"service":"VoxNova AI","status":"backend listo","docs":"/docs"}
    return FileResponse(index,media_type="text/html")
@app.get("/api")
def api_root(): return {"service":"VoxNova AI","docs":"/docs","health":"/health"}
