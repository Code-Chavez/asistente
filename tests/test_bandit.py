import pytest

pytest.importorskip("sklearn")

from agent.bandit import ContextualBandit  # noqa: E402

EJEMPLOS = [
    ("busca en google el clima", "buscar"),
    ("buscame recetas de pizza", "buscar"),
    ("investiga sobre la luna", "buscar"),
    ("abre la calculadora", "abrir"),
    ("abre el bloc de notas", "abrir"),
    ("inicia paint", "abrir"),
]


def entrenar(bandit, epocas=30):
    for _ in range(epocas):
        for q, a in EJEMPLOS:
            bandit.train_intent(a, {"q": q})


def test_predict_sin_entrenar_devuelve_none():
    b = ContextualBandit(["buscar", "abrir"])
    assert b.predict("busca algo") == (None, 0.0)


def test_predict_devuelve_accion_y_confianza():
    b = ContextualBandit(["buscar", "abrir"])
    entrenar(b)
    action, conf = b.predict("abre la calculadora")
    assert action == "abrir"
    assert 0.5 < conf <= 1.0


def test_load_con_las_mismas_acciones_reutiliza_modelo(tmp_path):
    path = str(tmp_path / "model.pkl")
    b = ContextualBandit(["buscar", "abrir"])
    entrenar(b)
    b.save(path)

    nuevo = ContextualBandit(["buscar", "abrir"])
    assert nuevo.load(path) is True
    assert nuevo.predict("abre la calculadora")[0] == "abrir"


def test_load_con_skill_nuevo_descarta_modelo_y_puede_aprenderlo(tmp_path):
    path = str(tmp_path / "model.pkl")
    b = ContextualBandit(["buscar", "abrir"])
    entrenar(b)
    b.save(path)

    nuevo = ContextualBandit(["buscar", "abrir", "llamar"])
    assert nuevo.load(path) is False
    assert nuevo.is_trained is False
    # Antes: partial_fit lanzaba ValueError con la clase nueva y nunca se aprendía
    for _ in range(30):
        for q, a in EJEMPLOS + [("llama a carlos", "llamar"), ("hazle una llamada a maria", "llamar")]:
            nuevo.train_intent(a, {"q": q})
    assert "llamar" in {str(c) for c in nuevo.model.classes_}
    assert nuevo.predict("llama a carlos")[0] == "llamar"


def test_load_con_skill_eliminado_no_lo_reintroduce(tmp_path):
    path = str(tmp_path / "model.pkl")
    b = ContextualBandit(["buscar", "abrir", "viejo"])
    entrenar(b)
    b.update("viejo", 1.0)
    b.save(path)

    nuevo = ContextualBandit(["buscar", "abrir"])
    assert nuevo.load(path) is False
    assert nuevo.actions == ["buscar", "abrir"]
    assert "viejo" not in nuevo.counts


def test_train_batch_aprende_clase_minoritaria_gracias_al_balanceo():
    # 200 frases de "buscar" frente a 3 de "abrir": sin balancear, "abrir" se ahoga
    ejemplos = [{"q": f"busca informacion sobre el tema {i}", "expected_action": "buscar"} for i in range(200)]
    ejemplos += [{"q": q, "expected_action": "abrir"}
                 for q in ["abre la calculadora", "abre el bloc de notas", "abre paint"]]
    b = ContextualBandit(["buscar", "abrir"])
    b.train_batch(ejemplos, epochs=30)
    assert b.is_trained
    assert b.predict("abre la calculadora")[0] == "abrir"
    assert b.predict("busca informacion sobre gatos")[0] == "buscar"


def test_train_batch_ignora_acciones_desconocidas():
    b = ContextualBandit(["buscar", "abrir"])
    b.train_batch([{"q": "x", "expected_action": "otra"}], epochs=1)
    assert b.is_trained is False
