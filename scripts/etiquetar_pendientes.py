"""Etiqueta las frases que Jarvis no entendió (o que marcaste con 👎).

El router las va guardando en agent/pendientes.jsonl. Aquí decides qué acción
era cada una; las etiquetadas pasan a agent/feedback_data.jsonl y se usan en
el siguiente entrenamiento (al arrancar demo.py o con --train).

Uso:
  python scripts/etiquetar_pendientes.py            # modo interactivo
  python scripts/etiquetar_pendientes.py --listar   # solo muestra las pendientes

Respuestas en cada frase:
  Enter     aceptar la sugerencia del modelo (si la hay)
  número    elegir esa acción de la lista
  n         no era un comando (acción "ninguna")
  s         saltar (se queda pendiente para otro día)
  b         borrar sin etiquetar (ruido, frase mal transcrita...)
  ?         volver a mostrar la lista de acciones
  q         guardar y salir
"""
import os
import sys
import argparse
from typing import Dict, List, Optional, Tuple

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from agent.datasets import (BASE_PATH, FEEDBACK_PATH, PENDING_PATH, append_jsonl,  # noqa: E402
                            load_jsonl, write_jsonl)


def _norm(q: str) -> str:
    return " ".join(q.lower().split())


def cargar_pendientes(pending_path: str, feedback_path: str) -> List[Dict]:
    """Pendientes sin duplicados y sin las que ya corregiste desde la GUI."""
    ya_etiquetadas = {_norm(r.get("q", "")) for r in load_jsonl(feedback_path)}
    vistas = set()
    out = []
    for r in load_jsonl(pending_path):
        clave = _norm(r.get("q", ""))
        if not clave or clave in ya_etiquetadas or clave in vistas:
            continue
        vistas.add(clave)
        out.append(r)
    return out


def interpretar(respuesta: str, sugerencia: Optional[str], acciones: List[str]) -> Tuple[str, Optional[str]]:
    """Traduce lo que escribe el usuario a (orden, acción)."""
    r = respuesta.strip().lower()
    if r == "":
        return ("etiquetar", sugerencia) if sugerencia in acciones else ("invalida", None)
    if r == "n":
        return ("etiquetar", "ninguna") if "ninguna" in acciones else ("invalida", None)
    if r in ("s", "b", "q", "?"):
        return {"s": "saltar", "b": "borrar", "q": "salir", "?": "ayuda"}[r], None
    if r.isdigit() and 1 <= int(r) <= len(acciones):
        return "etiquetar", acciones[int(r) - 1]
    if r in acciones:
        return "etiquetar", r
    return "invalida", None


def mostrar_acciones(acciones: List[str]):
    for i, a in enumerate(acciones, 1):
        print(f"  {i:2}. {a}")


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--listar", action="store_true", help="solo lista las frases pendientes")
    args = parser.parse_args()

    pendientes = cargar_pendientes(PENDING_PATH, FEEDBACK_PATH)
    if not pendientes:
        print("No hay frases pendientes. ¡Todo etiquetado!")
        write_jsonl(PENDING_PATH, [])
        return
    if args.listar:
        for p in pendientes:
            if p.get("motivo") == "rechazada":
                info = f"rechazaste: {p.get('sugerencia')}"
            elif p.get("sugerencia"):
                info = f"sugerencia: {p['sugerencia']} ({p.get('confianza')})"
            else:
                info = ""
            print(f"[{p.get('motivo', '?'):9}] {p['q']!r:55} {info}")
        print(f"\n{len(pendientes)} pendientes.")
        return

    acciones = sorted({r["expected_action"] for r in load_jsonl(BASE_PATH)})
    print(f"{len(pendientes)} frases pendientes. Acciones:")
    mostrar_acciones(acciones)
    print("(Enter = aceptar sugerencia · número = acción · n = ninguna · s = saltar · b = borrar · q = salir)\n")

    quedan: List[Dict] = []
    etiquetadas = 0
    for i, p in enumerate(pendientes):
        sug = p.get("sugerencia")
        extra = f" [rechazaste {sug} con 👎]" if p.get("motivo") == "rechazada" else ""
        pista = f" [Enter = {sug}]" if sug in acciones and p.get("motivo") != "rechazada" else ""
        while True:
            try:
                resp = input(f"({i + 1}/{len(pendientes)}) «{p['q']}»{extra}{pista} > ")
            except EOFError:
                resp = "q"
            # Una frase rechazada con 👎 NO debe aceptar la sugerencia con Enter
            orden, accion = interpretar(resp, None if p.get("motivo") == "rechazada" else sug, acciones)
            if orden == "ayuda":
                mostrar_acciones(acciones)
                continue
            if orden == "invalida":
                print("  No entendí. Escribe un número, n, s, b, ? o q.")
                continue
            break
        if orden == "salir":
            quedan.extend(pendientes[i:])
            break
        if orden == "saltar":
            quedan.append(p)
        elif orden == "etiquetar":
            append_jsonl(FEEDBACK_PATH, {"q": p["q"], "expected_action": accion, "source": "pendientes"})
            etiquetadas += 1
            print(f"  ✓ {accion}")
        # "borrar": simplemente no se conserva

    write_jsonl(PENDING_PATH, quedan)
    print(f"\n{etiquetadas} frases etiquetadas; quedan {len(quedan)} pendientes.")
    if etiquetadas:
        print("Se usarán en el próximo entrenamiento (al arrancar demo.py o con: python demo.py --train).")


if __name__ == "__main__":
    main()
