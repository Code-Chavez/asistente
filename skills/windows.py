import os
import time
import random
import webbrowser
import subprocess
from typing import Dict, Any

try:
    import pyautogui
    PYAUTOGUI_AVAILABLE = True
except ImportError:
    PYAUTOGUI_AVAILABLE = False

try:
    import pygetwindow as gw
    PYGETWINDOW_AVAILABLE = True
except ImportError:
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

def parse_whatsapp_command(q_original: str) -> tuple[str, str]:
    """
    NLP rudimentario usando patrones de conectores.
    Extrae el contacto y el mensaje de una frase, preservando mayúsculas.
    """
    q_low = f" {q_original.lower()} "
    q_orig = f" {q_original} "
    
    # Conectores para identificar el contacto (ordenados de más largo a más corto)
    contact_markers = [" a quien ", " para ", " busca a ", " busca ", " a "]
    
    # Conectores para identificar el mensaje
    msg_markers = [" diciendo que ", " diciendo ", " y dile que ", " y dile ", 
                   " que diga ", " dile que ", " dile ", " que ", " como ", " el mensaje "]
    
    contact = ""
    message = ""
    
    start_contact_idx = -1
    for marker in contact_markers:
        if marker in q_low:
            start_contact_idx = q_low.find(marker) + len(marker)
            break
            
    if start_contact_idx != -1:
        resto_low = q_low[start_contact_idx:]
        resto_orig = q_orig[start_contact_idx:]
        
        start_msg_idx = -1
        for marker in msg_markers:
            if marker in resto_low:
                start_msg_idx = resto_low.find(marker)
                message = resto_orig[start_msg_idx + len(marker):].strip()
                contact = resto_orig[:start_msg_idx].strip()
                break
                
        if start_msg_idx == -1:
            contact = resto_orig.strip()
            
    # Limpiar contacto de palabras sueltas si es muy largo
    if contact:
        cw = contact.split()
        if len(cw) > 3:
            contact = " ".join(cw[:3]) # asume máximo 3 palabras para un contacto
            
    # 1. Aplicar título (Mayúsculas)
    contact = contact.title()
    if message:
        message = message[0].upper() + message[1:]
        
    # 2. Corrección fonética manual de nombres (Alias)
    # Google Speech-to-Text suele usar la escritura en inglés para ciertos nombres.
    correcciones_nombres = {
        "Christopher": "Cristofer",
        "Cristopher": "Cristofer",
        "Jon": "John",
        "Brainy": "Brayni"
    }
    
    for mal_escrito, bien_escrito in correcciones_nombres.items():
        contact = contact.replace(mal_escrito, bien_escrito)
            
    return contact.strip(), message.strip()

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
        if not message:
            message = "Hola, este es un mensaje automatizado enviado por Jarvis."
            
        pyautogui.write(message, interval=0.03)
        safe_sleep(1.0)
        
        # Enviar de verdad el mensaje
        pyautogui.press('enter')
        
        return {"success": True, "message": f"Flujo RPA completado: Mensaje escrito a {contact}."}
    except InterruptedError as e:
        return {"success": False, "message": str(e)}
    except Exception as e:
        return {"success": False, "error": str(e), "message": "Falló la automatización RPA."}
