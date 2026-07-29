import customtkinter as ctk
import threading
from typing import Callable, Dict, Any

try:
    import sounddevice as sd
    from scipy.io.wavfile import write
    import speech_recognition as sr
    import os
    import tempfile
    AUDIO_AVAILABLE = True
except ImportError:
    AUDIO_AVAILABLE = False

from wake_word import WakeWordListener

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

class JarvisGUI(ctk.CTk):
    def __init__(self, execute_callback: Callable[[Dict[str, Any]], Dict[str, Any]],
                 feedback_callback: Callable[[str, float, Dict[str, Any]], None] = None,
                 actions: list = None):
        super().__init__()
        self.execute_callback = execute_callback
        self.feedback_callback = feedback_callback
        self.actions = actions or []          # acciones disponibles para corregir
        self.pending_feedback = None          # (action, query) de la última respuesta
        self.correction_query = None          # texto pendiente de corrección tras un 👎
        self.wake_listener = None             # escucha de palabra clave "Jarvis"
        self.title("Jarvis Assistant")
        self.geometry("700x500")
        # Output console
        self.textbox = ctk.CTkTextbox(self, width=660, height=400, font=("Consolas", 14), 
                                      fg_color="#1E1E1E", text_color="#00FF00")
        self.textbox.pack(pady=10, padx=20, fill="both", expand=True)
        self.textbox.configure(state="disabled")
        # Input frame
        self.input_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.input_frame.pack(pady=10, padx=20, fill="x")
        self.entry = ctk.CTkEntry(self.input_frame, placeholder_text="Escribe un comando...", font=("Consolas", 14), height=40)
        self.entry.pack(side="left", fill="x", expand=True, padx=(0, 5))
        self.entry.bind("<Return>", self.process_input)
        if AUDIO_AVAILABLE:
            self.mic_btn = ctk.CTkButton(self.input_frame, text="🎙️", width=40, height=40, 
                                         font=("Consolas", 16), command=self.start_listening,
                                         fg_color="#333333", hover_color="#555555")
            self.mic_btn.pack(side="left", padx=(0, 5))
            # Botón de modo manos libres (palabra clave "Jarvis")
            self.wake_btn = ctk.CTkButton(self.input_frame, text="🗣️", width=40, height=40,
                                          font=("Consolas", 16), command=self.toggle_wake,
                                          fg_color="#333333", hover_color="#555555")
            self.wake_btn.pack(side="left", padx=(0, 5))
        self.btn = ctk.CTkButton(self.input_frame, text="Enviar", command=self.process_input, height=40, font=("Consolas", 14, "bold"))
        self.btn.pack(side="right")
        # Barra de feedback 👍/👎 (solo si hay callback de aprendizaje)
        if self.feedback_callback:
            self.feedback_frame = ctk.CTkFrame(self, fg_color="transparent")
            self.feedback_frame.pack(pady=(0, 10), padx=20, fill="x")
            self.feedback_label = ctk.CTkLabel(self.feedback_frame, text="Esperando un comando...", font=("Consolas", 12))
            self.feedback_label.pack(side="left", padx=(0, 10))
            self.up_btn = ctk.CTkButton(self.feedback_frame, text="👍", width=50, height=32,
                                        command=lambda: self._send_feedback(True),
                                        fg_color="#2E7D32", hover_color="#1B5E20")
            self.up_btn.pack(side="left", padx=5)
            self.down_btn = ctk.CTkButton(self.feedback_frame, text="👎", width=50, height=32,
                                          command=lambda: self._send_feedback(False),
                                          fg_color="#C62828", hover_color="#8E0000")
            self.down_btn.pack(side="left", padx=5)
            # Barra de corrección (oculta hasta que haya un 👎)
            self.correction_frame = ctk.CTkFrame(self, fg_color="transparent")
            self.correction_label = ctk.CTkLabel(self.correction_frame, text="¿Cuál debió ser?", font=("Consolas", 12))
            self.correction_label.pack(side="left", padx=(0, 10))
            self.correction_menu = ctk.CTkOptionMenu(self.correction_frame,
                                                     values=self.actions or ["(sin acciones)"], width=220)
            self.correction_menu.pack(side="left", padx=5)
            self.correction_confirm = ctk.CTkButton(self.correction_frame, text="Corregir", width=90, height=32,
                                                    command=self._confirm_correction,
                                                    fg_color="#1565C0", hover_color="#0D47A1")
            self.correction_confirm.pack(side="left", padx=5)
            self._set_feedback_enabled(False)
        self.log_message("Sistema", "Jarvis inicializado. Interfaces online.")

    def _set_feedback_enabled(self, enabled: bool):
        if not self.feedback_callback:
            return
        state = "normal" if enabled else "disabled"
        self.up_btn.configure(state=state)
        self.down_btn.configure(state=state)
        self.feedback_label.configure(
            text="¿La última acción fue la correcta?" if enabled else "Esperando un comando..."
        )

    def _apply_feedback(self, action: str, reward: float, query: str):
        """Envía el feedback al router en segundo plano (puede guardar el modelo)."""
        def run():
            try:
                self.feedback_callback(action, reward, {"q": query})
            except Exception as e:
                msg = str(e)
                self.after(0, lambda: self.log_message("Sistema", f"Error guardando feedback: {msg}"))
        threading.Thread(target=run, daemon=True).start()

    def _send_feedback(self, positive: bool):
        if not self.pending_feedback:
            return
        action, query = self.pending_feedback
        self.pending_feedback = None
        self._set_feedback_enabled(False)

        if positive:
            self.log_message("Sistema", f"👍 Feedback registrado para [{action}]: reforzaré esa intención. ¡Gracias!")
            self._apply_feedback(action, 1.0, query)
        else:
            # Registramos el fallo de la acción equivocada...
            self.log_message("Sistema", f"👎 Anotado que [{action}] no era la correcta.")
            self._apply_feedback(action, 0.0, query)
            # ...y pedimos la acción correcta para aprenderla de verdad.
            if self.actions:
                self.correction_query = query
                self._show_correction(exclude=action)

    def _show_correction(self, exclude: str = None):
        opts = [a for a in self.actions if a != exclude] or list(self.actions)
        self.correction_menu.configure(values=opts)
        self.correction_menu.set(opts[0])
        self.correction_frame.pack(pady=(0, 10), padx=20, fill="x")

    def _hide_correction(self):
        if self.feedback_callback:
            self.correction_query = None
            self.correction_frame.pack_forget()

    def _confirm_correction(self):
        correct = self.correction_menu.get()
        query = self.correction_query
        self._hide_correction()
        if not correct or not query:
            return
        self.log_message("Sistema", f"✅ Aprendido: '{query}' → [{correct}]. ¡Gracias por corregirme!")
        self._apply_feedback(correct, 1.0, query)
    def log_message(self, sender: str, message: str):
        self.textbox.configure(state="normal")
        self.textbox.insert("end", f"[{sender}] {message}\n\n")
        self.textbox.configure(state="disabled")
        self.textbox.yview("end")
        if sender == "Jarvis":
            self.speak_text(message)
    def speak_text(self, text: str, block: bool = False):
        """Usa pyttsx3 para que Jarvis hable.

        block=True lo ejecuta de forma síncrona (útil antes de grabar un
        comando, para que la voz de Jarvis no se cuele en la grabación).
        """
        def run_tts():
            try:
                # pyrefly: ignore [missing-import]
                import pyttsx3
                # Inicializar el motor en este mismo hilo para evitar errores de COM en Windows
                engine = pyttsx3.init()
                engine.setProperty('rate', 170) # Velocidad un poco más natural
                # Buscar voz en español
                voices = engine.getProperty('voices')
                for voice in voices:
                    if 'spanish' in voice.name.lower() or 'es-' in voice.id.lower() or 'sabina' in voice.name.lower() or 'helena' in voice.name.lower() or 'pablo' in voice.name.lower():
                        engine.setProperty('voice', voice.id)
                        break
                engine.say(text)
                engine.runAndWait()
            except Exception as e:
                print(f"Error TTS: {e}")
        if block:
            run_tts()
        else:
            threading.Thread(target=run_tts, daemon=True).start()

    def toggle_wake(self):
        """Activa/desactiva la escucha de la palabra clave 'Jarvis'."""
        if self.wake_listener and self.wake_listener.is_running():
            self.wake_listener.stop()
            self.wake_listener = None
            self.wake_btn.configure(text="🗣️", fg_color="#333333")
            self.log_message("Sistema", "Modo manos libres desactivado.")
            return
        self.wake_listener = WakeWordListener(on_wake=self._on_wake_word)
        if self.wake_listener.start():
            self.wake_btn.configure(text="👂", fg_color="#1565C0")
            self.log_message("Sistema", "Modo manos libres activo. Di 'Hey Jarvis' para hablarme.")
        else:
            err = self.wake_listener.error or "No se pudo iniciar la escucha."
            self.wake_listener = None
            self.log_message("Sistema", f"No pude activar manos libres: {err}")

    def _on_wake_word(self):
        """Se ejecuta (en el hilo del listener) al detectar 'Jarvis'."""
        self.after(0, lambda: self.log_message("Sistema", "🗣️ 'Hey Jarvis' detectado."))
        # Acuse de recibo hablado y BLOQUEANTE, para no grabarlo dentro del comando
        self.speak_text("Sí, señor. ¿Qué hacemos?", block=True)
        text = self._grabar_y_transcribir(5)
        if text:
            self.after(0, lambda: self._handle_voice_result(text))
        else:
            self.after(0, lambda: self.log_message("Sistema", "No capté ningún comando. Di 'Hey Jarvis' otra vez."))

    def _grabar_y_transcribir(self, seconds: int = 5):
        """Graba una frase corta del micrófono y la transcribe. Devuelve texto o None."""
        if not AUDIO_AVAILABLE:
            return None
        try:
            fs = 44100
            rec = sd.rec(int(seconds * fs), samplerate=fs, channels=1, dtype='int16')
            sd.wait()
            temp_wav = os.path.join(tempfile.gettempdir(), "jarvis_cmd.wav")
            write(temp_wav, fs, rec)
            r = sr.Recognizer()
            with sr.AudioFile(temp_wav) as source:
                audio = r.record(source)
            return r.recognize_google(audio, language="es-ES")
        except Exception:
            return None

    def process_input(self, event=None):
        text = self.entry.get().strip()
        if not text:
            return
        self.entry.delete(0, "end")
        self.log_message("Usuario", text)
        # Excute in background
        threading.Thread(target=self._process_command, args=(text,), daemon=True).start()
    def start_listening(self):
        # Si ya está grabando, el segundo clic lo detiene
        if getattr(self, "is_recording", False):
            self.is_recording = False
            self.mic_btn.configure(text="⚙️", state="disabled", fg_color="#333333")
            return
        # Si no, empieza a grabar
        self.is_recording = True
        self.mic_btn.configure(text="🔴", fg_color="red")
        threading.Thread(target=self._record_and_process, daemon=True).start()
    def _record_and_process(self):
        try:
            import time as time_mod
            fs = 44100  # Sample rate
            max_seconds = 60  # Duración máxima de 1 minuto
            # Comenzar a grabar en segundo plano
            myrecording = sd.rec(int(max_seconds * fs), samplerate=fs, channels=1, dtype='int16')
            start_time = time_mod.time()
            # Bucle de espera activa chequeando la bandera de toggle
            while self.is_recording and time_mod.time() - start_time < max_seconds:
                time_mod.sleep(0.1)
            sd.stop()  # Detener la grabación
            self.is_recording = False # Por si salió por tiempo
            elapsed = time_mod.time() - start_time
            frames = int(elapsed * fs)
            # Recortar el array a la duración real grabada
            if frames < len(myrecording):
                myrecording = myrecording[:frames]
            self.after(0, lambda: self.mic_btn.configure(text="⚙️", state="disabled"))
            # Save as WAV file in temp
            temp_wav = os.path.join(tempfile.gettempdir(), "jarvis_temp_audio.wav")
            write(temp_wav, fs, myrecording)
            # Recognize using SpeechRecognition
            r = sr.Recognizer()
            with sr.AudioFile(temp_wav) as source:
                audio = r.record(source)
            try:
                # We use Google Speech Recognition
                text = r.recognize_google(audio, language="es-ES")
                self.after(0, lambda: self._handle_voice_result(text))
            except sr.UnknownValueError:
                self.after(0, lambda: self.log_message("Sistema", "No pude entender el audio."))
            except sr.RequestError as e:
                msg = str(e)
                self.after(0, lambda: self.log_message("Sistema", f"Error de red: {msg}"))
        except Exception as e:
            msg = str(e)
            self.after(0, lambda: self.log_message("Sistema", f"Error de micrófono: {msg}"))
        finally:
            self.is_recording = False
            self.after(0, lambda: self.mic_btn.configure(text="🎙️", state="normal", fg_color="#333333"))
    def _handle_voice_result(self, text: str):
        self.log_message("Usuario (Voz)", text)
        threading.Thread(target=self._process_command, args=(text,), daemon=True).start()
    def _process_command(self, text: str):
        if self.feedback_callback:
            self.pending_feedback = None
            self.after(0, self._hide_correction)
            self.after(0, lambda: self._set_feedback_enabled(False))
        response = self.execute_callback({"q": text, "dry_run": False})
        action = response.get("action", "Desconocido")
        res_data = response.get("result", {})
        success = res_data.get("success", False)
        msg = res_data.get("message", "")
        if not msg:
            if success:
                msg = f"Acción [{action}] ejecutada con éxito."
            else:
                err = res_data.get("error", "Error desconocido")
                msg = f"Falló al ejecutar [{action}]: {err}"
        # Detalles adicionales
        data = res_data.get("data", {})
        if data:
            msg += f"\nDetalles: {data}"
        self.after(0, lambda: self.log_message("Jarvis", msg))
        # Habilitamos el feedback para esta acción concreta
        if self.feedback_callback and action and action != "Desconocido":
            self.pending_feedback = (action, text)
            self.after(0, lambda: self._set_feedback_enabled(True))
def run_gui(execute_callback, feedback_callback=None, actions=None):
    app = JarvisGUI(execute_callback, feedback_callback, actions)
    app.mainloop()
