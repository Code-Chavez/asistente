import pytest

from skills.windows import (
    parse_whatsapp_command,
    describir_enviar_whatsapp,
    describir_llamar_whatsapp,
    describir_enviar_nota_voz,
)


@pytest.mark.parametrize("frase, contacto, mensaje", [
    # "por/de whatsapp" ya no se cuela en el contacto
    ("llama a carlos por whatsapp", "Carlos", ""),
    ("manda una nota de voz a maria por whatsapp", "Maria", ""),
    ("llamada de voz a papa por whatsapp", "Papa", ""),
    ("envia un audio de whatsapp a carlos", "Carlos", ""),
    ("mandale un mensaje por whatsapp a carlos", "Carlos", ""),
    ("grabale una nota de voz a mama por WhatsApp", "Mama", ""),
    # contacto + mensaje
    ("whatsapp a mama diciendo llego tarde", "Mama", "Llego tarde"),
    ("envia un whatsapp a maria diciendo que ya voy", "Maria", "Ya voy"),
    ("dile a maria que ya llegue", "Maria", "Ya llegue"),
    ("manda un whatsapp a pedro y dile que me llame", "Pedro", "Me llame"),
    # se usa el conector que aparece PRIMERO, no el primero de la lista
    ("manda a maria que compre pan para la cena", "Maria", "Compre pan para la cena"),
    # sin contacto
    ("abre whatsapp", "", ""),
])
def test_extrae_contacto_y_mensaje(frase, contacto, mensaje):
    assert parse_whatsapp_command(frase) == (contacto, mensaje)


def test_conserva_mayusculas_del_mensaje():
    assert parse_whatsapp_command("whatsapp a Ana diciendo Nos vemos en Lima") == ("Ana", "Nos vemos en Lima")


def test_contacto_maximo_tres_palabras():
    contacto, _ = parse_whatsapp_command("whatsapp a juan carlos perez garcia lopez")
    assert contacto == "Juan Carlos Perez"


def test_correccion_de_nombres_por_palabra_completa():
    assert parse_whatsapp_command("llama a christopher")[0] == "Cristofer"
    assert parse_whatsapp_command("llama a jon")[0] == "John"
    # antes el reemplazo por subcadena convertía "Jonathan" en "Johnathan"
    assert parse_whatsapp_command("llama a jonathan")[0] == "Jonathan"


def test_confirmacion_whatsapp_muestra_contacto_y_mensaje():
    texto = describir_enviar_whatsapp({"q": "whatsapp a mama diciendo llego tarde"})
    assert "«Mama»" in texto and "«Llego tarde»" in texto


@pytest.mark.parametrize("frase", ["abre whatsapp", "manda un whatsapp a carlos"])
def test_whatsapp_sin_envio_no_pide_confirmacion(frase):
    # Solo abrir la app, o falta el mensaje (el skill lo pedirá): nada que confirmar
    assert describir_enviar_whatsapp({"q": frase}) is None


def test_confirmacion_llamada_y_nota_de_voz():
    assert describir_llamar_whatsapp({"q": "llama a carlos por whatsapp"}) == "Voy a llamar a «Carlos» por WhatsApp."
    assert describir_llamar_whatsapp({"q": "llama por whatsapp"}) is None
    texto = describir_enviar_nota_voz({"q": "nota de voz de 10 segundos a luis"})
    assert "«Luis»" in texto and "10 s" in texto


def test_skills_no_envian_sin_datos_completos():
    from skills.windows import enviar_whatsapp, enviar_nota_voz, PYAUTOGUI_AVAILABLE
    if not PYAUTOGUI_AVAILABLE:
        pytest.skip("pyautogui no disponible")
    # Contacto sin mensaje: antes enviaba "mensaje automatizado enviado por Jarvis"
    r = enviar_whatsapp({"q": "manda un whatsapp a carlos"})
    assert r["success"] is False and "Qué le digo" in r["message"]
    # Nota de voz sin contacto: antes grababa en el chat que estuviera abierto
    r = enviar_nota_voz({"q": "graba una nota de voz"})
    assert r["success"] is False and "A quién" in r["message"]
