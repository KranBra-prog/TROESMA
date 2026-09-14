import os
import asyncio
import logging
from threading import Thread
from flask import Flask
from dotenv import load_dotenv

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
)

import database as db

# Cargar variables de entorno
load_dotenv()
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CAFECITO_URL = os.getenv("CAFECITO_URL", "https://cafecito.app")

# Configuración de Logs
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# --- SERVIDOR KEEP-ALIVE PARA RENDER ---
app = Flask("")

@app.route("/")
def home():
    return "Bot de Trivia activo 24/7"

def run_flask():
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))

def keep_alive():
    t = Thread(target=run_flask)
    t.daemon = True
    t.start()

# --- DISEÑO Y UTILIDADES VISUALES ---
def encabezado(titulo: str) -> str:
    """Genera un encabezado visual estandarizado para los mensajes."""
    return f"━━━━━━━━━━━━━━━━━━━━━━\n🎯 *TROESMA QUIZ* | {titulo}\n━━━━━━━━━━━━━━━━━━━━━━\n\n"

def generar_barra_progreso(porcentaje: float, longitud: int = 10) -> str:
    """Genera una barra de progreso basada en el porcentaje especificado."""
    llenos = int(round(longitud * (porcentaje / 100)))
    vacios = longitud - llenos
    return "█" * llenos + "░" * vacios

def generar_barra_tiempo(segundos_restantes: int, total_segundos: int = 15) -> str:
    """Genera una barra de tiempo animada colorimétrica."""
    porcentaje = segundos_restantes / total_segundos
    bloques = int(porcentaje * 10)
    
    if porcentaje > 0.6:
        color = "🟩"
    elif porcentaje > 0.3:
        color = "🟨"
    else:
        color = "🟥"
        
    return f"[{color * bloques}{'▫️' * (10 - bloques)}] ({segundos_restantes}s)"

# --- COMANDOS DEL BOT ---

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Muestra el mensaje de bienvenida principal."""
    user = update.effective_user
    db.registrar_o_actualizar_usuario(user.id, user.username, user.first_name)
    
    texto = (
        f"{encabezado('¡BIENVENIDO!')}"
        f"Hola *{user.first_name}* 👋\n\n"
        "Demuestra tus conocimientos en nuestras trivias interactivas.\n\n"
        "📌 *Comandos principales:*\n"
        "• /quiz - Iniciar una nueva ronda de preguntas\n"
        "• /perfil - Ver tu nivel, estadísticas y racha\n"
        "• /ranking_gen - Tabla global de clasificación\n"
        "• /ranking_cat - Clasificación por categoría\n"
        "• /reiniciar - Limpiar historial para volver a jugar\n"
        "• /donar - Apoyar el proyecto\n"
    )
    
    keyboard = [
        [InlineKeyboardButton("🎮 Jugar Ahora", callback_data="menu_quiz")],
        [InlineKeyboardButton("👤 Mi Perfil", callback_data="ver_perfil"),
         InlineKeyboardButton("🏆 Ranking", callback_data="menu_ranking")]
    ]
    
    await update.message.reply_text(
        texto, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def cmd_perfil(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Muestra la tarjeta de perfil y estadísticas del jugador."""
    user = update.effective_user
    db.registrar_o_actualizar_usuario(user.id, user.username, user.first_name)
    
    # Obtener datos acumulados
    ranking = db.obtener_ranking_general()
    pos_user = "N/A"
    p_pos, p_neg, total = 0, 0, 0
    
    for idx, fila in enumerate(ranking, start=1):
        # fila: (nombre, pos, neg, total)
        if fila[0] == (user.first_name or user.username or "Anónimo"):
            pos_user = f"#{idx}"
            p_pos = fila[1] or 0
            p_neg = fila[2] or 0
            total = fila[3] or 0
            break

    total_respuestas = p_pos + p_neg
    efectividad = (p_pos / total_respuestas * 100) if total_respuestas > 0 else 0
    barra_efectividad = generar_barra_progreso(efectividad)
    
    racha_actual = context.user_data.get("streak", 0)

    texto = (
        f"{encabezado('PERFIL DE JUGADOR')}"
        f"👤 *Usuario:* {user.first_name}\n"
        f"🏅 *Posición Global:* {pos_user}\n"
        f"🔥 *Racha Actual:* {racha_actual} seguidas\n"
        f"⭐ *Puntos Totales:* {total}\n\n"
        f"📊 *Efectividad:* {efectividad:.1f}%\n"
        f"`[{barra_efectividad}]`\n\n"
        f"✅ *Aciertos:* {p_pos}\n"
        f"❌ *Errores:* {p_neg}\n"
        f"📝 *Total Contestado:* {total_respuestas}"
    )
    
    keyboard = [[InlineKeyboardButton("🚀 Iniciar Quiz", callback_data="menu_quiz")]]
    
    if update.message:
        await update.message.reply_text(texto, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))
    else:
        await update.callback_query.edit_message_text(texto, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))

async def cmd_quiz(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Muestra el menú de categorías para comenzar un quiz."""
    data_quiz = context.bot_data.get("quiz_json", {})
    categorias = data_quiz.get("categorias", [])

    if not categorias:
        msg = "⚠️ No se encontraron categorías cargadas en el sistema."
        if update.message:
            await update.message.reply_text(msg)
        else:
            await update.callback_query.edit_message_text(msg)
        return

    keyboard = []
    for cat in categorias:
        keyboard.append([InlineKeyboardButton(cat["nombre"], callback_data=f"cat_{cat['id']}")])

    texto = f"{encabezado('SELECCIÓN DE CATEGORÍA')}" "Elige la categoría en la que deseas competir:"
    
    if update.message:
        await update.message.reply_text(texto, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))
    else:
        await update.callback_query.edit_message_text(texto, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))

# --- LÓGICA DEL JUEGO Y PREGUNTAS ---

async def presentar_pregunta(query, context: ContextTypes.DEFAULT_TYPE, user_id: int, cat_id: str):
    """Selecciona y envía una pregunta no respondida al usuario con temporizador dinámico."""
    data_quiz = context.bot_data.get("quiz_json", {})
    categoria = next((c for c in data_quiz.get("categorias", []) if c["id"] == cat_id), None)

    if not categoria:
        await query.edit_message_text("❌ Categoría no encontrada.")
        return

    # Obtener preguntas no respondidas
    respondidas = db.obtener_ids_preguntas_respondidas(user_id)
    disponibles = [p for p in categoria["preguntas"] if p["id"] not in respondidas]

    if not disponibles:
        texto = (
            f"{encabezado('CATEGORÍA COMPLETADA')}"
            f"🎉 ¡Felicidades! Has respondido todas las preguntas de *{categoria['nombre']}*.\n\n"
            "Usa el comando /reiniciar si deseas volver a jugar esta categoría."
        )
        keyboard = [[InlineKeyboardButton("📂 Otra Categoría", callback_data="menu_quiz")]]
        await query.edit_message_text(texto, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))
        return

    pregunta_actual = disponibles[0]
    context.user_data["pregunta_activa"] = pregunta_actual
    context.user_data["cat_activa"] = cat_id

    # Construir botones de opciones
    keyboard = []
    for idx, opcion in enumerate(pregunta_actual["opciones"]):
        keyboard.append([InlineKeyboardButton(opcion, callback_data=f"ans_{idx}")])

    markup = InlineKeyboardMarkup(keyboard)
    
    # Renderizar tarjeta inicial
    racha = context.user_data.get("streak", 0)
    indicador_racha = f" (🔥 Racha x{racha})" if racha > 1 else ""
    
    texto_pregunta = (
        f"{encabezado(categoria['nombre'])}\n"
        f"❓ *{pregunta_actual['pregunta']}*{indicador_racha}\n\n"
        f"⏱️ Tiempo restante:\n`{generar_barra_tiempo(15)}`"
    )

    # Si la pregunta incluye imagen opcional
    if "imagen" in pregunta_actual and pregunta_actual["imagen"]:
        msg = await query.message.reply_photo(
            photo=pregunta_actual["imagen"],
            caption=texto_pregunta,
            parse_mode="Markdown",
            reply_markup=markup
        )
    else:
        msg = await query.edit_message_text(
            text=texto_pregunta,
            parse_mode="Markdown",
            reply_markup=markup
        )

    context.user_data["msg_id_activo"] = msg.message_id

    # Iniciar temporizador en segundo plano (15 segundos)
    asyncio.create_task(
        iniciar_temporizador(
            chat_id=query.message.chat_id,
            message_id=msg.message_id,
            context=context,
            pregunta_id=pregunta_actual["id"],
            has_photo="imagen" in pregunta_actual and bool(pregunta_actual["imagen"])
        )
    )

async def iniciar_temporizador(chat_id: int, message_id: int, context: ContextTypes.DEFAULT_TYPE, pregunta_id: str, has_photo: bool):
    """Cuenta regresiva dinámicamente actualizada cada segundo."""
    for s in range(14, -1, -1):
        await asyncio.sleep(1)
        
        # Verificar si el usuario ya respondió
        preg_activa = context.user_data.get("pregunta_activa")
        if not preg_activa or preg_activa["id"] != pregunta_id:
            return  # La pregunta fue respondida o cambió

        # Actualizar texto con la barra de tiempo
        barra = generar_barra_tiempo(s)
        pregunta = preg_activa["pregunta"]
        cat_nombre = context.user_data.get("cat_activa", "QUIZ")
        
        nuevo_texto = (
            f"{encabezado(cat_nombre)}\n"
            f"❓ *{pregunta}*\n\n"
            f"⏱️ Tiempo restante:\n`{barra}`"
        )

        try:
            if has_photo:
                await context.bot.edit_message_caption(
                    chat_id=chat_id, message_id=message_id, caption=nuevo_texto, parse_mode="Markdown"
                )
            else:
                await context.bot.edit_message_text(
                    chat_id=chat_id, message_id=message_id, text=nuevo_texto, parse_mode="Markdown"
                )
        except Exception:
            pass # Prevenir errores si Telegram limita la tasa de edición

    # Si llega a 0 sin respuesta:
    if context.user_data.get("pregunta_activa", {}).get("id") == pregunta_id:
        context.user_data["streak"] = 0 # Reiniciar racha por tiempo agotado
        db.registrar_pregunta_respondida(chat_id, pregunta_id)
        db.actualizar_puntaje(chat_id, context.user_data.get("cat_activa"), es_correcto=False)
        context.user_data.pop("pregunta_activa", None)

        texto_fin = f"{encabezado('⏱️ TIEMPO AGOTADO')}\n¡Se agotaron los 15 segundos! No sumas puntos."
        keyboard = [[InlineKeyboardButton("➡️ Siguiente Pregunta", callback_data=f"cat_{context.user_data.get('cat_activa')}")]]
        
        if has_photo:
            await context.bot.edit_message_caption(chat_id=chat_id, message_id=message_id, caption=texto_fin, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))
        else:
            await context.bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=texto_fin, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))

# --- MANEJADOR DE CALLBACKS E INTERACTIVIDAD ---

async def manejar_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Procesa los clics en botones inline."""
    query = update.callback_query
    data = query.data
    user = query.from_user

    # Asegurar registro de usuario
    db.registrar_o_actualizar_usuario(user.id, user.username, user.first_name)

    if data == "menu_quiz":
        await cmd_quiz(update, context)
        await query.answer()

    elif data == "ver_perfil":
        await cmd_perfil(update, context)
        await query.answer()

    elif data.startswith("cat_"):
        cat_id = data.replace("cat_", "")
        await presentar_pregunta(query, context, user.id, cat_id)
        await query.answer()

    elif data.startswith("ans_"):
        idx_seleccionado = int(data.replace("ans_", ""))
        pregunta = context.user_data.get("pregunta_activa")

        if not pregunta:
            await query.answer("⚠️ Esta pregunta ya expiró o fue respondida.", show_alert=True)
            return

        opcion_elegida = pregunta["opciones"][idx_seleccionado]
        es_correcta = (opcion_elegida == pregunta["respuesta_correcta"])
        cat_id = context.user_data.get("cat_activa")

        # Registro en Base de Datos
        db.registrar_pregunta_respondida(user.id, pregunta["id"])
        db.actualizar_puntaje(user.id, cat_id, es_correcto)

        # Manejo de Racha
        if es_correcta:
            context.user_data["streak"] = context.user_data.get("streak", 0) + 1
            racha = context.user_data["streak"]
            msg_popup = f"🎉 ¡CORRECTO! +1 Punto\n🔥 Racha de {racha} aciertos"
        else:
            context.user_data["streak"] = 0
            msg_popup = f"❌ INCORRECTO\nLa respuesta era: {pregunta['respuesta_correcta']}"

        # 💡 POP-UP EMERGENTE EN PANTALLA
        await query.answer(text=msg_popup, show_alert=not es_correcta)

        # Construir mensaje de retroalimentación en el chat
        explicacion = pregunta.get("explicacion", "")
        bloque_explicacion = f"\n\n💡 *Explicación:*\n_{explicacion}_" if explicacion else ""

        if es_correcta:
            res_texto = (
                f"{encabezado('✅ ¡RESPUESTA CORRECTA!')}"
                f"Elegiste: *{opcion_elegida}*{bloque_explicacion}"
            )
        else:
            res_texto = (
                f"{encabezado('❌ RESPUESTA INCORRECTA')}"
                f"Tu respuesta: ~{opcion_elegida}~\n"
                f"Correcta: *{pregunta['respuesta_correcta']}*{bloque_explicacion}"
            )

        # Limpiar pregunta activa
        context.user_data.pop("pregunta_activa", None)

        keyboard = [[InlineKeyboardButton("➡️ Siguiente Pregunta", callback_data=f"cat_{cat_id}")]]
        
        if query.message.photo:
            await query.edit_message_caption(caption=res_texto, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))
        else:
            await query.edit_message_text(text=res_texto, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))

# --- COMANDOS ADICIONALES ---

async def cmd_ranking_gen(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Muestra el ranking global con medallas y gauges."""
    ranking = db.obtener_ranking_general()
    
    if not ranking:
        await update.message.reply_text("🏆 Aún no hay puntajes registrados.")
        return

    medallas = ["🥇", "🥈", "🥉"]
    lineas = []
    
    for idx, (nombre, pos, neg, total) in enumerate(ranking[:10], start=1):
        medalla = medallas[idx-1] if idx <= 3 else f"#{idx}"
        pos = pos or 0
        neg = neg or 0
        tot_resp = pos + neg
        
        efectividad = (pos / tot_resp * 100) if tot_resp > 0 else 0
        gauge = "🟩" * int(efectividad // 20) + "🟥" * (5 - int(efectividad // 20))
        
        lineas.append(f"{medalla} *{nombre}* - {total} pts `{gauge}`")

    texto = f"{encabezado('TOP 10 RANKING GENERAL')}" + "\n".join(lineas)
    await update.message.reply_text(texto, parse_mode="Markdown")

async def cmd_reiniciar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Limpia el historial de preguntas del usuario."""
    user = update.effective_user
    db.reiniciar_historial_usuario(user.id)
    context.user_data["streak"] = 0
    await update.message.reply_text("🔄 *Tu historial de preguntas ha sido reiniciado.* Puedes volver a jugar cualquier categoría desde cero.", parse_mode="Markdown")

async def cmd_donar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Envía el enlace de apoyo al creador."""
    keyboard = [[InlineKeyboardButton("☕ Donar en Cafecito", url=CAFECITO_URL)]]
    await update.message.reply_text(
        "Si disfrutas de este bot y deseas apoyar su mantenimiento, puedes invitarme un Cafecito ☕:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# --- CARGA DE DATOS Y MAIN ---

def cargar_quiz_data() -> dict:
    import json
    if os.path.exists("quiz_data.json"):
        with open("quiz_data.json", "r", encoding="utf-8") as f:
            return json.load(f)
    return {"categorias": []}

def main():
    # Inicializar Base de Datos en Supabase
    db.init_db()

    # Iniciar Servidor Web Keep-Alive para Render
    keep_alive()

    # Configurar la aplicación de Telegram
    app_telegram = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    app_telegram.bot_data["quiz_json"] = cargar_quiz_data()

    # Handlers de Comandos
    app_telegram.add_handler(CommandHandler("start", cmd_start))
    app_telegram.add_handler(CommandHandler("perfil", cmd_perfil))
    app_telegram.add_handler(CommandHandler("quiz", cmd_quiz))
    app_telegram.add_handler(CommandHandler("ranking_gen", cmd_ranking_gen))
    app_telegram.add_handler(CommandHandler("reiniciar", cmd_reiniciar))
    app_telegram.add_handler(CommandHandler("donar", cmd_donar))

    # Handler de Callbacks
    app_telegram.add_handler(CallbackQueryHandler(manejar_callback))

    logger.info("🤖 Bot desplegado e iniciando Polling...")
    app_telegram.run_polling()

if __name__ == "__main__":
    main()
