import os
import re
import time
import random
import webbrowser
import subprocess
from typing import Dict, Any, Optional, Tuple

try:
    import pyautogui
    PYAUTOGUI_AVAILABLE = True
except Exception:  # sin pantalla (p.ej. CI en Linux) falla con KeyError, no ImportError
    PYAUTOGUI_AVAILABLE = False

try:
    import pygetwindow as gw
    PYGETWINDOW_AVAILABLE = True
except Exception:
    PYGETWINDOW_AVAILABLE = False

CANCEL_FLAG = False
YOUTUBE_SEARCH_CACHE = []

def enfocar_navegador(url: str = "") -> bool:
    """Busca ventana de navegador, la activa y opcionalmente navega a una URL reusando pestaña."""
    if not PYGETWINDOW_AVAILABLE or not PYAUTOGUI_AVAILABLE:
        return False
        
    navegadores = ["Brave", "Chrome", "Edge", "Firefox", "YouTube"]
    ventana_objetivo = None
    
    for ventana in gw.getAllWindows():
        if not ventana.title: continue
        for nav in navegadores:
            if nav.lower() in ventana.title.lower():
                ventana_objetivo = ventana
                break
        if ventana_objetivo:
            break
            
    if ventana_objetivo:
        try:
            if ventana_objetivo.isMinimized:
                ventana_objetivo.restore()
            ventana_objetivo.activate()
            import time
            time.sleep(0.5)
            
            if url:
                # Ctrl+L para enfocar barra de direcciones (funciona en todos los navegadores)
                pyautogui.hotkey('ctrl', 'l')
                time.sleep(0.2)
                pyautogui.write(url)
                time.sleep(0.1)
                pyautogui.press('enter')
            return True
        except Exception:
            return False
    return False

def safe_sleep(seconds: float):
    """Duerme por X segundos revisando CANCEL_FLAG en intervalos cortos."""
    global CANCEL_FLAG
    import time
    start = time.time()
    while time.time() - start < seconds:
        if CANCEL_FLAG:
            raise InterruptedError("Acción cancelada por el usuario.")
        time.sleep(0.1)


def cancelar_accion(ctx: Dict[str, Any]) -> Dict[str, Any]:
    global CANCEL_FLAG
    CANCEL_FLAG = True
    return {"success": True, "message": "Abortando operación en curso de emergencia."}


def parse_search_query(q: str) -> str:
    """Extrae el concepto a buscar limpiando palabras de relleno y plataformas (conectores)."""
    q_low = f" {q.lower()} "
    
    # 1. Quitar menciones de la plataforma (al final o en medio)
    platforms = [
        " en youtube ", " en google ", " en el navegador ", 
        " en brave ", " en internet "
    ]
    for p in platforms:
        q_low = q_low.replace(p, " ")
        
    # 2. Quitar verbos y frases de acción (de más largo a más corto)
    fillers = [
        " investiga sobre ", " dime sobre ", " pon el video de ", " pon un video de ", 
        " reproduce la cancion de ", " reproduce la cancion ", " quien es ", " que es ", 
        " busca sobre ", " pon un video ", " reproduce a ", " reproduce ", 
        " investiga ", " buscame ", " busca ", " pon "
    ]
    for filler in fillers:
        if filler in q_low:
            q_low = q_low.replace(filler, " ", 1)
    
    return q_low.strip()

def buscar_web(ctx: Dict[str, Any]) -> Dict[str, Any]:
    q = ctx.get("q", "")
    dry = bool(ctx.get("dry_run", False))
    
    query = parse_search_query(q)
    if not query:
        query = q if q else "noticias"
        
    if dry:
        success = random.random() < 0.7
        return {"success": success, "data": {"query": query}}
        
    url = f"https://www.google.com/search?q={query}"
    ok = webbrowser.open(url)
    return {"success": bool(ok), "data": {"url": url}, "message": f"Buscando '{query}' en Google."}

def buscar_youtube(ctx: Dict[str, Any]) -> Dict[str, Any]:
    global CANCEL_FLAG, YOUTUBE_SEARCH_CACHE
    CANCEL_FLAG = False
    
    q = ctx.get("q", "")
    dry = bool(ctx.get("dry_run", False))
    
    query = parse_search_query(q)
    if not query:
        query = "musica" # Fallback
        
    if dry: return {"success": True}
    
    try:
        from youtubesearchpython import VideosSearch
        videos_search = VideosSearch(query, limit = 3)
        results = videos_search.result()['result']
        
        if not results:
            return {"success": False, "message": "No encontré videos para esa búsqueda."}
            
        # 1. Abrir o reutilizar pestaña con la búsqueda en vivo
        search_url = f"https://www.youtube.com/results?search_query={query.replace(' ', '+')}"
        if not enfocar_navegador(search_url):
            webbrowser.open(search_url)
            
        YOUTUBE_SEARCH_CACHE = []
        respuesta_texto = f"En tu pantalla veo estas opciones para {query}:\n"
        for i, video in enumerate(results):
            title = video['title']
            link = video['link']
            YOUTUBE_SEARCH_CACHE.append({"title": title, "link": link})
            respuesta_texto += f"{i+1}. {title}\n"
            
        respuesta_texto += "\n¿Cuál reproduzco?"
        
        return {"success": True, "message": respuesta_texto}
    except Exception as e:
        return {"success": False, "error": str(e), "message": "Falló la búsqueda en YouTube."}

def seleccionar_opcion(ctx: Dict[str, Any]) -> Dict[str, Any]:
    global YOUTUBE_SEARCH_CACHE
    q = ctx.get("q", "").lower()
    dry = bool(ctx.get("dry_run", False))
    
    if not YOUTUBE_SEARCH_CACHE:
        return {"success": False, "message": "No tengo opciones en memoria en este momento."}
        
    if dry: return {"success": True}
    
    idx = -1
    if "primer" in q or "1" in q or "uno" in q:
        idx = 0
    elif "segund" in q or "2" in q or "dos" in q:
        idx = 1
    elif "tercer" in q or "3" in q or "tres" in q:
        idx = 2
        
    if idx == -1 or idx >= len(YOUTUBE_SEARCH_CACHE):
        return {"success": False, "message": "No entendí la opción elegida. Dime el primero, segundo o tercero."}
        
    video = YOUTUBE_SEARCH_CACHE[idx]
    if not enfocar_navegador(video["link"]):
        webbrowser.open(video["link"])
        
    YOUTUBE_SEARCH_CACHE = [] # Limpiar la memoria tras reproducir
    
    return {"success": True, "message": f"Reproduciendo: {video['title']}"}

def controlar_pantalla(ctx: Dict[str, Any]) -> Dict[str, Any]:
    q = ctx.get("q", "").lower()
    dry = bool(ctx.get("dry_run", False))
    
    if not PYAUTOGUI_AVAILABLE and not dry:
        return {"success": False, "message": "Falta pyautogui para controlar la pantalla."}
        
    if dry: return {"success": True}
    
    if "baja" in q or "abajo" in q or "escrol" in q or "scroll" in q:
        pyautogui.scroll(-800)
        return {"success": True, "message": "Bajando pantalla."}
    elif "sube" in q or "arriba" in q:
        pyautogui.scroll(800)
        return {"success": True, "message": "Subiendo pantalla."}
    elif "pausa" in q or "play" in q or "reproduce" in q or "deten" in q:
        pyautogui.press("space")
        return {"success": True, "message": "Video pausado o reanudado."}
    elif "cierra" in q or "quitar" in q:
        pyautogui.hotkey('ctrl', 'w')
        return {"success": True, "message": "Pestaña cerrada."}
        
    return {"success": False, "message": "Comando de pantalla no reconocido."}


def crear_nota(ctx: Dict[str, Any]) -> Dict[str, Any]:
    q = ctx.get("q", "").lower()
    content = ctx.get("content", "")
    
    # NLP rudimentario para extraer contenido del texto dictado/escrito
    if not content:
        # Frases de activación para ignorar
        ignorar = [
            "apunta esto por favor", "apunta esto", "crea una nota importante", 
            "crea una nota", "crea un documento de word", "nuevo archivo de texto", 
            "escribir carta documento", "escribe un recordatorio", "nueva nota",
            "crear un documento"
        ]
        texto_limpio = q
        for frase in ignorar:
            if frase in texto_limpio:
                texto_limpio = texto_limpio.replace(frase, "")
                
        texto_limpio = texto_limpio.strip(' ":.,')
        if texto_limpio:
            content = texto_limpio
        else:
            content = "Nota vacía creada por comando directo."

    title = ctx.get("title", "nota")
    base = os.path.dirname(__file__)
    base = os.path.dirname(base)
    notes_dir = os.path.join(base, "notes")
    dry = bool(ctx.get("dry_run", False))
    ts = int(time.time())
    filename = f"{title}_{ts}.txt"
    path = os.path.join(notes_dir, filename)
    if dry:
        success = random.random() < 0.85
        return {"success": success, "data": {"path": path}}
    try:
        os.makedirs(notes_dir, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        return {"success": True, "data": {"path": path}}
    except Exception as e:
        return {"success": False, "error": str(e), "data": {"path": path}}


def abrir_app(ctx: Dict[str, Any]) -> Dict[str, Any]:
    q = ctx.get("q", "").lower()
    app = ctx.get("app", "notepad")
    
    if "calculadora" in q or "calc" in q:
        app = "calc"
    elif "explorador" in q or "archivos" in q:
        app = "explorer"
    elif "cmd" in q or "consola" in q or "terminal" in q:
        app = "cmd"
    elif "paint" in q:
        app = "mspaint"
        
    dry = bool(ctx.get("dry_run", False))
    if dry:
        return {"success": True, "data": {"app": app}}
    try:
        subprocess.Popen(f"start {app}", shell=True)
        return {"success": True, "data": {"app": app}, "message": f"He abierto {app}."}
    except Exception as e:
        return {"success": False, "error": str(e), "data": {"app": app}}

def abrir_excel(ctx: Dict[str, Any]) -> Dict[str, Any]:
    dry = bool(ctx.get("dry_run", False))
    if dry: return {"success": True}
    try:
        # os.startfile("excel") falla: espera una ruta, no el nombre del ejecutable.
        # 'start' resuelve el ejecutable vía PATH / registro de apps.
        subprocess.Popen("start excel", shell=True)
        return {"success": True, "message": "Excel abierto con éxito."}
    except Exception as e:
        return {"success": False, "error": str(e), "message": "No se pudo abrir Excel."}

def crear_documento(ctx: Dict[str, Any]) -> Dict[str, Any]:
    dry = bool(ctx.get("dry_run", False))
    if dry: return {"success": True}
    try:
        subprocess.Popen("start winword", shell=True)
        return {"success": True, "message": "Microsoft Word abierto con éxito."}
    except Exception as e:
        return {"success": False, "error": str(e), "message": "No se pudo abrir Word."}

# "por whatsapp", "de whatsapp", "en wasap"... no forman parte del contacto.
_PLATAFORMA_WA = re.compile(r"\s+(?:por|de|en|via|vía)\s+(?:whatsapp|whatsaap|wasap|wassap|whats)\b",
                            re.IGNORECASE)

# Google Speech-to-Text suele usar la escritura en inglés para ciertos nombres.
CORRECCIONES_NOMBRES = {
    "Christopher": "Cristofer",
    "Cristopher": "Cristofer",
    "Jon": "John",
    "Brainy": "Brayni",
}


def _primer_marcador(texto: str, marcadores) -> Optional[Tuple[int, str]]:
    """(posición, marcador) del marcador que aparece ANTES en el texto.

    A igual posición gana el más largo (" dile que " frente a " dile ").
    """
    mejor = None
    for m in marcadores:
        i = texto.find(m)
        if i != -1 and (mejor is None or i < mejor[0] or (i == mejor[0] and len(m) > len(mejor[1]))):
            mejor = (i, m)
    return mejor


def parse_whatsapp_command(q_original: str) -> Tuple[str, str]:
    """
    NLP rudimentario usando patrones de conectores.
    Extrae el contacto y el mensaje de una frase, preservando mayúsculas.
    """
    q_orig = f" {_PLATAFORMA_WA.sub('', q_original).strip()} "
    q_low = q_orig.lower()

    # Conectores para identificar el contacto y el mensaje. Se usa el que
    # aparece primero en la frase (no el primero de la lista): así en
    # "manda a maria que compre pan para la cena" el contacto es "maria".
    contact_markers = [" a quien ", " para ", " busca a ", " busca ", " a "]
    msg_markers = [" diciendo que ", " diciendo ", " y dile que ", " y dile ",
                   " que diga ", " dile que ", " dile ", " que ", " como ", " el mensaje "]

    contact = ""
    message = ""

    found = _primer_marcador(q_low, contact_markers)
    if found:
        start_contact_idx = found[0] + len(found[1])
        resto_low = q_low[start_contact_idx:]
        resto_orig = q_orig[start_contact_idx:]

        msg = _primer_marcador(resto_low, msg_markers)
        if msg:
            message = resto_orig[msg[0] + len(msg[1]):].strip()
            contact = resto_orig[:msg[0]].strip()
        else:
            contact = resto_orig.strip()

    # Limpiar contacto de palabras sueltas si es muy largo
    cw = contact.split()[:3]  # asume máximo 3 palabras para un contacto

    # Mayúsculas + corrección fonética de nombres, palabra a palabra
    # (reemplazar subcadenas convertía "Jonathan" en "Johnathan").
    contact = " ".join(CORRECCIONES_NOMBRES.get(w.title(), w.title()) for w in cw)
    if message:
        message = message[0].upper() + message[1:]

    return contact.strip(), message.strip()


def describir_enviar_whatsapp(ctx: Dict[str, Any]) -> Optional[str]:
    """Texto de confirmación, o None si el skill no va a enviar nada."""
    contact, message = parse_whatsapp_command(ctx.get("q", ""))
    if not contact or not message:
        return None  # solo abre WhatsApp o pide el mensaje: nada que confirmar
    return f"Voy a enviar un WhatsApp a «{contact}» con el mensaje: «{message}»."


def describir_llamar_whatsapp(ctx: Dict[str, Any]) -> Optional[str]:
    contact, _ = parse_whatsapp_command(ctx.get("q", ""))
    if not contact:
        return None  # el skill preguntará a quién llamar
    return f"Voy a llamar a «{contact}» por WhatsApp."


def describir_enviar_nota_voz(ctx: Dict[str, Any]) -> Optional[str]:
    q = ctx.get("q", "")
    contact, _ = parse_whatsapp_command(q)
    if not contact:
        return None  # el skill preguntará a quién enviarla
    return f"Voy a grabar una nota de voz de ~{_dur_segundos(q)} s y enviarla a «{contact}»."


def enviar_whatsapp(ctx: Dict[str, Any]) -> Dict[str, Any]:
    global CANCEL_FLAG
    CANCEL_FLAG = False
    q_original = ctx.get("q", "")
    dry = bool(ctx.get("dry_run", False))
    
    if not PYAUTOGUI_AVAILABLE and not dry:
        return {"success": False, "message": "Falta la librería pyautogui para usar RPA."}
        
    # Extracción mejorada de contacto y mensaje usando el nuevo parser de conectores
    contact, message = parse_whatsapp_command(q_original)

    if dry: return {"success": True}

    # Con contacto pero sin mensaje NO enviamos un texto inventado: preguntamos.
    if contact and not message:
        return {"success": False,
                "message": f"¿Qué le digo a {contact}? Por ejemplo: 'whatsapp a {contact} diciendo hola'."}

    try:
        subprocess.Popen("start whatsapp:", shell=True)
        safe_sleep(6.0) # Tiempo generoso para que abra WhatsApp Desktop
        
        # Si no detectamos contacto, solo lo abrimos
        if not contact:
            return {"success": True, "message": "WhatsApp abierto (no se detectó contacto)."}
            
        # Buscar contacto
        pyautogui.hotkey('ctrl', 'f')
        safe_sleep(1.0)
        
        pyautogui.write(contact, interval=0.05)
        safe_sleep(2.0) # Esperar a que los resultados de búsqueda carguen
        
        pyautogui.press('enter') # Entrar al chat
        safe_sleep(1.5)
        
        # Escribir mensaje
        pyautogui.write(message, interval=0.03)
        safe_sleep(1.0)
        
        # Enviar de verdad el mensaje
        pyautogui.press('enter')
        
        return {"success": True, "message": f"Flujo RPA completado: Mensaje escrito a {contact}."}
    except InterruptedError as e:
        return {"success": False, "message": str(e)}
    except Exception as e:
        return {"success": False, "error": str(e), "message": "Falló la automatización RPA."}


# ---- Automatización avanzada de WhatsApp (nota de voz y llamada) ----
# Estas acciones localizan botones en pantalla por imagen. Necesitan capturas
# de referencia (hazlas una vez desde TU WhatsApp) en la carpeta assets/:
#   assets/wa_mic.png   -> botón del micrófono
#   assets/wa_send.png  -> botón de enviar (opcional)
#   assets/wa_call.png  -> botón de llamada de voz
# Es un enfoque best-effort: depende de tu resolución/tema y puede fallar.

def _assets_dir() -> str:
    base = os.path.dirname(os.path.dirname(__file__))
    return os.path.join(base, "assets")


def _dur_segundos(q: str, default: int = 5) -> int:
    """Duración pedida en la frase (p.ej. 'nota de voz de 10 segundos')."""
    m = re.search(r"(\d+)\s*(seg|segundo|segundos|s)?\b", q.lower())
    if m:
        try:
            return max(1, min(int(m.group(1)), 120))
        except ValueError:
            pass
    return default


def _localizar_boton(nombre_img: str):
    """Centro (x, y) de un botón por imagen, o None si no está calibrado/visible."""
    if not PYAUTOGUI_AVAILABLE:
        return None
    ruta = os.path.join(_assets_dir(), nombre_img)
    if not os.path.exists(ruta):
        return None
    try:
        # confidence requiere opencv; si no está instalado, cae a coincidencia exacta.
        try:
            return pyautogui.locateCenterOnScreen(ruta, confidence=0.8)
        except TypeError:
            return pyautogui.locateCenterOnScreen(ruta)
    except Exception:
        return None


def _abrir_chat_whatsapp(contact: str) -> bool:
    """Abre WhatsApp Desktop y entra al chat del contacto vía búsqueda."""
    subprocess.Popen("start whatsapp:", shell=True)
    safe_sleep(6.0)
    if not contact:
        return False
    pyautogui.hotkey('ctrl', 'f')
    safe_sleep(1.0)
    pyautogui.write(contact, interval=0.05)
    safe_sleep(2.0)
    pyautogui.press('enter')
    safe_sleep(1.5)
    return True


def enviar_nota_voz(ctx: Dict[str, Any]) -> Dict[str, Any]:
    global CANCEL_FLAG
    CANCEL_FLAG = False
    q_original = ctx.get("q", "")
    dry = bool(ctx.get("dry_run", False))
    seconds = _dur_segundos(q_original)

    if dry:
        return {"success": True}

    if not PYAUTOGUI_AVAILABLE:
        return {"success": False, "message": "Falta pyautogui para grabar notas de voz por RPA."}

    contact, _ = parse_whatsapp_command(q_original)
    if not contact:
        return {"success": False, "message": "¿A quién envío la nota de voz? No detecté el contacto."}

    if not os.path.exists(os.path.join(_assets_dir(), "wa_mic.png")):
        return {"success": False, "message": "Para notas de voz necesito una captura del botón del micrófono en assets/wa_mic.png."}
    try:
        _abrir_chat_whatsapp(contact)
        mic = _localizar_boton("wa_mic.png")
        if mic is None:
            return {"success": False, "message": "No encontré el botón de micrófono en pantalla (revisa assets/wa_mic.png)."}
        # Mantener pulsado para grabar la nota de voz
        pyautogui.mouseDown(mic.x, mic.y)
        safe_sleep(seconds)
        pyautogui.mouseUp(mic.x, mic.y)
        safe_sleep(0.5)
        # Si hay un botón de envío separado, lo pulsamos
        send = _localizar_boton("wa_send.png")
        if send is not None:
            pyautogui.click(send.x, send.y)
        return {"success": True, "message": f"Nota de voz de ~{seconds}s enviada a {contact}."}
    except InterruptedError as e:
        return {"success": False, "message": str(e)}
    except Exception as e:
        return {"success": False, "error": str(e), "message": "Falló la nota de voz por RPA."}


def llamar_whatsapp(ctx: Dict[str, Any]) -> Dict[str, Any]:
    global CANCEL_FLAG
    CANCEL_FLAG = False
    q_original = ctx.get("q", "")
    dry = bool(ctx.get("dry_run", False))

    if dry:
        return {"success": True}

    if not PYAUTOGUI_AVAILABLE:
        return {"success": False, "message": "Falta pyautogui para llamar por RPA."}

    contact, _ = parse_whatsapp_command(q_original)
    if not contact:
        return {"success": False, "message": "¿A quién llamo? No detecté el contacto."}

    try:
        _abrir_chat_whatsapp(contact)
        call = _localizar_boton("wa_call.png")
        if call is None:
            return {"success": False, "message": "Abrí el chat pero no encontré el botón de llamada. Guarda una captura en assets/wa_call.png."}
        pyautogui.click(call.x, call.y)
        return {"success": True, "message": f"Llamando a {contact} por WhatsApp."}
    except InterruptedError as e:
        return {"success": False, "message": str(e)}
    except Exception as e:
        return {"success": False, "error": str(e), "message": "Falló la llamada por RPA."}
