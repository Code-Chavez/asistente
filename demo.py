import os
import sys
from agent import SkillRouter
from skills import buscar_web, buscar_youtube, crear_nota, abrir_app, enviar_whatsapp, abrir_excel, crear_documento, analizar_pantalla, cancelar_accion, seleccionar_opcion, controlar_pantalla
from gui import run_gui

MODEL_PATH = os.path.join("agent", "model.pkl")


def main():
    router = SkillRouter(epsilon=0.1) # Bajamos epsilon para explotar más
    router.register_skill("buscar_web", buscar_web)
    router.register_skill("buscar_youtube", buscar_youtube)
    router.register_skill("seleccionar_opcion", seleccionar_opcion)
    router.register_skill("controlar_pantalla", controlar_pantalla)
    router.register_skill("crear_nota", crear_nota)
    router.register_skill("abrir_app", abrir_app)
    router.register_skill("enviar_whatsapp", enviar_whatsapp)
    router.register_skill("abrir_excel", abrir_excel)
    router.register_skill("crear_documento", crear_documento)
    router.register_skill("analizar_pantalla", analizar_pantalla)
    router.register_skill("cancelar_accion", cancelar_accion)
    
    if "--reset" in sys.argv:
        pref_path = os.path.join("agent", "preferences.json")
        log_path = "training_log.jsonl"
        for p in [pref_path, log_path, MODEL_PATH]:
            if os.path.exists(p):
                os.remove(p)
        print("Memoria, modelo y logs reseteados")
        return
        
    dry = "--real" not in sys.argv
    def load_contexts(defaults):
        if "--contexts" in sys.argv:
            import os, json
            try:
                idx = sys.argv.index("--contexts")
                path = sys.argv[idx + 1] if idx + 1 < len(sys.argv) else ""
                if path and os.path.exists(path):
                    with open(path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    if isinstance(data, list):
                        return data
            except Exception:
                pass
        return defaults
        
    # Añadimos datos de entrenamiento para que el clasificador de ML aprenda
    # a mapear textos a skills específicas
    training_data = [
        {"q": "clima hoy", "expected_action": "buscar_web"},
        {"q": "busca en google el clima", "expected_action": "buscar_web"},
        {"q": "investiga sobre inteligencia artificial", "expected_action": "buscar_web"},
        {"q": "busca imagenes de gatos", "expected_action": "buscar_web"},
        {"q": "dime sobre la revolucion francesa", "expected_action": "buscar_web"},
        
        {"q": "pon en youtube un video de risa", "expected_action": "buscar_youtube"},
        {"q": "reproduce la cancion despacito en youtube", "expected_action": "buscar_youtube"},
        {"q": "busca en youtube tutorial de python", "expected_action": "buscar_youtube"},
        {"q": "pon a coldplay", "expected_action": "buscar_youtube"},
        
        {"q": "el primero", "expected_action": "seleccionar_opcion"},
        {"q": "reproduce el segundo", "expected_action": "seleccionar_opcion"},
        {"q": "la opcion 1", "expected_action": "seleccionar_opcion"},
        {"q": "el tercer video", "expected_action": "seleccionar_opcion"},
        
        {"q": "baja un poco", "expected_action": "controlar_pantalla"},
        {"q": "sube la pantalla", "expected_action": "controlar_pantalla"},
        {"q": "pausa el video", "expected_action": "controlar_pantalla"},
        {"q": "cierra la pestaña", "expected_action": "controlar_pantalla"},
        {"q": "escrol para abajo", "expected_action": "controlar_pantalla"},
        
        {"q": "crea una nota importante", "expected_action": "crear_nota"},
        {"q": "apunta esto por favor", "expected_action": "crear_nota"},
        {"q": "nueva nota", "expected_action": "crear_nota"},
        {"q": "escribe un recordatorio", "expected_action": "crear_nota"},
        
        {"q": "abre el explorador", "expected_action": "abrir_app"},
        {"q": "inicia la calculadora", "expected_action": "abrir_app"},
        {"q": "ejecuta notepad", "expected_action": "abrir_app"},
        
        {"q": "envia un whatsapp a maria hola", "expected_action": "enviar_whatsapp"},
        {"q": "mandale un mensaje por whatsapp a carlos", "expected_action": "enviar_whatsapp"},
        {"q": "whatsapp a mama diciendo llego tarde", "expected_action": "enviar_whatsapp"},
        {"q": "abre whatsapp", "expected_action": "enviar_whatsapp"},
        {"q": "abre whatsaapp", "expected_action": "enviar_whatsapp"},
        
        {"q": "abre un excel", "expected_action": "abrir_excel"},
        {"q": "nueva hoja de calculo", "expected_action": "abrir_excel"},
        {"q": "crea un excel para cuentas", "expected_action": "abrir_excel"},
        
        {"q": "crea un documento de word", "expected_action": "crear_documento"},
        {"q": "nuevo archivo de texto", "expected_action": "crear_documento"},
        {"q": "escribir carta documento", "expected_action": "crear_documento"},
        
        {"q": "mira mi pantalla", "expected_action": "analizar_pantalla"},
        {"q": "que ves en mi pantalla", "expected_action": "analizar_pantalla"},
        {"q": "toma una captura", "expected_action": "analizar_pantalla"},
        {"q": "dime que hay aqui", "expected_action": "analizar_pantalla"},
        
        {"q": "cancela", "expected_action": "cancelar_accion"},
        {"q": "detente", "expected_action": "cancelar_accion"},
        {"q": "para la automatizacion", "expected_action": "cancelar_accion"},
        {"q": "abortar mision", "expected_action": "cancelar_accion"},
    ]
    
    contexts = load_contexts(training_data)

    def train_epochs(epochs: int):
        """Entrena el clasificador de intención de forma supervisada.

        Usa train_intent (no add_feedback) para NO contaminar preferences.json
        con éxitos/fallos simulados que nunca ocurrieron de verdad.
        """
        for _ in range(epochs):
            for ctx in contexts:
                router.train_intent(ctx["expected_action"], {"q": ctx["q"], "dry_run": True})

    # Cargamos el modelo persistido para seguir entrenando sobre lo ya aprendido
    loaded = router.load_model(MODEL_PATH)

    if "--train" in sys.argv:
        train_epochs(50)
        router.save_model(MODEL_PATH)
        print("Entrenamiento ML completado y guardado. El modelo de Intenciones está listo.")
    elif "--status" in sys.argv:
        print("Modelo cargado:", loaded)
        print("Valores:", router.get_values())
        print("Conteos:", router.get_counts())
        print("Stats:", router.get_stats())
    else:
        # Iniciar GUI por defecto
        if loaded:
            print("Modelo previo cargado. Reforzando con datos recientes...")
            train_epochs(5)   # refresco ligero sobre lo ya aprendido
        else:
            print("Entrenando cerebro de Machine Learning por primera vez...")
            train_epochs(30)
        router.save_model(MODEL_PATH)
        print("Entrenamiento listo. Iniciando GUI...")
        try:
            run_gui(router.execute)
        finally:
            # Persistimos lo aprendido online durante la sesión (ejecuciones reales)
            router.save_model(MODEL_PATH)
            print("Modelo guardado. Hasta luego.")


if __name__ == "__main__":
    main()
