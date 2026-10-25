import React, { useEffect, useState } from 'react';
import { createRoot } from 'react-dom/client';
import { AudioLines, Mic, Scissors, WandSparkles, Upload, Download, RefreshCw, ShieldCheck, LoaderCircle } from 'lucide-react';
import './style.css';

function readableError(value) {
  if (typeof value === 'string') return value;
  if (value == null) return 'Ocurrió un error inesperado.';
  if (Array.isArray(value)) return value.map(readableError).filter(Boolean).join(' · ');
  if (typeof value === 'object') {
    if (value.message) return readableError(value.message);
    if (value.detail) return readableError(value.detail);
    if (value.error) return readableError(value.error);
    return Object.entries(value).map(([key, item]) => key + ': ' + readableError(item)).join(' · ');
  }
  return String(value);
}

function App() {
  const [mode,setMode] = useState('replace');
  const [customVoices,setCustomVoices] = useState(()=>{ try { return JSON.parse(localStorage.getItem('voxnova_custom_voices') || '[]'); } catch { return []; } });
  const [voices,setVoices] = useState(()=>{ try { return JSON.parse(localStorage.getItem('voxnova_custom_voices') || '[]'); } catch { return []; } });
  const [voice,setVoice] = useState('');
  const [file,setFile] = useState(null);
  const [name,setName] = useState('Mi voz');
  const [text,setText] = useState('');
  const [start,setStart] = useState('0');
  const [end,setEnd] = useState('3');
  const [consent,setConsent] = useState(false);
  const [busy,setBusy] = useState(false);
  const [error,setError] = useState('');
  const [message,setMessage] = useState('');
  const [audioUrl,setAudioUrl] = useState('');
  const [apiReady,setApiReady] = useState(false);

  async function loadVoices(preferredVoiceId = '') {
    try {
      const h = await fetch('/health');
      const health = await h.json();
      setApiReady(!!health.provider_configured);
      if (!health.provider_configured) return [];
      const r = await fetch('/api/voices');
      const data = await r.json();
      if (!r.ok) throw new Error(readableError(data.detail || data.message || 'No se pudieron cargar las voces'));
      const list = data.voices || [];
      const combined = [...customVoices, ...list.filter(v => !customVoices.some(cv => cv.voice_id === v.voice_id))];
      setVoices(combined);
      if (preferredVoiceId && list.some(v => v.voice_id === preferredVoiceId)) {
        setVoice(preferredVoiceId);
      } else if (!voice && list.length) {
        setVoice(list[0].voice_id);
      }
      return list;
    } catch(e) {
      setError(readableError(e?.message || e));
      return [];
    }
  }
  useEffect(()=>{ loadVoices(); },[]);
  useEffect(()=>()=>{ if(audioUrl) URL.revokeObjectURL(audioUrl); },[audioUrl]);
  function selectFile(e){ setFile(e.target.files?.[0] || null); setError(''); setMessage(''); }
  async function run(e) {
    e.preventDefault(); setBusy(true); setError(''); setMessage('');
    try {
      let response;
      if(mode === 'speech') {
        response = await fetch('/api/speech',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({voice_id:voice,text})});
      } else {
        if(!file) throw new Error('Primero selecciona un archivo de audio.');
        if(!consent) throw new Error('Confirma que tienes permiso para utilizar esta voz y grabación.');
        const form = new FormData(); form.append('file',file); form.append('voice_id',voice); form.append('consent_confirmed','true');
        if(mode === 'clone') { form.append('name',name); response = await fetch('/api/voices/clone',{method:'POST',body:form}); }
        if(mode === 'convert') response = await fetch('/api/convert-voice',{method:'POST',body:form});
        if(mode === 'replace') {
          form.append('start_seconds',start); form.append('end_seconds',end); form.append('replacement_text',text);
          response = await fetch('/api/replace-segment',{method:'POST',body:form});
        }
      }
      if(!response) throw new Error('Selecciona una operación válida.');
      if(!response.ok) {
        let detail = 'No se pudo completar esta acción. Vuelve a intentarlo.';
        try {
          const d = await response.json();
          detail = readableError(d.detail || d.message || d.error || d);
        } catch {}
        throw new Error(detail);
      }
      if(mode === 'clone') {
        const data = await response.json();
        const clonedName = data.name || name;
        const clonedVoiceId = data.voice_id || data.voice?.voice_id || '';
        if (!clonedVoiceId) throw new Error('La voz se creó, pero el servidor no devolvió su identificador.');
        const savedVoice = {voice_id:clonedVoiceId, name:clonedName, category:'Voz clonada', provider:data.provider || 'JSF Labs'};
        const updated = [savedVoice, ...customVoices.filter(v => v.voice_id !== clonedVoiceId)];
        setCustomVoices(updated);
        setVoices(prev => [savedVoice, ...prev.filter(v => v.voice_id !== clonedVoiceId)]);
        localStorage.setItem('voxnova_custom_voices', JSON.stringify(updated));
        setVoice(clonedVoiceId);
        setMode('speech');
        setMessage('¡Voz "' + clonedName + '" guardada en este navegador! Ya puedes escribir tu texto en Texto a voz y generar el audio con esa voz.');
      } else {
        const blob=await response.blob(); setAudioUrl(URL.createObjectURL(blob)); setMessage('Audio procesado correctamente. Escúchalo y descarga el resultado.');
      }
    } catch(e) { setError(readableError(e?.message || e)); }
    finally { setBusy(false); }
  }
  const modes = [
    {id:'replace',label:'Editar un audio',desc:'Reemplaza una frase',icon:Scissors},
    {id:'speech',label:'Texto a voz',desc:'Escribe y genera audio',icon:AudioLines},
    {id:'convert',label:'Cambiar mi voz',desc:'Transforma una grabación',icon:RefreshCw},
    {id:'clone',label:'Clonar una voz',desc:'Guarda una voz propia',icon:Mic}
  ];
  return <div className="shell">
    <header><div className="brand"><div className="logo"><AudioLines size={25}/></div><div><b>VoxNova <span>AI</span></b><small>LABORATORIO DE VOZ</small></div></div><div className={'status '+(apiReady?'online':'offline')}><i/> {apiReady?'IA conectada':'Configura la API'}</div></header>
    <main>
      <section className="hero"><div className="eyebrow"><WandSparkles size={15}/> AUDIO INTELIGENTE</div><h1>Tu voz. Tus ideas.<br/><em>Sin límites.</em></h1><p>Edita fragmentos, crea voces desde texto o transforma grabaciones en un solo lugar.</p></section>
      <section className="workspace">
        <nav className="tabs">{modes.map(m=>{const Icon=m.icon;return <button key={m.id} className={'tab '+(mode===m.id?'active':'')} onClick={()=>{setMode(m.id);setError('');setMessage('');setAudioUrl('')}}><Icon size={18}/><span>{m.label}<small>{m.desc}</small></span></button>})}</nav>
        <form onSubmit={run} className="panel">
          <div className="panelhead"><div><span className="step">01</span><h2>{modes.find(m=>m.id===mode)?.label}</h2></div><span className="secure"><ShieldCheck size={15}/> Procesamiento seguro</span></div>
          {mode !== 'speech' && <label className="field"><span>Archivo de audio</span><label className="drop"><Upload size={22}/><b>{file?file.name:'Selecciona o arrastra un audio'}</b><small>MP3, WAV, M4A, OGG · Máximo 40 MB</small><input type="file" accept="audio/*,.mp3,.wav,.m4a,.ogg,.opus" onChange={selectFile}/></label></label>}
          {mode === 'clone' && <label className="field"><span>Nombre para esta voz</span><input value={name} onChange={e=>setName(e.target.value)} required placeholder="Ej. Mi voz"/></label>}
          {mode !== 'clone' && <label className="field"><span>{mode==='speech'?'Texto que dirá la voz':mode==='replace'?'Nueva frase para el fragmento':'Voz de destino'}</span>{mode==='speech'||mode==='replace'?<textarea value={text} onChange={e=>setText(e.target.value)} required rows={4} placeholder={mode==='speech'?'Escribe aquí lo que quieres que diga la voz…':'Escribe la frase que reemplazará el fragmento…'}/>:<select value={voice} onChange={e=>setVoice(e.target.value)} required><option value="">Selecciona una voz</option>{voices.map(v=><option key={v.voice_id} value={v.voice_id}>{v.name} {v.category?'· '+v.category:''}</option>)}</select>}</label>}
          {mode==='replace' && <div className="timings"><label className="field"><span>Inicio (segundos)</span><input type="number" min="0" step="0.1" value={start} onChange={e=>setStart(e.target.value)} required/></label><label className="field"><span>Fin (segundos)</span><input type="number" min="0.1" step="0.1" value={end} onChange={e=>setEnd(e.target.value)} required/></label></div>}
          {(mode==='speech'||mode==='replace') && <label className="field"><span>Voz que se utilizará</span><select value={voice} onChange={e=>setVoice(e.target.value)} required><option value="">Selecciona una voz</option>{voices.map(v=><option key={v.voice_id} value={v.voice_id}>{v.name} {v.category?'· '+v.category:''}</option>)}</select></label>}
          {mode!=='speech' && <label className="consent"><input type="checkbox" checked={consent} onChange={e=>setConsent(e.target.checked)}/><span>Confirmo que tengo autorización para usar esta grabación y la voz seleccionada.</span></label>}
          {!apiReady && <div className="notice">Configura <code>JSF_LABS_API_KEY</code> en Render para clonar voces y generar texto con ellas. ElevenLabs es opcional para las otras funciones.</div>}
          {error && <div className="alert">{error}</div>}{message && <div className="success">{message}</div>}
          <button className="submit" disabled={busy || !apiReady}>{busy?<><LoaderCircle className="spin" size={18}/> Procesando audio…</>:<><WandSparkles size={18}/> {mode==='clone'?'Crear voz':mode==='speech'?'Generar audio':mode==='convert'?'Transformar voz':'Reemplazar fragmento'}</>}</button>
          {audioUrl && <div className="result"><b><AudioLines size={17}/> Resultado</b><audio controls src={audioUrl}/><a className="download" href={audioUrl} download={mode==='replace'?'audio-editado.mp3':mode==='convert'?'voz-transformada.mp3':'voz-generada.mp3'}><Download size={17}/> Descargar audio</a></div>}
        </form>
      </section>
      <p className="footnote">Utiliza únicamente voces propias o voces para las que tengas permiso expreso. Revisa el audio final antes de compartirlo.</p>
    </main>
    <footer>VOXNOVA AI <span>·</span> HERRAMIENTAS DE VOZ CON IA</footer>
  </div>;
}
createRoot(document.getElementById('root')).render(<App/>);
