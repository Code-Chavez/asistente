import os
import random
import pickle
import numpy as np
from collections import Counter
from typing import Optional, Dict, List, Any, Tuple
try:
    from sklearn.feature_extraction.text import HashingVectorizer
    from sklearn.linear_model import SGDClassifier
    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False

MAX_SAMPLE_WEIGHT = 10.0


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
            self.is_trained = False

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

    def predict(self, text: str) -> Tuple[Optional[str], float]:
        """Devuelve (acción, confianza) según el clasificador de intención.

        (None, 0.0) si el modelo no está entrenado o falla. La confianza es la
        probabilidad de la clase ganadora: el router la usa para NO ejecutar
        nada cuando el modelo no está seguro.
        """
        if not (SKLEARN_AVAILABLE and self.is_trained and text):
            return None, 0.0
        try:
            X = self.vectorizer.transform([text])
            probs = self.model.predict_proba(X)[0]
            i = int(np.argmax(probs))
            action = str(self.model.classes_[i])
            if action not in self.actions:
                return None, 0.0
            return action, float(probs[i])
        except Exception as e:
            print(f"[Bandit] Error in prediction: {e}")
            return None, 0.0

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

    def train_batch(self, examples: List[Dict[str, str]], epochs: int = 30,
                    balanced: bool = True, seed: int = 0):
        """Entrena el clasificador con muchos ejemplos {"q", "expected_action"} a la vez.

        Mucho más rápido que train_intent frase a frase. Con balanced=True cada
        clase pesa lo mismo en total: si no, buscar_web/ninguna (cientos de
        frases de MASSIVE) aplastarían a acciones con 4-5 ejemplos.
        """
        if not SKLEARN_AVAILABLE:
            return
        pares = [(e["q"], e["expected_action"]) for e in examples
                 if e.get("q") and e.get("expected_action") in self.actions]
        if not pares:
            return
        X = self.vectorizer.transform([q for q, _ in pares])
        y = np.array([a for _, a in pares])
        pesos = np.ones(len(y))
        if balanced:
            conteo = Counter(y.tolist())
            # Peso inverso a la frecuencia, acotado: pesos enormes desestabilizan el SGD
            pesos = np.array([min(len(y) / (len(conteo) * conteo[a]), MAX_SAMPLE_WEIGHT) for a in y])
        rng = np.random.RandomState(seed)
        for _ in range(epochs):
            idx = rng.permutation(len(y))
            try:
                if not self.is_trained:
                    self.model.partial_fit(X[idx], y[idx], classes=self.actions, sample_weight=pesos[idx])
                    self.is_trained = True
                else:
                    self.model.partial_fit(X[idx], y[idx], sample_weight=pesos[idx])
            except Exception as e:
                print(f"[Bandit] Error training model: {e}")
                return

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

        # Solo traemos stats de acciones que siguen registradas: si un skill se
        # eliminó, no debe volver a colarse en las acciones posibles.
        for a in self.actions:
            if a in state.get("counts", {}):
                self.counts[a] = state["counts"][a]
            if a in state.get("values", {}):
                self.values[a] = state["values"][a]

        model = state.get("model")
        if not (state.get("is_trained") and model is not None):
            return False
        # SGDClassifier fija sus clases en el primer partial_fit. Si desde que se
        # guardó se añadió o quitó algún skill, el modelo ya no puede aprender las
        # clases nuevas (partial_fit lanzaría ValueError): lo descartamos para
        # que se reentrene desde cero con el conjunto actual de acciones.
        saved_classes = {str(c) for c in getattr(model, "classes_", [])}
        if saved_classes != set(self.actions):
            nuevas = sorted(set(self.actions) - saved_classes)
            quitadas = sorted(saved_classes - set(self.actions))
            print(f"[Bandit] Las acciones cambiaron (nuevas={nuevas}, quitadas={quitadas}); "
                  "se reentrenará el modelo desde cero.")
            return False
        self.model = model
        self.is_trained = True
        return True
