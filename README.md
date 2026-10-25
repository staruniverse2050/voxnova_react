# VoxNova AI — React + FastAPI

Aplicación web de audio con interfaz React y backend FastAPI en el mismo servicio. No requiere instalar una aplicación en el dispositivo del usuario final; se accede desde el navegador cuando está desplegada.

## Funciones
- Generar audio desde texto con una voz seleccionada (`POST /api/speech`).
- Crear clon de una voz con muestra subida y consentimiento (`POST /api/voices/clone`).
- Convertir una grabación a una voz seleccionada (`POST /api/convert-voice`).
- Reemplazar un intervalo de un audio por una frase generada (`POST /api/replace-segment`).
- Grabar desde el micrófono en navegador compatible.

## Requisitos de proveedores
Para clonar voces y generar texto a voz, configura `REPLICAVOX_API_KEY` como variable secreta en Render. El plan gratuito anunciado por Replicavox incluye 15.000 caracteres al mes y una voz clonada; las voces clonadas deben hacerse públicas para usarlas por API en el plan gratuito. Las funciones Cambiar mi voz y Editar un audio todavía usan `ELEVENLABS_API_KEY`. Nunca publiques las llaves en el repositorio.

## Ejecutar en desarrollo
Requiere Node.js 20.19+ (o 22.12+) y Python 3.12+, además de FFmpeg para editar fragmentos.

Terminal 1, backend:
```bash
python -m venv .venv
# Windows: .venv\\Scripts\\activate
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
# define ELEVENLABS_API_KEY en el entorno
uvicorn app.main:app --reload --port 8000
```

Terminal 2, frontend:
```bash
cd frontend
npm install
npm run dev
```
Abre la URL de Vite que aparece en la terminal. El proxy envía `/api` y `/health` al backend local.

## Desplegar
El `Dockerfile` hace build del frontend React y lo sirve junto al backend FastAPI. Publica el repositorio en un host compatible con Docker (por ejemplo Render) y define `REPLICAVOX_API_KEY` como variable secreta (y `ELEVENLABS_API_KEY` si usarás las funciones de edición/conversión). Después abre la URL HTTPS generada por el proveedor. La URL pública no se crea automáticamente desde este ZIP.

## Endpoints
- `GET /health` — estado y si la API está configurada.
- `GET /api/voices` — voces disponibles en la cuenta.
- `POST /api/voices/clone` — formulario: `name`, `consent_confirmed`, `file`.
- `POST /api/speech` — JSON: `voice_id`, `text`.
- `POST /api/convert-voice` — formulario: `voice_id`, `consent_confirmed`, `file`.
- `POST /api/replace-segment` — formulario: `voice_id`, `start_seconds`, `end_seconds`, `replacement_text`, `consent_confirmed`, `file`.
- `GET /docs` — documentación interactiva.

Clona únicamente voces propias o con permiso expreso. La edición de fragmentos puede sonar menos natural si la duración de la frase nueva difiere mucho del segmento sustituido.
