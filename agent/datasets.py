"""Carga de los datasets de entrenamiento / evaluación (formato JSONL).

Cada línea es {"q": frase, "expected_action": acción} y, opcionalmente,
"source" y "split" (train/dev/test). Archivos:

  data/base_es.jsonl     frases escritas a mano (entrenamiento)
  data/massive_es.jsonl  MASSIVE de Amazon adaptado (scripts/importar_massive.py)
  data/eval_es.jsonl     frases de evaluación: NUNCA se entrenan con ellas
  agent/feedback_data.jsonl  correcciones del usuario (👍 / "¿Cuál debió ser?")
"""
import os
import json
from typing import Dict, Iterable, List, Optional

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(ROOT, "data")
BASE_PATH = os.path.join(DATA_DIR, "base_es.jsonl")
MASSIVE_PATH = os.path.join(DATA_DIR, "massive_es.jsonl")
EVAL_PATH = os.path.join(DATA_DIR, "eval_es.jsonl")
FEEDBACK_PATH = os.path.join(ROOT, "agent", "feedback_data.jsonl")
PENDING_PATH = os.path.join(ROOT, "agent", "pendientes.jsonl")


def load_jsonl(path: str) -> List[Dict]:
    """Lee un JSONL ignorando líneas vacías o corruptas. [] si no existe."""
    rows: List[Dict] = []
    if not os.path.exists(path):
        return rows
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except ValueError:
                continue
    return rows


def write_jsonl(path: str, rows: Iterable[Dict]):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


def append_jsonl(path: str, row: Dict):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "a", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")


def filter_examples(rows: Iterable[Dict], actions: Iterable[str], split: Optional[str] = None) -> List[Dict]:
    """Solo ejemplos válidos de acciones registradas (y del split pedido, si hay)."""
    actions = set(actions)
    out = []
    for r in rows:
        if not r.get("q") or r.get("expected_action") not in actions:
            continue
        if split and r.get("split", "train") != split:
            continue
        out.append({"q": r["q"], "expected_action": r["expected_action"]})
    return out


def training_examples(actions: Iterable[str], feedback_path: Optional[str] = None,
                      use_massive: bool = True) -> List[Dict]:
    """Dataset de entrenamiento completo: base + MASSIVE (train) + feedback del usuario."""
    actions = list(actions)
    examples = filter_examples(load_jsonl(BASE_PATH), actions)
    if use_massive:
        examples += filter_examples(load_jsonl(MASSIVE_PATH), actions, split="train")
    if feedback_path:
        examples += filter_examples(load_jsonl(feedback_path), actions)
    return examples
