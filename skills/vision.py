import os
import random
from typing import Dict, Any

try:
    import mss
    MSS_AVAILABLE = True
except ImportError:
    MSS_AVAILABLE = False


def _notes_dir() -> str:
    base = os.path.dirname(os.path.dirname(__file__))
    d = os.path.join(base, "notes")
    os.makedirs(d, exist_ok=True)
    return d


def _capturar(filename: str) -> str:
    """Toma una captura real de pantalla y la guarda en notes/. Devuelve la ruta."""
    with mss.mss() as sct:
        monitor = sct.monitors[1]
        sct_img = sct.grab(monitor)
        output_path = os.path.join(_notes_dir(), filename)
        mss.tools.to_png(sct_img.rgb, sct_img.size, output=output_path)
    return output_path


def capturar_pantalla(ctx: Dict[str, Any]) -> Dict[str, Any]:
    """Solo toma la captura, sin describir lo que hay (para guardarla o revisarla luego)."""
    dry = bool(ctx.get("dry_run", False))
    if dry:
        success = random.random() < 0.9
        return {"success": success, "data": {"status": "mocked_training"}, "message": "Captura simulada."}

    if not MSS_AVAILABLE:
        return {
            "success": False,
            "error": "Librería de captura no instalada. Usa 'pip install mss'.",
            "message": "No puedo capturar la pantalla, me falta el módulo mss."
        }

    try:
        output_path = _capturar("captura_pantalla.png")
        return {
            "success": True,
            "data": {"image_path": output_path},
            "message": f"He capturado tu pantalla y la guardé en {output_path}."
        }
    except Exception as e:
        return {"success": False, "error": str(e), "message": f"Falló la captura: {e}"}


def describir_pantalla(ctx: Dict[str, Any]) -> Dict[str, Any]:
    """Toma una captura y describe (de forma simulada) lo que hay en ella."""
    dry = bool(ctx.get("dry_run", False))
    history = ctx.get("history", [])

    if dry:
        success = random.random() < 0.9
        return {"success": success, "data": {"status": "mocked_training"}, "message": "Análisis simulado."}

    if not MSS_AVAILABLE:
        return {
            "success": False,
            "error": "Librerías de visión no instaladas. Usa 'pip install mss Pillow'.",
            "message": "No puedo ver, me faltan los módulos mss y Pillow."
        }

    try:
        output_path = _capturar("vision_capture.png")

        # Simulación de análisis (MOCK de una API real tipo GPT-4V)
        # En el futuro, aquí se enviaría output_path a una API de LLM Multimodal.
        analisis_simulado = "Veo una pantalla con algo de código y herramientas de desarrollo."

        # Si el usuario hace referencia a algo anterior, lo notamos en la respuesta
        if len(history) > 1:
            analisis_simulado += " Tomando en cuenta nuestra plática anterior, parece que sigues trabajando en el mismo proyecto."

        return {
            "success": True,
            "data": {
                "image_path": output_path,
                "analysis": analisis_simulado,
            },
            "message": f"He capturado tu pantalla y la he guardado en {output_path}. {analisis_simulado}"
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "message": f"Falló el análisis visual: {e}"
        }
