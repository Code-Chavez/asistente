import os
import random
import pickle
import numpy as np
from typing import Optional, Dict, List, Any
try:
    from sklearn.feature_extraction.text import HashingVectorizer
    from sklearn.linear_model import SGDClassifier
    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False


class ContextualBandit:
    def __init__(self, actions: Optional[List[str]] = None, epsilon: float = 0.1):
        self.epsilon = epsilon
        self.actions = actions or []
        self.counts: Dict[str, int] = {a: 0 for a in self.actions}
        self.values: Dict[str, float] = {a: 0.0 for a in self.actions}

        if SKLEARN_AVAILABLE:
            # Usamos HashingVectorizer para permitir el aprendizaje Online
            # (El TfidfVectorizer anterior se bloqueaba con el vocabulario de la 1era frase).
            # Es stateless: no necesita persistirse, solo el modelo SGD.
            self.vectorizer = HashingVectorizer(n_features=5000, analyzer='char_wb', ngram_range=(3, 5))
            self.model = SGDClassifier(loss='log_loss', learning_rate='optimal')
            self.is_trained = False
        else:
            self.model = None

    def add_action(self, action: str):
        if action not in self.actions:
            self.actions.append(action)
            self.counts[action] = 0
            self.values[action] = 0.0

    def select(self, context: Dict[str, Any] = None) -> Optional[str]:
        if not self.actions:
            return None

        context = context or {}
        # Solo exploramos durante el entrenamiento simulado (dry_run).
        # En ejecución real NUNCA disparamos una acción al azar: sería
        # ejecutar un skill distinto al que el usuario pidió (mandar un
        # WhatsApp, abrir apps, etc.) 1 de cada 10 veces.
        if context.get("dry_run") and random.random() < self.epsilon:
            return random.choice(self.actions)

        # Exploitation: usamos el clasificador de intención si está entrenado
        if SKLEARN_AVAILABLE and self.is_trained and 'q' in context:
            text = context.get('q', '')
            try:
                X = self.vectorizer.transform([text])
                pred = self.model.predict(X)[0]
                if pred in self.actions:
                    return pred
            except Exception as e:
                print(f"[Bandit] Error in prediction: {e}")

        # Fallback: mejor acción por valor promedio si el modelo no está listo o falla
        return max(self.actions, key=lambda a: self.values[a])

    def train_intent(self, action: str, context: Dict[str, Any] = None):
        """Entrena SOLO el clasificador de intención (texto -> acción).

        Se usa para el warm-up y el aprendizaje online sin tocar las
        estadísticas de éxito/fallo (esas reflejan ejecuciones reales).
        """
        if not (SKLEARN_AVAILABLE and context and 'q' in context):
            return
        if action not in self.actions:
            return
        text = context.get('q', '')
        try:
            X = self.vectorizer.transform([text])
            if not self.is_trained:
                # Primera vez: inicializamos las clases con todas las acciones conocidas
                self.model.partial_fit(X, [action], classes=self.actions)
                self.is_trained = True
            else:
                self.model.partial_fit(X, [action])
        except Exception as e:
            print(f"[Bandit] Error training model: {e}")

    def update(self, action: str, reward: float, context: Dict[str, Any] = None, learn: bool = True):
        if action not in self.actions:
            return

        # Actualizamos las estadísticas clásicas de multi-armed bandit
        self.counts[action] += 1
        n = self.counts[action]
        self.values[action] += (reward - self.values[action]) / n

        # Aprendizaje online del clasificador de intención: SOLO cuando hay una
        # señal explícita de que la intención fue correcta (learn=True y reward>0).
        # OJO: que un skill se ejecute sin error (success=True) no significa que
        # la intención fuese la correcta, por eso la ejecución real pasa learn=False.
        if learn and reward > 0:
            self.train_intent(action, context)

    def save(self, path: str):
        """Persiste el estado aprendido (modelo SGD + stats MAB) a disco."""
        if not SKLEARN_AVAILABLE:
            return
        state = {
            "actions": self.actions,
            "counts": self.counts,
            "values": self.values,
            "is_trained": self.is_trained,
            "model": self.model if self.is_trained else None,
        }
        try:
            with open(path, "wb") as f:
                pickle.dump(state, f)
        except Exception as e:
            print(f"[Bandit] Error saving model: {e}")

    def load(self, path: str) -> bool:
        """Carga un estado previo si existe. Devuelve True si cargó el modelo entrenado."""
        if not SKLEARN_AVAILABLE or not os.path.exists(path):
            return False
        try:
            with open(path, "rb") as f:
                state = pickle.load(f)
        except Exception as e:
            print(f"[Bandit] Error loading model: {e}")
            return False

        # Fusionamos: conservamos las acciones registradas por el router y
        # traemos las stats/modelo persistidos.
        for a in state.get("actions", []):
            self.add_action(a)
        self.counts.update(state.get("counts", {}))
        self.values.update(state.get("values", {}))
        if state.get("is_trained") and state.get("model") is not None:
            self.model = state["model"]
            self.is_trained = True
            return True
        return False
