"""Mide qué tal clasifica el modelo de intención con datos que NO ha visto.

Entrena un modelo nuevo (no toca agent/model.pkl) y lo evalúa sobre:
  - data/eval_es.jsonl   frases escritas a mano, todas las acciones
  - MASSIVE test         solo buscar_web / buscar_youtube / crear_nota / ninguna

Uso:
  python scripts/evaluar.py                 # compara "solo base" vs "base + MASSIVE"
  python scripts/evaluar.py --config massive --detalle
  python scripts/evaluar.py --umbral 0.6

Cómo leer el resultado, con el umbral de confianza del router:
  ACIERTA   ejecuta la acción correcta (o reconoce que no es un comando)
  SE ABSTIENE  no está seguro y pregunta: molesto, pero seguro
  SE EQUIVOCA  ejecuta una acción que no era: lo que hay que minimizar
"""
import os
import sys
import argparse
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from agent.bandit import ContextualBandit  # noqa: E402
from agent.datasets import (BASE_PATH, EVAL_PATH, FEEDBACK_PATH, MASSIVE_PATH,  # noqa: E402
                            filter_examples, load_jsonl, training_examples)
from agent.router import MIN_CONFIDENCE  # noqa: E402

UMBRALES = [0.3, 0.4, 0.5, 0.6, 0.7]


def entrenar(actions, use_massive, use_feedback, epochs):
    bandit = ContextualBandit(list(actions))
    ejemplos = training_examples(actions, FEEDBACK_PATH if use_feedback else None, use_massive)
    bandit.train_batch(ejemplos, epochs=epochs)
    return bandit, len(ejemplos)


def resultado(expected, pred, conf, umbral):
    if conf < umbral:
        # Abstenerse ante algo que no es un comando también es acertar
        return "acierta" if expected == "ninguna" else "abstiene"
    return "acierta" if pred == expected else "equivoca"


def evaluar(bandit, ejemplos, umbral, detalle=False):
    preds = [(e, *bandit.predict(e["q"])) for e in ejemplos]
    n = len(preds)
    top1 = sum(p == e["expected_action"] for e, p, _ in preds) / n
    print(f"    precisión sin umbral: {top1:.0%}")
    for u in UMBRALES:
        c = Counter(resultado(e["expected_action"], p, conf, u) for e, p, conf in preds)
        marca = "  <- umbral actual" if abs(u - umbral) < 1e-9 else ""
        print(f"    umbral {u:.1f}: acierta {c['acierta'] / n:4.0%} · se abstiene {c['abstiene'] / n:4.0%}"
              f" · SE EQUIVOCA {c['equivoca'] / n:4.0%}{marca}")

    if detalle:
        por_accion = {}
        for e, p, conf in preds:
            r = resultado(e["expected_action"], p, conf, umbral)
            por_accion.setdefault(e["expected_action"], Counter())[r] += 1
        print(f"    por acción (umbral {umbral}):")
        for a, c in sorted(por_accion.items()):
            total = sum(c.values())
            print(f"      {a:20} {c['acierta']:3}/{total:<3} aciertos, {c['abstiene']} abstenciones, {c['equivoca']} errores")
        errores = [(e, p, conf) for e, p, conf in preds if resultado(e["expected_action"], p, conf, umbral) == "equivoca"]
        if errores:
            print("    errores:")
            for e, p, conf in errores[:25]:
                print(f"      {e['q']!r:50} esperaba {e['expected_action']:18} -> {p} ({conf:.2f})")


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--config", choices=["base", "massive", "ambos"], default="ambos")
    parser.add_argument("--umbral", type=float, default=MIN_CONFIDENCE)
    parser.add_argument("--epochs", type=int, default=30)
    parser.add_argument("--sin-feedback", action="store_true", help="no usar las correcciones del usuario")
    parser.add_argument("--detalle", action="store_true", help="resultado por acción y lista de errores")
    args = parser.parse_args()

    base = load_jsonl(BASE_PATH)
    actions = sorted({e["expected_action"] for e in base})
    conjuntos = [("eval_es (a mano)", filter_examples(load_jsonl(EVAL_PATH), actions))]
    massive_test = filter_examples(load_jsonl(MASSIVE_PATH), actions, split="test")
    if massive_test:
        conjuntos.append(("MASSIVE test", massive_test))
    elif args.config != "base":
        print("Aviso: no hay data/massive_es.jsonl; ejecuta antes scripts/importar_massive.py\n")

    configs = {"base": [False], "massive": [True], "ambos": [False, True]}[args.config]
    for use_massive in configs:
        bandit, n = entrenar(actions, use_massive, not args.sin_feedback, args.epochs)
        nombre = "base + MASSIVE" if use_massive else "solo base"
        print(f"== Modelo: {nombre} ({n} ejemplos de entrenamiento)")
        for titulo, ejemplos in conjuntos:
            print(f"  -- {titulo}: {len(ejemplos)} frases")
            evaluar(bandit, ejemplos, args.umbral, args.detalle)
        print()


if __name__ == "__main__":
    main()
