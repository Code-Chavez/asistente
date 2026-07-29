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

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

class JarvisGUI(ctk.CTk):
    def __init__(self, execute_callback: Callable[[Dict[str, Any]], Dict[str, Any]]):
        super().__init__()
        self.execute_callback = execute_callback
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
        self.btn = ctk.CTkButton(self.input_frame, text="Enviar", command=self.process_input, height=40, font=("Consolas", 14, "bold"))
        self.btn.pack(side="right")
        self.log_message("Sistema", "Jarvis inicializado. Interfaces online.")
    def log_message(self, sender: str, message: str):
        self.textbox.configure(state="normal")
        self.textbox.insert("end", f"[{sender}] {message}\n\n")
        self.textbox.configure(state="disabled")
        self.textbox.yview("end")
        if sender == "Jarvis":
            self.speak_text(message)
    def speak_text(self, text: str):
        """Usa pyttsx3 en un hilo separado para que Jarvis hable."""
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
        threading.Thread(target=run_tts, daemon=True).start()
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
                self.after(0, lambda: self.log_message("Sistema", f"Error de red: {e}"))
        except Exception as e:
            self.after(0, lambda: self.log_message("Sistema", f"Error de micrófono: {e}"))
        finally:
            self.is_recording = False
            self.after(0, lambda: self.mic_btn.configure(text="🎙️", state="normal", fg_color="#333333"))
    def _handle_voice_result(self, text: str):
        self.log_message("Usuario (Voz)", text)
        threading.Thread(target=self._process_command, args=(text,), daemon=True).start()
    def _process_command(self, text: str):
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
def run_gui(execute_callback):
    app = JarvisGUI(execute_callback)
    app.mainloop()
