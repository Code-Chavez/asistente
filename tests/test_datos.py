import os
import sys

import pytest

from agent.datasets import filter_examples, load_jsonl, write_jsonl, append_jsonl
from skills.charla import ninguna

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), "scripts"))
from etiquetar_pendientes import cargar_pendientes, interpretar  # noqa: E402
from importar_massive import MAPEO, adaptar  # noqa: E402

ACCIONES = ["buscar_web", "crear_nota", "ninguna"]


# ---- agent/datasets.py ----

def test_jsonl_ida_y_vuelta_ignora_lineas_rotas(tmp_path):
    path = str(tmp_path / "d.jsonl")
    write_jsonl(path, [{"q": "hola", "expected_action": "ninguna"}])
    with open(path, "a", encoding="utf-8") as f:
        f.write("{roto\n\n")
    append_jsonl(path, {"q": "busca gatos", "expected_action": "buscar_web"})
    assert [r["q"] for r in load_jsonl(path)] == ["hola", "busca gatos"]
    assert load_jsonl(str(tmp_path / "no_existe.jsonl")) == []


def test_filter_examples_por_accion_y_split():
    rows = [
        {"q": "a", "expected_action": "buscar_web", "split": "train"},
        {"q": "b", "expected_action": "buscar_web", "split": "test"},
        {"q": "c", "expected_action": "skill_borrado"},
        {"q": "", "expected_action": "buscar_web"},
        {"q": "d", "expected_action": "ninguna"},  # sin split = train
    ]
    assert [r["q"] for r in filter_examples(rows, ACCIONES)] == ["a", "b", "d"]
    assert [r["q"] for r in filter_examples(rows, ACCIONES, split="train")] == ["a", "d"]
    assert [r["q"] for r in filter_examples(rows, ACCIONES, split="test")] == ["b"]


# ---- scripts/importar_massive.py ----

def _fila(intent, utt, partition="train"):
    return {"intent": intent, "utt": utt, "partition": partition}


def test_adaptar_aplica_mapeo_y_descarta_ambiguas():
    rows = [
        _fila("weather_query", "que tiempo hace"),
        _fila("general_greet", "hola que tal"),
        _fila("email_sendemail", "envia un correo a papa"),  # ambigua con WhatsApp
        _fila("intencion_desconocida", "xyz"),
        _fila("play_music", "pon a rosalia", "test"),
    ]
    out = {(e["q"], e["expected_action"], e["split"]) for e in adaptar(rows, max_por_accion=10)}
    assert out == {
        ("que tiempo hace", "buscar_web", "train"),
        ("hola que tal", "ninguna", "train"),
        ("pon a rosalia", "buscar_youtube", "test"),
    }


def test_adaptar_limita_y_reparte_entre_intenciones():
    rows = [_fila("weather_query", f"clima {i}") for i in range(50)]
    rows += [_fila("qa_factoid", f"dato {i}") for i in range(3)]
    out = adaptar(rows, max_por_accion=10)
    assert len(out) == 10
    # El cupo se reparte: la intención pequeña entra entera aunque la otra tenga 50
    assert sum(e["source"] == "massive:qa_factoid" for e in out) == 3


def test_mapeo_nunca_manda_a_acciones_sensibles():
    # MASSIVE no debe enseñar nada sobre WhatsApp/llamadas: esas frases son nuestras
    assert not {"enviar_whatsapp", "llamar_whatsapp", "enviar_nota_voz"} & set(MAPEO.values())


# ---- scripts/etiquetar_pendientes.py ----

@pytest.mark.parametrize("resp, sugerencia, esperado", [
    ("", "buscar_web", ("etiquetar", "buscar_web")),
    ("", None, ("invalida", None)),
    ("2", None, ("etiquetar", "crear_nota")),
    ("99", None, ("invalida", None)),
    ("n", "buscar_web", ("etiquetar", "ninguna")),
    ("crear_nota", None, ("etiquetar", "crear_nota")),
    ("s", None, ("saltar", None)),
    ("b", None, ("borrar", None)),
    ("q", None, ("salir", None)),
    ("?", None, ("ayuda", None)),
    ("algo raro", None, ("invalida", None)),
])
def test_interpretar_respuesta(resp, sugerencia, esperado):
    assert interpretar(resp, sugerencia, ACCIONES) == esperado


def test_cargar_pendientes_sin_duplicados_ni_ya_corregidas(tmp_path):
    pend, fb = str(tmp_path / "p.jsonl"), str(tmp_path / "f.jsonl")
    for q in ["hola jarvis", "Hola  Jarvis", "pon la radio", "anota esto"]:
        append_jsonl(pend, {"q": q, "motivo": "dudosa"})
    append_jsonl(fb, {"q": "anota esto", "expected_action": "crear_nota"})  # corregida en la GUI
    assert [p["q"] for p in cargar_pendientes(pend, fb)] == ["hola jarvis", "pon la radio"]


# ---- skills/charla.py ----

def test_ninguna_responde_sin_ejecutar_nada():
    assert ninguna({"q": "hola jarvis"})["message"].startswith("Hola")
    assert ninguna({"q": "muchas gracias"})["message"] == "A su servicio."
    assert ninguna({"q": "enciende la luz"})["success"] is True
