import pytest

from skills.windows import (
    abrir_aplicacion,
    control_volumen,
    bloquear_pantalla,
    minimizar_ventanas,
    PYAUTOGUI_AVAILABLE,
)
from skills.vision import capturar_pantalla, describir_pantalla, MSS_AVAILABLE


# ---- skills/windows.py ----

@pytest.mark.parametrize("frase, app", [
    ("abre la calculadora", "calc"),
    ("abre el explorador de archivos", "explorer"),
    ("abre una terminal", "cmd"),
    ("abre el bloc de notas", "notepad"),
    ("abre paint", "mspaint"),
    ("abre spotify", "spotify"),
    ("abre chrome por favor", "chrome"),
    ("no reconozco esta app rara", "notepad"),  # sin match: fallback inofensivo
])
def test_abrir_aplicacion_resuelve_el_ejecutable(frase, app):
    r = abrir_aplicacion({"q": frase, "dry_run": True})
    assert r["success"] is True
    assert r["data"]["app"] == app


def test_abrir_aplicacion_respeta_app_explicita_del_contexto():
    r = abrir_aplicacion({"q": "abre la calculadora", "app": "winword", "dry_run": True})
    assert r["data"]["app"] == "winword"


@pytest.mark.parametrize("frase, accion", [
    ("sube el volumen", "subir"),
    ("baja un poco el volumen", "bajar"),
    ("silencia el sonido", "silenciar"),
    ("ponlo mas alto", "subir"),
])
def test_control_volumen_interpreta_la_orden(frase, accion):
    r = control_volumen({"q": frase, "dry_run": True})
    assert r["success"] is True
    assert r["data"]["accion"] == accion


def test_control_volumen_sin_orden_clara_pregunta():
    r = control_volumen({"q": "haz algo con el audio"})
    assert r["success"] is False
    assert "Subo, bajo o silencio" in r["message"]


def test_bloquear_pantalla_dry_run_no_bloquea_de_verdad():
    assert bloquear_pantalla({"q": "bloquea la pantalla", "dry_run": True}) == {"success": True}


def test_minimizar_ventanas_dry_run_no_requiere_pyautogui():
    assert minimizar_ventanas({"q": "minimiza todo", "dry_run": True}) == {"success": True}


def test_minimizar_ventanas_sin_pyautogui_falla_con_mensaje_claro(monkeypatch):
    monkeypatch.setattr("skills.windows.PYAUTOGUI_AVAILABLE", False)
    r = minimizar_ventanas({"q": "minimiza todo"})
    assert r["success"] is False and "pyautogui" in r["message"]


@pytest.mark.skipif(not PYAUTOGUI_AVAILABLE, reason="pyautogui no disponible")
def test_control_volumen_real_pulsa_la_tecla(monkeypatch):
    teclas = []
    monkeypatch.setattr("skills.windows.pyautogui.press", lambda t: teclas.append(t))
    r = control_volumen({"q": "silencia el sonido"})
    assert r["success"] is True
    assert teclas == ["volumemute"]


@pytest.mark.skipif(not PYAUTOGUI_AVAILABLE, reason="pyautogui no disponible")
def test_minimizar_ventanas_real_usa_win_d(monkeypatch):
    combinaciones = []
    monkeypatch.setattr("skills.windows.pyautogui.hotkey", lambda *k: combinaciones.append(k))
    r = minimizar_ventanas({"q": "minimiza todo"})
    assert r["success"] is True
    assert combinaciones == [("win", "d")]


def test_bloquear_pantalla_real_llama_a_lockworkstation(monkeypatch):
    llamadas = []

    class FakeUser32:
        def LockWorkStation(self):
            llamadas.append(True)

    class FakeWindll:
        user32 = FakeUser32()

    import ctypes
    monkeypatch.setattr(ctypes, "windll", FakeWindll(), raising=False)
    r = bloquear_pantalla({"q": "bloquea la pantalla"})
    assert r["success"] is True
    assert llamadas == [True]


# ---- skills/vision.py ----

def test_capturar_pantalla_dry_run_no_requiere_mss():
    r = capturar_pantalla({"q": "toma una captura", "dry_run": True})
    assert "success" in r and r["data"]["status"] == "mocked_training"


def test_describir_pantalla_dry_run_no_requiere_mss():
    r = describir_pantalla({"q": "que ves", "dry_run": True})
    assert "success" in r and r["data"]["status"] == "mocked_training"


def test_capturar_pantalla_no_describe_nada():
    # A diferencia de describir_pantalla, no debe incluir un "análisis"
    r = capturar_pantalla({"q": "toma una captura", "dry_run": True})
    assert "analysis" not in r.get("data", {})


def _requiere_pantalla_real():
    """mss puede importarse sin problema y aun así no haber pantalla que capturar
    (p.ej. el runner de Linux del CI, sin servidor X): se salta en ese caso."""
    if not MSS_AVAILABLE:
        pytest.skip("mss no disponible")
    try:
        import mss
        with mss.mss():
            pass
    except Exception as e:
        pytest.skip(f"sin pantalla real que capturar: {e}")


def test_capturar_pantalla_real_guarda_un_png(tmp_path, monkeypatch):
    _requiere_pantalla_real()
    import skills.vision as vision
    monkeypatch.setattr(vision, "_notes_dir", lambda: str(tmp_path))
    r = capturar_pantalla({"q": "toma una captura"})
    assert r["success"] is True
    assert r["data"]["image_path"].endswith("captura_pantalla.png")
    assert "analysis" not in r["data"]


def test_describir_pantalla_real_incluye_analisis(tmp_path, monkeypatch):
    _requiere_pantalla_real()
    import skills.vision as vision
    monkeypatch.setattr(vision, "_notes_dir", lambda: str(tmp_path))
    r = describir_pantalla({"q": "que ves"})
    assert r["success"] is True
    assert r["data"]["image_path"].endswith("vision_capture.png")
    assert r["data"]["analysis"]


def test_describir_pantalla_menciona_la_platica_anterior_si_hay_historial():
    _requiere_pantalla_real()
    r = describir_pantalla({"q": "que ves", "history": [{"role": "user"}, {"role": "jarvis"}]})
    assert "plática anterior" in r["message"]
