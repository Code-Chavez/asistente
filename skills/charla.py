from typing import Dict, Any

SALUDOS = ("hola", "buenas", "buenos dias", "buenos días", "hey", "que tal", "qué tal")
GRACIAS = ("gracias", "te lo agradezco")


def ninguna(ctx: Dict[str, Any]) -> Dict[str, Any]:
    """La frase no es un comando: respondemos sin ejecutar nada."""
    q = ctx.get("q", "").lower().strip()
    if q.startswith(SALUDOS):
        msg = "Hola, señor. ¿En qué le ayudo?"
    elif any(g in q for g in GRACIAS):
        msg = "A su servicio."
    else:
        msg = "Eso todavía no sé hacerlo. Si era un comando, enséñame cuál con 👎."
    return {"success": True, "message": msg}
