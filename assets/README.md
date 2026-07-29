# Calibración de botones para RPA de WhatsApp

Los skills `enviar_nota_voz` y `llamar_whatsapp` localizan botones en pantalla
por reconocimiento de imagen. Para que funcionen debes capturar **una vez** los
botones de TU WhatsApp Desktop (dependen de tu resolución y tema) y guardarlos
aquí con estos nombres exactos:

| Archivo | Botón a capturar |
|---|---|
| `wa_mic.png`  | El botón del **micrófono** (para notas de voz) |
| `wa_send.png` | El botón de **enviar** (opcional) |
| `wa_call.png` | El botón de **llamada de voz** (arriba a la derecha del chat) |

## Cómo capturarlos
1. Abre un chat en WhatsApp Desktop.
2. Recorta SOLO el icono del botón (con la herramienta Recortes de Windows) y
   guárdalo con el nombre correspondiente en esta carpeta.
3. Mantén el recorte pequeño y nítido; incluye solo el icono.

> Nota: estas capturas son personales y NO se suben al repositorio
> (`.gitignore` excluye `assets/*.png`). El reconocimiento es *best-effort*:
> si cambias de tema, tamaño de ventana o resolución, tendrás que recapturarlos.
> Para mayor fiabilidad, instala OpenCV (`pip install opencv-python`), que
> habilita la coincidencia por confianza.
