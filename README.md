# 🤖 TROESMA - Bot Educativo de Telegram

Un bot interactivo de trivias y evaluación continua para Telegram desarrollado en Python. Incluye temporizador visual en tiempo real, tablas de clasificación globales y por categoría, y soporte para imágenes educativas.

---

## 🚀 Características

- ⏱️ **Temporizador animado:** Cuenta regresiva de 15 segundos con barra de progreso visual (`🟩` → `🟨` → `🟥`).
- 🏆 **Ranking dinámico:** Medallas (`🥇`, `🥈`, `🥉`) para el Top 3 y barra de efectividad de aciertos/errores.
- 🗂️ **Categorías múltiples:** Carga dinámica de preguntas desde `quiz_data.json`.
- 🖼️ **Soporte multimedia:** Preguntas con imágenes y banderas en alta resolución.
- 🔄 **Sin preguntas repetidas:** Registro persistente en SQLite con opción de reinicio mediante `/reiniciar`.
- 🌐 **Despliegue 24/7:** Servidor Flask integrado para compatibilidad con el plan gratuito de Render.

---

## 🛠️ Requisitos Previos

- Python 3.10 o superior
- Un token de bot proporcionado por [@BotFather](https://t.me/BotFather)

