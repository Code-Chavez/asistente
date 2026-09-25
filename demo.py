import os
import sys
from agent import SkillRouter
from skills import buscar_web, buscar_youtube, crear_nota, abrir_app, enviar_whatsapp, abrir_excel, crear_documento, analizar_pantalla, cancelar_accion, seleccionar_opcion, controlar_pantalla, enviar_nota_voz, llamar_whatsapp, grabar_audio
from skills.windows import describir_enviar_whatsapp, describir_llamar_whatsapp, describir_enviar_nota_voz
from skills.charla import ninguna
from agent.datasets import training_examples
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
    router.register_skill("enviar_whatsapp", enviar_whatsapp, confirm=describir_enviar_whatsapp)
    router.register_skill("abrir_excel", abrir_excel)
    router.register_skill("crear_documento", crear_documento)
    router.register_skill("analizar_pantalla", analizar_pantalla)
    router.register_skill("cancelar_accion", cancelar_accion)
    router.register_skill("grabar_audio", grabar_audio)
    router.register_skill("enviar_nota_voz", enviar_nota_voz, confirm=describir_enviar_nota_voz)
    router.register_skill("llamar_whatsapp", llamar_whatsapp, confirm=describir_llamar_whatsapp)
    # "No es un comando": saludos, charla, cosas que Jarvis no sabe hacer
    router.register_skill("ninguna", ninguna)
    
    if "--reset" in sys.argv:
        pref_path = os.path.join("agent", "preferences.json")
        log_path = "training_log.jsonl"
        for p in [pref_path, log_path, MODEL_PATH]:
            if os.path.exists(p):
                os.remove(p)
        print("Memoria, modelo y logs reseteados")
        if os.path.exists(router.dataset_path):
            print(f"Se conservan tus correcciones en {router.dataset_path} (bórralo a mano si quieres empezar de cero).")
        return
        
    def load_contexts(defaults):
        if "--contexts" in sys.argv:
            import json
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

    # Datos de entrenamiento: frases base (data/base_es.jsonl), MASSIVE adaptado
    # (data/massive_es.jsonl, si existe) y tus correcciones (agent/feedback_data.jsonl).
    # Ver scripts/importar_massive.py y scripts/evaluar.py.
    feedback_examples = router.load_feedback_examples()
    base_examples = training_examples(router.skills, use_massive="--sin-massive" not in sys.argv)
    contexts = load_contexts(base_examples) + feedback_examples

    def train_epochs(epochs: int):
        """Entrena el clasificador de intención de forma supervisada.

        Usa train_batch (no add_feedback) para NO contaminar preferences.json
        con éxitos/fallos simulados que nunca ocurrieron de verdad.
        """
        router.bandit.train_batch(contexts, epochs=epochs)

    # Cargamos el modelo persistido para seguir entrenando sobre lo ya aprendido
    loaded = router.load_model(MODEL_PATH)

    if "--train" in sys.argv:
        train_epochs(50)
        router.save_model(MODEL_PATH)
        print("Entrenamiento ML completado y guardado. El modelo de Intenciones está listo.")
    elif "--status" in sys.argv:
        print("Modelo cargado:", loaded)
        print("Ejemplos de entrenamiento:", len(contexts), f"(de ellos {len(feedback_examples)} tuyos)")
        if os.path.exists(router.pending_path):
            print("Frases pendientes de etiquetar: python scripts/etiquetar_pendientes.py --listar")
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

        def on_feedback(action, reward, ctx):
            # El 👍 refuerza la intención; el 👎 solo registra el fallo.
            router.add_feedback(action, reward, ctx)
            router.save_model(MODEL_PATH)

        try:
            run_gui(router.execute, on_feedback, actions=list(router.skills.keys()))
        finally:
            # Persistimos lo aprendido online durante la sesión (ejecuciones reales)
            router.save_model(MODEL_PATH)
            print("Modelo guardado. Hasta luego.")


if __name__ == "__main__":
    main()
