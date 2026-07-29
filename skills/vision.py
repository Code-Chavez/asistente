import os
import random
from typing import Dict, Any

try:
    import mss
    from PIL import Image
    MSS_AVAILABLE = True
except ImportError:
    MSS_AVAILABLE = False


def analizar_pantalla(ctx: Dict[str, Any]) -> Dict[str, Any]:
    q = ctx.get("q", "")
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
        # Tomar captura de pantalla real
        with mss.mss() as sct:
            monitor = sct.monitors[1]
            sct_img = sct.grab(monitor)
            # Guardar la imagen localmente
            base = os.path.dirname(os.path.dirname(__file__))
            notes_dir = os.path.join(base, "notes")
            os.makedirs(notes_dir, exist_ok=True)
            output_path = os.path.join(notes_dir, "vision_capture.png")
            
            mss.tools.to_png(sct_img.rgb, sct_img.size, output=output_path)

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
                "analysis": analisis_simulado
            },
            "message": f"He capturado tu pantalla y la he guardado en {output_path}. {analisis_simulado}"
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "message": f"Falló el análisis visual: {e}"
        }
