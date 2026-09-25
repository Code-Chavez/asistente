# Datos de entrenamiento del clasificador de intención

Formato JSONL: una frase por línea, `{"q": "...", "expected_action": "..."}`.

| Archivo | Qué es | ¿Se entrena con él? |
|---|---|---|
| `base_es.jsonl` | Frases escritas a mano para cada acción | Sí |
| `massive_es.jsonl` | MASSIVE adaptado (generado por `scripts/importar_massive.py`) | Solo `split: train` |
| `eval_es.jsonl` | Frases de evaluación escritas a mano | **Nunca**: solo para medir |
| `raw/` | Copia local de MASSIVE es-ES (ignorada por git) | — |

Las correcciones del usuario viven en `agent/feedback_data.jsonl` y las frases
dudosas por etiquetar en `agent/pendientes.jsonl` (ambas personales, fuera de git).

Para añadir frases nuevas a una acción, escríbelas en `base_es.jsonl`. No copies
frases de `eval_es.jsonl`: si el modelo las ha visto, la evaluación deja de servir.

## Atribución

`massive_es.jsonl` es una adaptación (subconjunto y reetiquetado de intenciones)
de **MASSIVE**, © Amazon.com, Inc., publicado bajo licencia
[CC BY 4.0](https://creativecommons.org/licenses/by/4.0/):

> FitzGerald et al. (2022). *MASSIVE: A 1M-Example Multilingual Natural Language
> Understanding Dataset with 51 Typologically-Diverse Languages.*
> https://github.com/alexa/massive
