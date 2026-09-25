"""Descarga MASSIVE (Amazon) en español y lo adapta a las acciones de Jarvis.

MASSIVE: ~16.500 frases en es-ES etiquetadas con 60 intenciones.
Licencia CC BY 4.0 — https://github.com/alexa/massive
  FitzGerald et al. (2022), "MASSIVE: A 1M-Example Multilingual Natural
  Language Understanding Dataset with 51 Typologically-Diverse Languages".

Uso:
  python scripts/importar_massive.py              # genera data/massive_es.jsonl
  python scripts/importar_massive.py --max 300    # tope de frases por acción y split

La primera vez descarga el paquete oficial (~40 MB) y guarda solo es-ES en
data/raw/ (ignorado por git); después reutiliza esa copia.
"""
import os
import sys
import random
import tarfile
import argparse
import urllib.request
from collections import Counter, defaultdict

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from agent.datasets import DATA_DIR, MASSIVE_PATH, load_jsonl, write_jsonl  # noqa: E402

URL = "https://amazon-massive-nlu-dataset.s3.amazonaws.com/amazon-massive-dataset-1.1.tar.gz"
LOCALE = "es-ES"
RAW_PATH = os.path.join(DATA_DIR, "raw", f"massive-{LOCALE}.jsonl")

# Intención de MASSIVE -> acción de Jarvis.
#   None  = se descarta (demasiado parecida a un skill nuestro, confundiría).
#   Las que no aparecen aquí también se descartan.
MAPEO = {
    # Preguntas que se resuelven buscando en Google
    "weather_query": "buscar_web",
    "qa_factoid": "buscar_web",
    "qa_definition": "buscar_web",
    "qa_currency": "buscar_web",
    "qa_stock": "buscar_web",
    "qa_maths": "buscar_web",
    "news_query": "buscar_web",
    "cooking_recipe": "buscar_web",
    "recommendation_locations": "buscar_web",
    "recommendation_events": "buscar_web",
    "recommendation_movies": "buscar_web",
    "transport_traffic": "buscar_web",
    "transport_query": "buscar_web",
    # Poner música / contenido -> YouTube
    "play_music": "buscar_youtube",
    "play_podcasts": "buscar_youtube",
    # Listas -> notas
    "lists_createoradd": "crear_nota",
    # Cosas que Jarvis NO hace: ejemplos negativos para la clase "ninguna"
    "general_greet": "ninguna",
    "general_joke": "ninguna",
    "general_quirky": "ninguna",
    "datetime_query": "ninguna",
    "datetime_convert": "ninguna",
    "alarm_set": "ninguna",
    "alarm_query": "ninguna",
    "alarm_remove": "ninguna",
    "iot_cleaning": "ninguna",
    "iot_coffee": "ninguna",
    "iot_hue_lightchange": "ninguna",
    "iot_hue_lightdim": "ninguna",
    "iot_hue_lightoff": "ninguna",
    "iot_hue_lighton": "ninguna",
    "iot_hue_lightup": "ninguna",
    "iot_wemo_off": "ninguna",
    "iot_wemo_on": "ninguna",
    "takeaway_order": "ninguna",
    "takeaway_query": "ninguna",
    "transport_taxi": "ninguna",
    "transport_ticket": "ninguna",
    "play_game": "ninguna",
    "lists_query": "ninguna",
    "lists_remove": "ninguna",
    "calendar_query": "ninguna",
    "calendar_remove": "ninguna",
    "music_likeness": "ninguna",
    "music_dislikeness": "ninguna",
    "music_settings": "ninguna",
    "audio_volume_other": "ninguna",  # "cambia el volumen a 35%": no soportamos un nivel exacto
    "email_query": "ninguna",
    "email_querycontact": "ninguna",
    "email_addcontact": "ninguna",
    # Subir/bajar/silenciar volumen -> nuestro control_volumen
    "audio_volume_up": "control_volumen",
    "audio_volume_down": "control_volumen",
    "audio_volume_mute": "control_volumen",

    # Ambiguas con nuestros skills (enviar mensajes, poner audio, recordatorios)
    "email_sendemail": None,
    "social_post": None,
    "social_query": None,
    "play_radio": None,
    "play_audiobook": None,
    "music_query": None,
    "calendar_set": None,
    "cooking_query": None,
}

SPLITS = {"train": "train", "dev": "dev", "test": "test"}


def descargar(force: bool = False) -> str:
    """Extrae solo es-ES del paquete oficial, en streaming (no guarda el .tar.gz)."""
    if os.path.exists(RAW_PATH) and not force:
        return RAW_PATH
    os.makedirs(os.path.dirname(RAW_PATH), exist_ok=True)
    print(f"Descargando MASSIVE (~40 MB) desde {URL} ...")
    with urllib.request.urlopen(URL) as resp, tarfile.open(fileobj=resp, mode="r|gz") as tar:
        for member in tar:
            if member.name.endswith(f"/{LOCALE}.jsonl"):
                with open(RAW_PATH, "wb") as out:
                    out.write(tar.extractfile(member).read())
                print(f"Guardado {RAW_PATH}")
                return RAW_PATH
    raise RuntimeError(f"No se encontró {LOCALE}.jsonl dentro del paquete")


def adaptar(rows, max_por_accion: int, seed: int = 0):
    """Aplica el MAPEO y limita cuántas frases entran por (split, acción).

    El tope evita que buscar_web / ninguna (miles de frases) aplasten a las
    acciones con pocos ejemplos. Dentro de cada acción se reparte el cupo
    entre sus intenciones de origen para no quedarse solo con la más grande.
    """
    rng = random.Random(seed)
    grupos = defaultdict(lambda: defaultdict(list))  # (split, acción) -> intención -> frases
    for r in rows:
        action = MAPEO.get(r["intent"])
        split = SPLITS.get(r["partition"])
        if action is None or split is None:
            continue
        grupos[(split, action)][r["intent"]].append(r["utt"].strip())

    out = []
    for (split, action), por_intencion in sorted(grupos.items()):
        cupo = max_por_accion if split == "train" else max(1, max_por_accion // 3)
        # Round-robin entre intenciones de origen hasta llenar el cupo
        colas = {i: rng.sample(frases, len(frases)) for i, frases in sorted(por_intencion.items())}
        elegidas = []
        while len(elegidas) < cupo and any(colas.values()):
            for intent, cola in colas.items():
                if cola and len(elegidas) < cupo:
                    elegidas.append((intent, cola.pop()))
        for intent, q in elegidas:
            out.append({"q": q, "expected_action": action, "source": f"massive:{intent}", "split": split})
    return out


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--max", type=int, default=300,
                        help="máximo de frases de train por acción (dev/test usan un tercio)")
    parser.add_argument("--redownload", action="store_true", help="vuelve a descargar el paquete")
    args = parser.parse_args()

    rows = load_jsonl(descargar(args.redownload))
    ejemplos = adaptar(rows, args.max)
    write_jsonl(MASSIVE_PATH, ejemplos)

    print(f"\n{len(ejemplos)} ejemplos escritos en {MASSIVE_PATH}")
    conteo = Counter((e["split"], e["expected_action"]) for e in ejemplos)
    for split in ("train", "dev", "test"):
        detalle = ", ".join(f"{a}={n}" for (s, a), n in sorted(conteo.items()) if s == split)
        print(f"  {split:5}: {detalle}")


if __name__ == "__main__":
    main()
