# Asistente Jarvis con Inteligencia Artificial

Este proyecto es un asistente virtual escalable inspirado en Jarvis, impulsado por una interfaz gráfica moderna (customtkinter) y un sistema de Machine Learning (scikit-learn) para la detección de intenciones.

## Flujo de Ejecución de la Arquitectura

La arquitectura está diseñada para ser altamente modular, aislando la predicción de la ejecución real. Aquí tienes el flujo exacto de cómo viajan los datos desde que escribes un mensaje hasta que la acción ocurre:

```mermaid
sequenceDiagram
    participant User as Usuario
    participant GUI as Interfaz (gui.py)
    participant Router as SkillRouter
    participant ML as ContextualBandit (ML)
    participant Skill as Skill (Ej: WhatsApp)

    User->>GUI: Escribe comando (Ej: "manda whatsapp a carlos")
    GUI->>Router: execute({"q": "manda whatsapp..."})
    
    activate Router
    Router->>ML: select(context)
    
    activate ML
    Note over ML: 1. Vectoriza texto (TF-IDF)<br/>2. Infiere intención (SGDClassifier)
    ML-->>Router: Devuelve acción: "enviar_whatsapp"
    deactivate ML
    
    Router->>Skill: execute(context)
    
    activate Skill
    Note over Skill: 3. Extrae parámetros (Ej: "carlos")<br/>4. Ejecuta la lógica o API
    Skill-->>Router: Devuelve Result (Success, Mensaje)
    deactivate Skill
    
    Note over Router: 5. Actualiza estadísticas (Memoria)
    Router-->>GUI: Devuelve respuesta formateada
    deactivate Router
    
    GUI->>User: Muestra mensaje en pantalla
```

### Componentes del Flujo

1. **Interfaz Gráfica (`gui.py`)**: Atrapa la entrada del usuario de manera asíncrona para no congelar la pantalla, y le pasa la consulta en formato de "Contexto" (`{"q": texto}`) al Router.
2. **Enrutador (`agent/router.py`)**: Es el director de orquesta. Conoce todas las habilidades (skills) disponibles pero no sabe cuándo ejecutarlas. Le delega esa decisión al bandido/clasificador.
3. **Cerebro ML (`agent/bandit.py`)**: El modelo de `scikit-learn`. Traduce el lenguaje natural a comandos fijos que la programación puede entender. Además, es capaz de aprender sobre la marcha (Online Learning) con retroalimentación (feedback).
4. **Habilidades (`skills/`)**: Son módulos tontos y especializados. Reciben el texto original para buscar palabras clave (como a quién enviar el mensaje) y ejecutan la acción real (abrir web, crear archivo, etc.).

## Instalación y Uso

1. Instalar requerimientos: `pip install -r requirements.txt`
2. Ejecutar el asistente: `python demo.py`
