"""Detección de palabra de activación ("Jarvis") en segundo plano con Porcupine.

Porcupine hace la detección de forma OFFLINE: solo el comando que dictas
DESPUÉS de decir "Jarvis" sale del equipo (para transcribirse). El audio
ambiente nunca se envía a la nube mientras espera la palabra clave.

Requisitos:
  pip install pvporcupine pvrecorder
  AccessKey gratis de https://console.picovoice.ai puesto en:
    - la variable de entorno PICOVOICE_ACCESS_KEY, o
    - un archivo 'picovoice.key' junto a este módulo (gitignoreado).
"""
import os
import threading

try:
    import pvporcupine
    from pvrecorder import PvRecorder
    PORCUPINE_AVAILABLE = True
except ImportError:
    PORCUPINE_AVAILABLE = False


def get_access_key() -> str:
    """Obtiene el AccessKey de Picovoice desde el entorno o un archivo local."""
    key = os.environ.get("PICOVOICE_ACCESS_KEY", "").strip()
    if key:
        return key
    base = os.path.dirname(__file__)
    for name in ("picovoice.key", ".picovoice_key"):
        path = os.path.join(base, name)
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    return f.read().strip()
            except Exception:
                pass
    return ""


class WakeWordListener:
    """Escucha continua de una palabra clave. Llama a on_wake() al detectarla.

    Durante on_wake() se libera el micrófono (se pausa el grabador) para que el
    resto de la app pueda capturar el comando dictado; luego se reanuda.
    """

    def __init__(self, on_wake, keyword: str = "jarvis", sensitivity: float = 0.5):
        self.on_wake = on_wake
        self.keyword = keyword
        self.sensitivity = sensitivity
        self.error = None
        self._thread = None
        self._running = False

    def available(self) -> bool:
        return PORCUPINE_AVAILABLE and bool(get_access_key())

    def start(self) -> bool:
        if self._running:
            return True
        if not PORCUPINE_AVAILABLE:
            self.error = "Faltan librerías: pip install pvporcupine pvrecorder"
            return False
        key = get_access_key()
        if not key:
            self.error = ("Falta el AccessKey de Picovoice. Ponlo en la variable "
                          "PICOVOICE_ACCESS_KEY o en el archivo picovoice.key")
            return False
        self.error = None
        self._running = True
        self._thread = threading.Thread(target=self._loop, args=(key,), daemon=True)
        self._thread.start()
        return True

    def stop(self):
        self._running = False

    def is_running(self) -> bool:
        return self._running

    def _loop(self, key: str):
        porcupine = None
        recorder = None
        try:
            porcupine = pvporcupine.create(
                access_key=key,
                keywords=[self.keyword],
                sensitivities=[self.sensitivity],
            )
            recorder = PvRecorder(frame_length=porcupine.frame_length, device_index=-1)
            recorder.start()
            while self._running:
                pcm = recorder.read()
                if porcupine.process(pcm) >= 0:
                    # Detectado: liberamos el micro para capturar el comando
                    recorder.stop()
                    try:
                        self.on_wake()
                    except Exception as e:
                        print(f"[WakeWord] error en on_wake: {e}")
                    finally:
                        if self._running:
                            recorder.start()
        except Exception as e:
            self.error = str(e)
            print(f"[WakeWord] error: {e}")
        finally:
            self._running = False
            try:
                if recorder is not None:
                    recorder.stop()
                    recorder.delete()
            except Exception:
                pass
            try:
                if porcupine is not None:
                    porcupine.delete()
            except Exception:
                pass
