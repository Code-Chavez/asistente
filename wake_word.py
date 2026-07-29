"""Detección de palabra de activación ("Hey Jarvis") en segundo plano.

Motor: openWakeWord (https://github.com/dscripka/openWakeWord).
100% local y OFFLINE, código abierto, SIN cuentas ni claves de acceso.
Usa el modelo pre-entrenado 'hey_jarvis' y captura el audio con sounddevice.

Requisitos:
  pip install openwakeword onnxruntime sounddevice numpy
Los modelos pre-entrenados se descargan solos la primera vez (una única vez).
"""
import time
import threading

try:
    import numpy as np
    import sounddevice as sd
    import openwakeword
    from openwakeword.model import Model
    OPENWAKEWORD_AVAILABLE = True
except ImportError:
    OPENWAKEWORD_AVAILABLE = False

SAMPLE_RATE = 16000   # openWakeWord trabaja a 16 kHz
FRAME = 1280          # tamaño de bloque recomendado (80 ms)


class WakeWordListener:
    """Escucha continua de la palabra clave. Llama a on_wake() al detectarla.

    Durante on_wake() se libera el micrófono (se pausa el stream) para que el
    resto de la app pueda capturar el comando dictado; luego se reanuda.
    """

    def __init__(self, on_wake, keyword: str = "hey_jarvis", threshold: float = 0.4,
                 on_status=None):
        self.on_wake = on_wake
        self.keyword = keyword
        self.threshold = threshold
        self.on_status = on_status   # callback opcional para reportar estado/score
        self.error = None
        self._thread = None
        self._running = False

    def _status(self, msg: str):
        if self.on_status:
            try:
                self.on_status(msg)
            except Exception:
                pass

    def available(self) -> bool:
        return OPENWAKEWORD_AVAILABLE

    def start(self) -> bool:
        if self._running:
            return True
        if not OPENWAKEWORD_AVAILABLE:
            self.error = "Faltan librerías: pip install openwakeword onnxruntime sounddevice"
            return False
        self.error = None
        self._running = True
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()
        return True

    def stop(self):
        self._running = False

    def is_running(self) -> bool:
        return self._running

    def _crear_modelo(self):
        """Crea el modelo; descarga los pesos pre-entrenados si aún no están."""
        try:
            return Model(wakeword_models=[self.keyword], inference_framework="onnx")
        except Exception:
            # Primera vez: descargamos los modelos pre-entrenados y reintentamos
            openwakeword.utils.download_models()
            return Model(wakeword_models=[self.keyword], inference_framework="onnx")

    def _loop(self):
        stream = None
        try:
            model = self._crear_modelo()
            # Usamos las claves REALES que carga el modelo (p.ej. 'hey_jarvis_v0.1'),
            # en vez de adivinar el nombre. Filtramos por 'jarvis' por si se cargan varias.
            all_keys = list(getattr(model, "models", {}).keys())
            keys = [k for k in all_keys if "jarvis" in k.lower()] or all_keys or [self.keyword]
            print(f"[WakeWord] escuchando; claves del modelo: {keys}")
            self._status(f"Escuchando 'Hey Jarvis' (modelo: {', '.join(keys)})")

            stream = sd.InputStream(samplerate=SAMPLE_RATE, channels=1,
                                    dtype="int16", blocksize=FRAME)
            stream.start()
            peak = 0.0
            last_report = time.time()
            while self._running:
                data, _ = stream.read(FRAME)
                audio = np.asarray(data, dtype=np.int16).reshape(-1)
                prediction = model.predict(audio)
                score = max((prediction.get(k, 0.0) for k in keys), default=0.0)
                if score > 0.3:  # traza de depuración para calibrar sensibilidad
                    print(f"[WakeWord] score={score:.2f}")
                # Reporte de pico a la GUI cada ~1.5 s para ver si el micro registra
                peak = max(peak, score)
                if time.time() - last_report > 1.5:
                    self._status(f"micrófono OK · pico 'Hey Jarvis' = {peak:.2f} "
                                 f"(dispara a {self.threshold})")
                    peak = 0.0
                    last_report = time.time()
                if score > self.threshold:
                    # Detectado: liberamos el micro para capturar el comando
                    stream.stop()
                    try:
                        self.on_wake()
                    except Exception as e:
                        print(f"[WakeWord] error en on_wake: {e}")
                    finally:
                        if self._running:
                            stream.start()
        except Exception as e:
            self.error = str(e)
            print(f"[WakeWord] error: {e}")
        finally:
            self._running = False
            try:
                if stream is not None:
                    stream.stop()
                    stream.close()
            except Exception:
                pass
