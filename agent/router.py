import os
import time
from typing import Callable, Dict, Any, Optional, List
from .bandit import ContextualBandit
from .datasets import append_jsonl, filter_examples, load_jsonl
from .memory import PreferencesMemory, ConversationalMemory

# Por debajo de esta confianza el clasificador "no sabe": no ejecutamos nada.
# Calibrado con el modelo actual: las frases válidas quedan en 0.6-0.9 y las
# frases fuera de dominio ("hola", "gracias", "que hora es") en 0.1-0.45.
MIN_CONFIDENCE = 0.5

UNCERTAIN_MESSAGE = ("No estoy seguro de qué quieres que haga. "
                     "Dímelo de otra forma o enséñame cuál era la acción.")


class Skill:
    def __init__(self, name: str, func: Callable[[Dict[str, Any]], Dict[str, Any]],
                 confirm: Optional[Callable[[Dict[str, Any]], Optional[str]]] = None):
        self.name = name
        self.func = func
        # confirm(ctx) describe lo que se va a hacer ("Voy a llamar a María...").
        # Si devuelve texto, el router pide confirmación antes de ejecutar;
        # si devuelve None, el skill se ejecuta directamente.
        self.confirm = confirm

    def execute(self, context: Dict[str, Any]) -> Dict[str, Any]:
        return self.func(context)


class SkillRouter:
    def __init__(self, epsilon: float = 0.1, min_confidence: float = MIN_CONFIDENCE,
                 data_dir: Optional[str] = None):
        data_dir = data_dir or os.path.dirname(__file__)
        self.skills: Dict[str, Skill] = {}
        self.bandit = ContextualBandit(epsilon=epsilon)
        self.min_confidence = min_confidence
        self.memory = PreferencesMemory(os.path.join(data_dir, "preferences.json"))
        self.chat_memory = ConversationalMemory(os.path.join(data_dir, "chat_history.json"))
        # Ejemplos (frase -> acción) confirmados por el usuario con 👍 o corrección.
        # Se reutilizan al reentrenar, así no se pierden si el modelo se descarta.
        self.dataset_path = os.path.join(data_dir, "feedback_data.jsonl")
        # Frases dudosas o rechazadas (👎) para etiquetar después con
        # scripts/etiquetar_pendientes.py: son los mejores datos nuevos.
        self.pending_path = os.path.join(data_dir, "pendientes.jsonl")

    def register_skill(self, name: str, func: Callable[[Dict[str, Any]], Dict[str, Any]],
                       confirm: Optional[Callable[[Dict[str, Any]], Optional[str]]] = None):
        if name in self.skills:
            return
        skill = Skill(name, func, confirm)
        self.skills[name] = skill
        self.bandit.add_action(name)

    def choose_action(self, context: Optional[Dict[str, Any]] = None) -> Optional[str]:
        return self.bandit.select(context)

    def execute(self, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        context = context or {}

        # Inyectar la memoria conversacional en el contexto
        context["history"] = self.chat_memory.get_history()

        confirmed = context.get("confirmed_action")
        confidence = None
        if confirmed:
            # El usuario ya confirmó esta acción concreta: no volvemos a predecir.
            if confirmed not in self.skills:
                return {"error": "unknown_action", "action": None,
                        "result": {"success": False, "message": f"No conozco la acción [{confirmed}]."}}
            action = confirmed
        elif context.get("q"):
            action, confidence = self.bandit.predict(context["q"])
            if action is None or confidence < self.min_confidence:
                self._record_pending(context["q"], "dudosa", action, confidence)
                return {
                    "action": None,
                    "uncertain": True,
                    "suggestion": action,
                    "confidence": confidence,
                    "result": {"success": False, "message": UNCERTAIN_MESSAGE},
                }
        else:
            action = self.choose_action(context)

        if action is None:
            return {"error": "no_actions"}

        skill = self.skills[action]

        # Acciones con efectos que no se pueden deshacer (mensajes, llamadas):
        # describimos lo que vamos a hacer y esperamos un "sí" explícito.
        if skill.confirm and not confirmed and not context.get("dry_run"):
            description = skill.confirm(context)
            if description:
                return {
                    "action": action,
                    "needs_confirmation": True,
                    "confidence": confidence,
                    "result": {"success": False, "message": f"{description} ¿Lo confirmas?"},
                }

        result = skill.execute(context)
        success = bool(result.get("success", False))
        reward = 1.0 if success else 0.0

        # Actualizamos bandit y memory. learn=False: la ejecución registra el
        # resultado real (stats + valor MAB) pero NO enseña la intención al
        # clasificador; eso solo ocurre con feedback humano explícito (👍).
        self.bandit.update(action, reward, context, learn=False)
        self.memory.record_outcome(action, success)

        # Actualizamos la memoria conversacional profunda (si no es dry_run de entrenamiento)
        if not context.get("dry_run", False) and "q" in context:
            user_text = context["q"]
            jarvis_msg = result.get("message", f"Ejecutando acción: {action}")
            self.chat_memory.add_message("user", user_text)
            self.chat_memory.add_message("jarvis", jarvis_msg)

        return {
            "action": action,
            "confidence": confidence,
            "result": result,
            "reward": reward,
            "values": dict(self.bandit.values),
            "counts": dict(self.bandit.counts),
            "stats": self.memory.get_stats(),
        }

    def add_feedback(self, action: str, reward: float, context: Optional[Dict[str, Any]] = None):
        self.bandit.update(action, reward, context)
        self.memory.record_outcome(action, reward > 0)
        q = (context or {}).get("q")
        if not q or action not in self.skills:
            return
        if reward > 0:
            self._record_example(q, action)
        else:
            self._record_pending(q, "rechazada", action)

    def _record_example(self, q: str, action: str):
        try:
            append_jsonl(self.dataset_path, {"q": q, "expected_action": action})
        except Exception as e:
            print(f"[Router] Error guardando ejemplo de entrenamiento: {e}")

    def _record_pending(self, q: str, motivo: str, suggestion: Optional[str] = None,
                        confidence: Optional[float] = None):
        row = {"q": q, "motivo": motivo, "sugerencia": suggestion,
               "confianza": None if confidence is None else round(confidence, 3),
               "ts": int(time.time())}
        try:
            append_jsonl(self.pending_path, row)
        except Exception as e:
            print(f"[Router] Error guardando frase pendiente: {e}")

    def load_feedback_examples(self) -> List[Dict[str, str]]:
        """Ejemplos confirmados por el usuario, solo de skills aún registrados."""
        return filter_examples(load_jsonl(self.dataset_path), self.skills)

    def train_intent(self, action: str, context: Optional[Dict[str, Any]] = None):
        """Entrena el clasificador de intención sin registrar estadísticas.

        Para el warm-up / entrenamiento supervisado: no debe contaminar
        preferences.json con éxitos/fallos que nunca ocurrieron.
        """
        self.bandit.train_intent(action, context)

    def save_model(self, path: str):
        self.bandit.save(path)

    def load_model(self, path: str) -> bool:
        return self.bandit.load(path)

    def get_values(self) -> Dict[str, float]:
        return dict(self.bandit.values)

    def get_counts(self) -> Dict[str, int]:
        return dict(self.bandit.counts)

    def get_stats(self) -> Dict[str, Dict[str, int]]:
        return self.memory.get_stats()
