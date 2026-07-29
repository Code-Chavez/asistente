from typing import Callable, Dict, Any, Optional
from .bandit import ContextualBandit
from .memory import PreferencesMemory, ConversationalMemory


class Skill:
    def __init__(self, name: str, func: Callable[[Dict[str, Any]], Dict[str, Any]]):
        self.name = name
        self.func = func

    def execute(self, context: Dict[str, Any]) -> Dict[str, Any]:
        return self.func(context)


class SkillRouter:
    def __init__(self, epsilon: float = 0.1):
        self.skills: Dict[str, Skill] = {}
        self.bandit = ContextualBandit(epsilon=epsilon)
        self.memory = PreferencesMemory()
        self.chat_memory = ConversationalMemory()

    def register_skill(self, name: str, func: Callable[[Dict[str, Any]], Dict[str, Any]]):
        if name in self.skills:
            return
        skill = Skill(name, func)
        self.skills[name] = skill
        self.bandit.add_action(name)

    def choose_action(self, context: Optional[Dict[str, Any]] = None) -> Optional[str]:
        return self.bandit.select(context)

    def execute(self, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        context = context or {}
        
        # Inyectar la memoria conversacional en el contexto
        context["history"] = self.chat_memory.get_history()
        
        action = self.choose_action(context)
        if action is None:
            return {"error": "no_actions"}
            
        skill = self.skills[action]
        result = skill.execute(context)
        success = bool(result.get("success", False))
        reward = 1.0 if success else 0.0
        
        # Actualizamos bandit y memory
        self.bandit.update(action, reward, context)
        self.memory.record_outcome(action, success)
        
        # Actualizamos la memoria conversacional profunda (si no es dry_run de entrenamiento)
        if not context.get("dry_run", False) and "q" in context:
            user_text = context["q"]
            jarvis_msg = result.get("message", f"Ejecutando acción: {action}")
            self.chat_memory.add_message("user", user_text)
            self.chat_memory.add_message("jarvis", jarvis_msg)
            
        return {
            "action": action,
            "result": result,
            "reward": reward,
            "values": dict(self.bandit.values),
            "counts": dict(self.bandit.counts),
            "stats": self.memory.get_stats(),
        }

    def add_feedback(self, action: str, reward: float, context: Optional[Dict[str, Any]] = None):
        self.bandit.update(action, reward, context)
        self.memory.record_outcome(action, reward > 0)

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

