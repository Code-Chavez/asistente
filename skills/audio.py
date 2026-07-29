import os
import re
import time
from typing import Dict, Any

try:
    import sounddevice as sd
    from scipy.io.wavfile import write as wav_write
    AUDIO_AVAILABLE = True
except ImportError:
    AUDIO_AVAILABLE = False

SAMPLE_RATE = 44100


def _parse_seconds(q: str, default: int = 8) -> int:
    """Extrae la duración en segundos de la frase (p.ej. 'graba 15 segundos')."""
    m = re.search(r"(\d+)\s*(seg|segundo|segundos|s)?\b", q.lower())
    if m:
        try:
            secs = int(m.group(1))
            # Acotamos a un rango sensato (1s..5min)
            return max(1, min(secs, 300))
        except ValueError:
            pass
    return default


def grabar_audio(ctx: Dict[str, Any]) -> Dict[str, Any]:
    """Graba desde el micrófono y guarda un .wav en la carpeta notes/."""
    q = ctx.get("q", "")
    dry = bool(ctx.get("dry_run", False))
    seconds = _parse_seconds(q)

    if dry:
        return {"success": True, "data": {"seconds": seconds}}

    if not AUDIO_AVAILABLE:
        return {
            "success": False,
            "error": "Faltan librerías de audio.",
            "message": "No puedo grabar: faltan sounddevice y scipy (pip install sounddevice scipy).",
        }

    base = os.path.dirname(os.path.dirname(__file__))
    notes_dir = os.path.join(base, "notes")
    ts = int(time.time())
    path = os.path.join(notes_dir, f"audio_{ts}.wav")

    try:
        os.makedirs(notes_dir, exist_ok=True)
        grabacion = sd.rec(int(seconds * SAMPLE_RATE), samplerate=SAMPLE_RATE, channels=1, dtype="int16")
        sd.wait()  # Espera a que termine la grabación
        wav_write(path, SAMPLE_RATE, grabacion)
        return {
            "success": True,
            "data": {"path": path, "seconds": seconds},
            "message": f"He grabado {seconds} segundos de audio y lo guardé en {path}.",
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "message": f"Falló la grabación de audio: {e}",
        }
