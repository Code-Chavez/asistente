import json

import pytest

from agent.router import SkillRouter, UNCERTAIN_MESSAGE


class SkillFalso:
    def __init__(self):
        self.llamadas = []

    def __call__(self, ctx):
        self.llamadas.append(ctx)
        return {"success": True, "message": "hecho"}


@pytest.fixture
def router(tmp_path):
    r = SkillRouter(data_dir=str(tmp_path))
    r.buscar = SkillFalso()
    r.enviar = SkillFalso()
    r.register_skill("buscar", r.buscar)
    r.register_skill("enviar", r.enviar,
                     confirm=lambda ctx: "Voy a enviar." if "a maria" in ctx["q"] else None)
    return r


def predice(router, action, confidence):
    router.bandit.predict = lambda text: (action, confidence)


def test_baja_confianza_no_ejecuta_nada(router):
    predice(router, "enviar", 0.29)
    resp = router.execute({"q": "hola jarvis"})
    assert resp["uncertain"] is True
    assert resp["action"] is None
    assert resp["suggestion"] == "enviar"
    assert resp["result"]["message"] == UNCERTAIN_MESSAGE
    assert router.enviar.llamadas == []


def test_modelo_sin_entrenar_no_ejecuta_nada(router):
    # Antes caía al "mejor valor" del bandit y ejecutaba una acción cualquiera
    resp = router.execute({"q": "busca el clima"})
    assert resp["uncertain"] is True
    assert router.buscar.llamadas == [] and router.enviar.llamadas == []


def test_confianza_alta_ejecuta_skill_normal(router):
    predice(router, "buscar", 0.9)
    resp = router.execute({"q": "busca el clima"})
    assert resp["action"] == "buscar"
    assert resp["confidence"] == 0.9
    assert len(router.buscar.llamadas) == 1


def test_skill_sensible_pide_confirmacion_antes_de_ejecutar(router):
    predice(router, "enviar", 0.95)
    resp = router.execute({"q": "whatsapp a maria diciendo hola"})
    assert resp["needs_confirmation"] is True
    assert resp["action"] == "enviar"
    assert resp["result"]["message"] == "Voy a enviar. ¿Lo confirmas?"
    assert router.enviar.llamadas == []

    # El usuario dice que sí: se ejecuta la acción confirmada sin volver a predecir
    predice(router, "buscar", 0.99)
    resp = router.execute({"q": "whatsapp a maria diciendo hola", "confirmed_action": "enviar"})
    assert resp["action"] == "enviar"
    assert len(router.enviar.llamadas) == 1
    assert router.buscar.llamadas == []


def test_skill_sensible_sin_nada_que_confirmar_se_ejecuta(router):
    predice(router, "enviar", 0.95)
    resp = router.execute({"q": "abre whatsapp"})
    assert "needs_confirmation" not in resp
    assert len(router.enviar.llamadas) == 1


def test_accion_confirmada_desconocida_no_ejecuta(router):
    resp = router.execute({"q": "x", "confirmed_action": "borrar_todo"})
    assert resp["error"] == "unknown_action"
    assert router.buscar.llamadas == [] and router.enviar.llamadas == []


def test_feedback_positivo_se_guarda_como_ejemplo(router):
    router.add_feedback("buscar", 1.0, {"q": "que tiempo hace"})
    router.add_feedback("enviar", 0.0, {"q": "hola jarvis"})  # 👎: no es un ejemplo válido
    assert router.load_feedback_examples() == [{"q": "que tiempo hace", "expected_action": "buscar"}]


def test_ejemplos_de_skills_eliminados_se_ignoran(router):
    with open(router.dataset_path, "a", encoding="utf-8") as f:
        f.write(json.dumps({"q": "algo viejo", "expected_action": "skill_borrado"}) + "\n")
        f.write("linea rota\n")
        f.write(json.dumps({"q": "busca gatos", "expected_action": "buscar"}) + "\n")
    assert router.load_feedback_examples() == [{"q": "busca gatos", "expected_action": "buscar"}]


def test_frase_dudosa_queda_pendiente_de_etiquetar(router):
    from agent.datasets import load_jsonl
    predice(router, "enviar", 0.29)
    router.execute({"q": "hola jarvis"})
    [p] = load_jsonl(router.pending_path)
    assert p["q"] == "hola jarvis"
    assert p["motivo"] == "dudosa"
    assert p["sugerencia"] == "enviar" and p["confianza"] == 0.29


def test_frase_rechazada_queda_pendiente_y_no_como_ejemplo(router):
    from agent.datasets import load_jsonl
    router.add_feedback("enviar", 0.0, {"q": "pon la radio"})
    [p] = load_jsonl(router.pending_path)
    assert p["motivo"] == "rechazada" and p["sugerencia"] == "enviar"
    assert router.load_feedback_examples() == []


def test_frase_ejecutada_con_confianza_no_queda_pendiente(router):
    import os
    predice(router, "buscar", 0.9)
    router.execute({"q": "busca el clima"})
    assert not os.path.exists(router.pending_path)
