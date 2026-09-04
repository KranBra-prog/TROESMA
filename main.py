import os
import json
import random
import asyncio
from threading import Thread
from flask import Flask
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
)
import database as db

# ---------------------------------------------------------
# CONFIGURACIÓN Y VARIABLES DE ENTORNO
# ---------------------------------------------------------
load_dotenv()
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CAFECITO_URL = os.getenv("CAFECITO_URL", "https://cafecito.app")

# ---------------------------------------------------------
# SERVIDOR FLASK PARA PLAN FREE EN RENDER
# ---------------------------------------------------------
web_app = Flask('')

@web_app.route('/')
def home():
    return "Bot educativo activo 24/7"

def run_web():
    port = int(os.environ.get("PORT", 8080))
    web_app.run(host='0.0.0.0', port=port)

def keep_alive():
    t = Thread(target=run_web)
    t.daemon = True
    t.start()

# ---------------------------------------------------------
# CARGA DE DATOS
# ---------------------------------------------------------
def cargar_quiz_data():
    with open("quiz_data.json", "r", encoding="utf-8") as f:
        return json.load(f)

QUIZ_DATA = cargar_quiz_data()

# ---------------------------------------------------------
# DISEÑO: ICONOS, BARRAS Y HELPERS VISUALES
# ---------------------------------------------------------

# Icono fijo para categorías conocidas; si aparece una categoría nueva
# en el JSON que no está en este mapa, se le asigna un icono de la
# lista de reserva de forma estable (siempre el mismo para esa categoría).
ICONOS_CATEGORIA = {
    "geografia": "🌍",
    "geografía": "🌍",
    "matematica": "🔢",
    "matemática": "🔢",
    "biologia": "🧬",
    "biología": "🧬",
    "historia": "🏛️",
    "arte": "🎨",
    "musica": "🎵",
    "música": "🎵",
    "deportes": "⚽",
    "ciencia": "🔬",
    "literatura": "📚",
    "tecnologia": "💻",
    "tecnología": "💻",
}
ICONOS_RESERVA = ["🧩", "✨", "🎯", "📌", "🔖", "🃏"]

SEPARADOR = "━━━━━━━━━━━━━━━━━━━━"


def icono_categoria(categoria: dict) -> str:
    clave = categoria["nombre"].strip().lower()
    if clave in ICONOS_CATEGORIA:
        return ICONOS_CATEGORIA[clave]
    indice = sum(ord(c) for c in clave) % len(ICONOS_RESERVA)
    return ICONOS_RESERVA[indice]


def encabezado(emoji: str, titulo: str) -> str:
    return f"<b>{emoji} {SEPARADOR}</b>\n<b>{titulo}</b>\n<b>{emoji} {SEPARADOR}</b>\n\n"


def barra_tiempo(tiempo_actual: int, tiempo_total: int = 15) -> str:
    total_bloques = 10
    llenos = max(0, min(total_bloques, round((tiempo_actual / tiempo_total) * total_bloques)))
    vacios = total_bloques - llenos

    if tiempo_actual > tiempo_total * 0.6:
        bloque = "🟩"
    elif tiempo_actual > tiempo_total * 0.3:
        bloque = "🟨"
    else:
        bloque = "🟥"

    return f"{bloque * llenos}{'⬜' * vacios}  <code>{tiempo_actual}s</code>"


def medalla(posicion: int) -> str:
    return {1: "🥇", 2: "🥈", 3: "🥉"}.get(posicion, f"{posicion}.")


def barra_puntaje(positivos: int, negativos: int, ancho: int = 10) -> str:
    total = positivos + negativos
    if total == 0:
        return "▫️" * ancho
    llenos_pos = max(0, min(ancho, round((positivos / total) * ancho)))
    return "🟢" * llenos_pos + "🔴" * (ancho - llenos_pos)


def fila_ranking(pos: int, nombre: str, pos_pts, neg_pts, total) -> str:
    pos_pts = pos_pts or 0
    neg_pts = neg_pts or 0
    total = total or 0
    signo = "-" if total < 0 else ""
    return (
        f"{medalla(pos)} <b>{nombre}</b>\n"
        f"   {barra_puntaje(pos_pts, neg_pts)}\n"
        f"   🔵 {pos_pts}  🔴 -{neg_pts}   ⭐ <b>{signo}{abs(total)} pts</b>\n\n"
    )

# ---------------------------------------------------------
# COMANDOS PRINCIPALES
# ---------------------------------------------------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    db.registrar_o_actualizar_usuario(user.id, user.username or "Anonimo", user.first_name)

    mensaje = (
        encabezado("🎓", "¡BIENVENIDO AL QUIZ EDUCATIVO!")
        + "<i>Demuestra tus conocimientos, compite en el ranking\n"
        "y pon a prueba tu rapidez mental.</i>\n\n"
        "<b>📌 Comandos disponibles</b>\n"
        "🔹 /quiz — Iniciar un cuestionario\n"
        "🔹 /ranking_cat — Ranking por categoría\n"
        "🔹 /ranking_gen — Ranking general\n"
        "🔹 /reiniciar — Limpiar tu historial\n"
        "🔹 /donar — Apoyar el proyecto\n\n"
        "<b>⏱️ Regla:</b> tenés 15s por pregunta. Si el tiempo llega a 0, "
        "se pasa a la siguiente y se descuenta 1 punto."
    )

    keyboard = [
        [InlineKeyboardButton("🎮 Jugar Quiz", callback_data="menu_quiz")],
        [InlineKeyboardButton("📊 Ranking General", callback_data="menu_rank_gen")],
        [InlineKeyboardButton("☕ Donar con Cafecito", url=CAFECITO_URL)],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    if update.message:
        await update.message.reply_text(mensaje, parse_mode="HTML", reply_markup=reply_markup)
    elif update.callback_query:
        await update.callback_query.edit_message_text(mensaje, parse_mode="HTML", reply_markup=reply_markup)

async def comando_quiz(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    db.registrar_o_actualizar_usuario(user.id, user.username or "Anonimo", user.first_name)

    keyboard = []
    fila = []
    for cat in QUIZ_DATA["categorias"]:
        etiqueta = f"{icono_categoria(cat)} {cat['nombre']}"
        fila.append(InlineKeyboardButton(etiqueta, callback_data=f"playcat_{cat['id']}"))
        if len(fila) == 2:
            keyboard.append(fila)
            fila = []
    if fila:
        keyboard.append(fila)

    reply_markup = InlineKeyboardMarkup(keyboard)
    texto = (
        encabezado("🗂️", "SELECCIONÁ UNA CATEGORÍA")
        + "<i>Elegí un tema para iniciar una ronda de 5 preguntas:</i>"
    )
    if update.message:
        await update.message.reply_text(texto, parse_mode="HTML", reply_markup=reply_markup)
    else:
        await update.callback_query.edit_message_text(texto, parse_mode="HTML", reply_markup=reply_markup)

# ---------------------------------------------------------
# LÓGICA DE PREGUNTAS Y TEMPORIZADOR
# ---------------------------------------------------------
def texto_pregunta_render(categoria: dict, pregunta_obj: dict, idx: int, total: int, tiempo: int) -> str:
    icono = icono_categoria(categoria)
    return (
        f"{icono} <b>{categoria['nombre']}</b>   ·   Pregunta <b>{idx + 1}/{total}</b>\n"
        f"{SEPARADOR}\n\n"
        f"<b>{pregunta_obj['pregunta']}</b>\n\n"
        f"{barra_tiempo(tiempo)}"
    )


async def manejar_pregunta(query, context, cat_id: str, idx: int, preguntas: list = None):
    if preguntas is None:
        if context.user_data is not None:
            preguntas = context.user_data.get("preguntas_quiz", [])
        else:
            preguntas = []

    categoria = next((c for c in QUIZ_DATA["categorias"] if c["id"] == cat_id), None)

    if not categoria or idx >= len(preguntas):
        await query.message.reply_text(
            encabezado("🎉", "¡HAS COMPLETADO TU RONDA!")
            + "<i>Consultá tus puntos actualizados con /ranking_cat o /ranking_gen</i>",
            parse_mode="HTML",
        )
        if context.user_data is not None:
            context.user_data.pop("preguntas_quiz", None)
        return

    pregunta_obj = preguntas[idx]

    opciones = pregunta_obj["opciones"].copy()
    random.shuffle(opciones)

    keyboard = []
    for opc in opciones:
        cb_data = f"ans_{cat_id}_{idx}_{opc}"
        keyboard.append([InlineKeyboardButton(f"▫️ {opc}", callback_data=cb_data)])

    reply_markup = InlineKeyboardMarkup(keyboard)

    tiempo_inicial = 15
    texto_pregunta = texto_pregunta_render(categoria, pregunta_obj, idx, len(preguntas), tiempo_inicial)

    if pregunta_obj.get("imagen"):
        msg = await query.message.reply_photo(
            photo=pregunta_obj["imagen"],
            caption=texto_pregunta,
            parse_mode="HTML",
            reply_markup=reply_markup
        )
    else:
        msg = await query.message.reply_text(
            texto_pregunta,
            parse_mode="HTML",
            reply_markup=reply_markup
        )

    context.job_queue.run_repeating(
        cuenta_regresiva_callback,
        interval=1,
        first=1,
        data={
            "chat_id": query.message.chat_id,
            "message_id": msg.message_id,
            "cat_id": cat_id,
            "idx": idx,
            "user_id": query.from_user.id,
            "tiene_foto": bool(pregunta_obj.get("imagen")),
            "preguntas": preguntas,
            "tiempo": tiempo_inicial,
            "tiempo_total": tiempo_inicial,
            "query": query
        },
        name=f"timer_{msg.message_id}"
    )

async def cuenta_regresiva_callback(context: ContextTypes.DEFAULT_TYPE):
    job = context.job
    job_data = job.data

    job_data["tiempo"] -= 1
    tiempo_actual = job_data["tiempo"]
    chat_id = job_data["chat_id"]
    message_id = job_data["message_id"]
    cat_id = job_data["cat_id"]
    idx = job_data["idx"]
    preguntas = job_data["preguntas"]
    pregunta_obj = preguntas[idx]
    categoria = next((c for c in QUIZ_DATA["categorias"] if c["id"] == cat_id), None)

    if tiempo_actual > 0:
        texto_actualizado = texto_pregunta_render(
            categoria, pregunta_obj, idx, len(preguntas), tiempo_actual
        )

        keyboard = []
        for opc in pregunta_obj["opciones"]:
            cb_data = f"ans_{cat_id}_{idx}_{opc}"
            keyboard.append([InlineKeyboardButton(f"▫️ {opc}", callback_data=cb_data)])
        reply_markup = InlineKeyboardMarkup(keyboard)

        try:
            if job_data["tiene_foto"]:
                await context.bot.edit_message_caption(
                    chat_id=chat_id, message_id=message_id, caption=texto_actualizado, parse_mode="HTML", reply_markup=reply_markup
                )
            else:
                await context.bot.edit_message_text(
                    chat_id=chat_id, message_id=message_id, text=texto_actualizado, parse_mode="HTML", reply_markup=reply_markup
                )
        except Exception:
            pass

    else:
        job.schedule_removal()

        user_id = job_data["user_id"]
        db.registrar_pregunta_respondida(user_id, pregunta_obj["id"])
        db.actualizar_puntaje(user_id, cat_id, es_correcto=False)

        texto_expirado = encabezado("⏰", "¡TIEMPO AGOTADO! ❌  (-1 Punto)")

        try:
            if job_data["tiene_foto"]:
                await context.bot.edit_message_caption(chat_id=chat_id, message_id=message_id, caption=texto_expirado, parse_mode="HTML")
            else:
                await context.bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=texto_expirado, parse_mode="HTML")
        except Exception:
            pass

        await asyncio.sleep(2)
        await manejar_pregunta(job_data["query"], context, cat_id, idx + 1, preguntas=preguntas)

async def procesar_respuesta(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    parts = query.data.split("_")
    cat_id = parts[1]
    idx = int(parts[2])
    respuesta = "_".join(parts[3:])

    current_jobs = context.job_queue.get_jobs_by_name(f"timer_{query.message.message_id}")
    for job in current_jobs:
        job.schedule_removal()

    preguntas = context.user_data.get("preguntas_quiz", []) if context.user_data else []
    if idx >= len(preguntas):
        return

    pregunta_obj = preguntas[idx]
    db.registrar_pregunta_respondida(query.from_user.id, pregunta_obj["id"])

    if respuesta == pregunta_obj["respuesta_correcta"]:
        db.actualizar_puntaje(query.from_user.id, cat_id, es_correcto=True)
        resultado = encabezado("✅", "¡RESPUESTA CORRECTA!  (+1 Punto)")
    else:
        db.actualizar_puntaje(query.from_user.id, cat_id, es_correcto=False)
        resultado = (
            encabezado("❌", "RESPUESTA INCORRECTA  (-1 Punto)")
            + f"<i>Correcta: {pregunta_obj['respuesta_correcta']}</i>"
        )

    if query.message.photo:
        await query.edit_message_caption(caption=resultado, parse_mode="HTML")
    else:
        await query.edit_message_text(text=resultado, parse_mode="HTML")

    await asyncio.sleep(2)
    await manejar_pregunta(query, context, cat_id, idx + 1, preguntas=preguntas)

# ---------------------------------------------------------
# RANKING Y OTROS COMANDOS
# ---------------------------------------------------------
async def comando_ranking_gen(update: Update, context: ContextTypes.DEFAULT_TYPE):
    ranking = db.obtener_ranking_general()

    texto = encabezado("🏆", "RANKING GENERAL DE JUGADORES")

    if not ranking:
        texto += "<i>Aún no hay puntos registrados en el juego.</i>"
    else:
        for pos, row in enumerate(ranking, start=1):
            nombre, pos_pts, neg_pts, total = row
            texto += fila_ranking(pos, nombre, pos_pts, neg_pts, total)

    if update.message:
        await update.message.reply_text(texto, parse_mode="HTML")
    else:
        await update.callback_query.edit_message_text(texto, parse_mode="HTML")

async def comando_ranking_cat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = []
    fila = []
    for cat in QUIZ_DATA["categorias"]:
        etiqueta = f"{icono_categoria(cat)} {cat['nombre']}"
        fila.append(InlineKeyboardButton(etiqueta, callback_data=f"showrankcat_{cat['id']}"))
        if len(fila) == 2:
            keyboard.append(fila)
            fila = []
    if fila:
        keyboard.append(fila)

    reply_markup = InlineKeyboardMarkup(keyboard)
    texto = (
        encabezado("🏅", "RANKING POR CATEGORÍA")
        + "<i>Seleccioná una categoría para ver sus posiciones:</i>"
    )
    if update.message:
        await update.message.reply_text(texto, parse_mode="HTML", reply_markup=reply_markup)
    else:
        await update.callback_query.edit_message_text(texto, parse_mode="HTML", reply_markup=reply_markup)

async def mostrar_ranking_cat_seleccionado(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    cat_id = query.data.split("_")[1]

    categoria = next((c for c in QUIZ_DATA["categorias"] if c["id"] == cat_id), None)
    ranking = db.obtener_ranking_categoria(cat_id)

    texto = encabezado(icono_categoria(categoria), f"RANKING: {categoria['nombre'].upper()}")

    if not ranking:
        texto += "<i>No hay puntos registrados en esta categoría aún.</i>"
    else:
        for pos, row in enumerate(ranking, start=1):
            nombre, pos_pts, neg_pts, total = row
            texto += fila_ranking(pos, nombre, pos_pts, neg_pts, total)

    await query.edit_message_text(texto, parse_mode="HTML")

async def comando_reiniciar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    db.reiniciar_historial_usuario(user_id)
    await update.message.reply_text(
        encabezado("🔄", "¡HISTORIAL REINICIADO!")
        + "<i>Se limpió tu registro de preguntas respondidas. Ahora podés volver a "
        "jugar todas las categorías desde cero.</i>",
        parse_mode="HTML"
    )

async def comando_donar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [[InlineKeyboardButton("☕ Invítame un Cafecito", url=CAFECITO_URL)]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    texto = (
        encabezado("☕", "APOYÁ AL PROYECTO EDUCATIVO")
        + "<i>Si disfrutás aprendiendo con este bot, podés colaborar invitándonos "
        "un cafecito para financiar el mantenimiento y sumar más contenido.</i>\n\n"
        "<b>¡Muchas gracias por tu apoyo! ❤️</b>"
    )
    if update.message:
        await update.message.reply_text(texto, parse_mode="HTML", reply_markup=reply_markup)
    else:
        await update.callback_query.edit_message_text(texto, parse_mode="HTML", reply_markup=reply_markup)

# ---------------------------------------------------------
# CALLBACK HANDLER GENERAL
# ---------------------------------------------------------
async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data

    if data == "menu_quiz":
        await comando_quiz(update, context)
    elif data == "menu_rank_gen":
        await comando_ranking_gen(update, context)
    elif data.startswith("playcat_"):
        cat_id = data.split("_")[1]
        user_id = query.from_user.id

        categoria = next((c for c in QUIZ_DATA["categorias"] if c["id"] == cat_id), None)
        if categoria:
            respondidas_ids = db.obtener_ids_preguntas_respondidas(user_id)
            preguntas_disponibles = [
                p for p in categoria["preguntas"]
                if p["id"] not in respondidas_ids
            ]

            if not preguntas_disponibles:
                await query.edit_message_text(
                    encabezado("🎓", "¡FELICITACIONES! 🎉")
                    + "<i>Ya respondiste todas las preguntas de esta categoría.</i>\n\n"
                    "Usá /reiniciar para volver a jugarla o elegí otra disponible.",
                    parse_mode="HTML"
                )
                return

            random.shuffle(preguntas_disponibles)
            ronda_preguntas = preguntas_disponibles[:5]
            if context.user_data is not None:
                context.user_data["preguntas_quiz"] = ronda_preguntas

            await manejar_pregunta(query, context, cat_id, 0, preguntas=ronda_preguntas)
    elif data.startswith("ans_"):
        await procesar_respuesta(update, context)
    elif data.startswith("showrankcat_"):
        await mostrar_ranking_cat_seleccionado(update, context)

# ---------------------------------------------------------
# ARRANQUE DE LA APLICACIÓN
# ---------------------------------------------------------
def main():
    db.init_db()

    # Iniciar servidor web para que Render mantenga el Web Service vivo
    keep_alive()

    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("quiz", comando_quiz))
    app.add_handler(CommandHandler("ranking_cat", comando_ranking_cat))
    app.add_handler(CommandHandler("ranking_gen", comando_ranking_gen))
    app.add_handler(CommandHandler("reiniciar", comando_reiniciar))
    app.add_handler(CommandHandler("donar", comando_donar))

    app.add_handler(CallbackQueryHandler(callback_handler))

    print("🤖 Bot educativo listo y en ejecución...")
    app.run_polling()

if __name__ == "__main__":
    main()
