import os
import json
import random
import asyncio
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
)
import database as db

load_dotenv()
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CAFECITO_URL = os.getenv("CAFECITO_URL", "https://cafecito.app")

def cargar_quiz_data():
    with open("quiz_data.json", "r", encoding="utf-8") as f:
        return json.load(f)

QUIZ_DATA = cargar_quiz_data()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    db.registrar_o_actualizar_usuario(user.id, user.username or "Anonimo", user.first_name)
    
    mensaje = (
        "<b>✨ ────────────────────────── ✨</b>\n"
        "<b>🎓 ¡BIENVENIDO AL QUIZ EDUCATIVO! 🎓</b>\n"
        "<b>✨ ────────────────────────── ✨</b>\n\n"
        "<i>Demuestra tus conocimientos, compite en el ranking\n"
        "y pon a prueba tu rapidez mental.</i>\n\n"
        "<b>📌 Comandos Disponibles:</b>\n"
        "🔹 <b>/quiz</b> : Iniciar un cuestionario\n"
        "🔹 <b>/ranking_cat</b> : Ranking por categoría\n"
        "🔹 <b>/ranking_gen</b> : Ranking general de usuarios\n"
        "🔹 <b>/reiniciar</b> : Limpiar tu historial para volver a jugar\n"
        "🔹 <b>/donar</b> : Apoyar el proyecto en Cafecito\n\n"
        "<b>⏱️ Reglas:</b> Cuentas con 15s por pregunta en cuenta regresiva. Si llega a 0s pasa a la siguiente descontando 1 punto."
    )
    
    keyboard = [
        [InlineKeyboardButton("🎮 Jugar Quiz", callback_data="menu_quiz")],
        [InlineKeyboardButton("📊 Ranking General", callback_data="menu_rank_gen")],
        [InlineKeyboardButton("☕ Donar con Cafecito", url=CAFECITO_URL)]
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
    for cat in QUIZ_DATA["categorias"]:
        keyboard.append([InlineKeyboardButton(cat["nombre"], callback_data=f"playcat_{cat['id']}")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    texto = (
        "<b>🎯 ────────────────────────── 🎯</b>\n"
        "<b>🗂️ SELECCIONA UNA CATEGORÍA 🗂️</b>\n"
        "<b>🎯 ────────────────────────── 🎯</b>\n\n"
        "<i>Elige un tema para iniciar una ronda de 5 preguntas:</i>"
    )
    if update.message:
        await update.message.reply_text(texto, parse_mode="HTML", reply_markup=reply_markup)
    else:
        await update.callback_query.edit_message_text(texto, parse_mode="HTML", reply_markup=reply_markup)

async def manejar_pregunta(query, context, cat_id: str, idx: int):
    preguntas = context.user_data.get("preguntas_quiz", [])
    categoria = next((c for c in QUIZ_DATA["categorias"] if c["id"] == cat_id), None)
    
    if not categoria or idx >= len(preguntas):
        await query.message.reply_text(
            "<b>🎉 ────────────────────────── 🎉</b>\n"
            "<b>¡HAS COMPLETADO TU RONDA!</b>\n"
            "<b>🎉 ────────────────────────── 🎉</b>\n\n"
            "<i>Consulta tus puntos actualizados usando /ranking_cat o /ranking_gen</i>",
            parse_mode="HTML"
        )
        context.user_data.pop("preguntas_quiz", None)
        return

    pregunta_obj = preguntas[idx]
    
    opciones = pregunta_obj["opciones"].copy()
    random.shuffle(opciones)
    
    keyboard = []
    for opc in opciones:
        cb_data = f"ans_{cat_id}_{idx}_{opc}"
        keyboard.append([InlineKeyboardButton(opc, callback_data=cb_data)])
        
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    tiempo_inicial = 15
    texto_pregunta = (
        f"<b>📋 Categoría:</b> {categoria['nombre']}\n"
        f"<b>❓ Pregunta {idx+1}/{len(preguntas)}:</b>\n\n"
        f"<b>{pregunta_obj['pregunta']}</b>\n\n"
        f"⏳ <b>Tiempo restante:</b> <code>{tiempo_inicial}s</code>"
    )

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
        texto_actualizado = (
            f"<b>📋 Categoría:</b> {categoria['nombre']}\n"
            f"<b>❓ Pregunta {idx+1}/{len(preguntas)}:</b>\n\n"
            f"<b>{pregunta_obj['pregunta']}</b>\n\n"
            f"⏳ <b>Tiempo restante:</b> <code>{tiempo_actual}s</code>"
        )
        
        keyboard = []
        for opc in pregunta_obj["opciones"]:
            cb_data = f"ans_{cat_id}_{idx}_{opc}"
            keyboard.append([InlineKeyboardButton(opc, callback_data=cb_data)])
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
        
        texto_expirado = (
            "<b>⏰ ────────────────────────── ⏰</b>\n"
            "<b>¡TIEMPO AGOTADO! ❌ (-1 Punto)</b>\n"
            "<b>⏰ ────────────────────────── ⏰</b>"
        )
        
        try:
            if job_data["tiene_foto"]:
                await context.bot.edit_message_caption(chat_id=chat_id, message_id=message_id, caption=texto_expirado, parse_mode="HTML")
            else:
                await context.bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=texto_expirado, parse_mode="HTML")
        except Exception:
            pass

        await asyncio.sleep(2)
        await manejar_pregunta(job_data["query"], context, cat_id, idx + 1)

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

    preguntas = context.user_data.get("preguntas_quiz", [])
    if idx >= len(preguntas):
        return
        
    pregunta_obj = preguntas[idx]
    db.registrar_pregunta_respondida(query.from_user.id, pregunta_obj["id"])
    
    if respuesta == pregunta_obj["respuesta_correcta"]:
        db.actualizar_puntaje(query.from_user.id, cat_id, es_correcto=True)
        resultado = "<b>✅ ¡RESPUESTA CORRECTA! (+1 Punto)</b>"
    else:
        db.actualizar_puntaje(query.from_user.id, cat_id, es_correcto=False)
        resultado = f"<b>❌ RESPUESTA INCORRECTA (-1 Punto)</b>\n<i>Correcta: {pregunta_obj['respuesta_correcta']}</i>"

    await query.edit_message_caption(
        caption=resultado, parse_mode="HTML"
    ) if query.message.photo else await query.edit_message_text(
        text=resultado, parse_mode="HTML"
    )

    await asyncio.sleep(2)
    await manejar_pregunta(query, context, cat_id, idx + 1)

async def comando_ranking_gen(update: Update, context: ContextTypes.DEFAULT_TYPE):
    ranking = db.obtener_ranking_general()
    
    texto = (
        "<b>🏆 ────────────────────────── 🏆</b>\n"
        "<b>📊 RANKING GENERAL DE JUGADORES 📊</b>\n"
        "<b>🏆 ────────────────────────── 🏆</b>\n\n"
    )
    
    if not ranking:
        texto += "<i>Aún no hay puntos registrados en el juego.</i>"
    else:
        for pos, row in enumerate(ranking, start=1):
            nombre, pos_pts, neg_pts, total = row
            pos_pts = pos_pts or 0
            neg_pts = neg_pts or 0
            total = total or 0
            
            signo = "-" if total < 0 else ""
            texto += (
                f"<b>{pos}. {nombre}</b>\n"
                f"   🔵 Positivas: {pos_pts} | 🔴 Negativas: -{neg_pts}\n"
                f"   ⭐ Total: <b>{signo}{abs(total)} pts</b>\n\n"
            )

    if update.message:
        await update.message.reply_text(texto, parse_mode="HTML")
    else:
        await update.callback_query.edit_message_text(texto, parse_mode="HTML")

async def comando_ranking_cat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = []
    for cat in QUIZ_DATA["categorias"]:
        keyboard.append([InlineKeyboardButton(cat["nombre"], callback_data=f"showrankcat_{cat['id']}")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    texto = (
        "<b>🏅 ────────────────────────── 🏅</b>\n"
        "<b>📊 RANKING POR CATEGORÍA 📊</b>\n"
        "<b>🏅 ────────────────────────── 🏅</b>\n\n"
        "<i>Selecciona una categoría para ver sus posiciones:</i>"
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
    
    texto = (
        f"<b>🏅 RANKING: {categoria['nombre']} 🏅</b>\n"
        "<b>─────────────────────────────</b>\n\n"
    )
    
    if not ranking:
        texto += "<i>No hay puntos registrados en esta categoría aún.</i>"
    else:
        for pos, row in enumerate(ranking, start=1):
            nombre, pos_pts, neg_pts, total = row
            pos_pts = pos_pts or 0
            neg_pts = neg_pts or 0
            total = total or 0
            
            signo = "-" if total < 0 else ""
            texto += (
                f"<b>{pos}. {nombre}</b>\n"
                f"   🔵 Positivas: {pos_pts} | 🔴 Negativas: -{neg_pts}\n"
                f"   ⭐ Total: <b>{signo}{abs(total)} pts</b>\n\n"
            )

    await query.edit_message_text(texto, parse_mode="HTML")

async def comando_reiniciar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    db.reiniciar_historial_usuario(user_id)
    await update.message.reply_text(
        "<b>🔄 ────────────────────────── 🔄</b>\n"
        "<b>¡HISTORIAL REINICIADO!</b>\n"
        "<b>🔄 ────────────────────────── 🔄</b>\n\n"
        "<i>Se ha limpiado tu registro de preguntas respondidas. Ahora puedes volver a jugar todas las categorías desde cero.</i>",
        parse_mode="HTML"
    )

async def comando_donar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [[InlineKeyboardButton("☕ Invítame un Cafecito", url=CAFECITO_URL)]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    texto = (
        "<b>☕ ────────────────────────── ☕</b>\n"
        "<b>APOYA AL PROYECTO EDUCATIVO</b>\n"
        "<b>☕ ────────────────────────── ☕</b>\n\n"
        "<i>Si disfrutas aprendiendo con este Bot, puedes colaborar invitándonos un Cafecito para financiar el mantenimiento y agregar más contenido.</i>\n\n"
        "<b>¡Muchas gracias por tu apoyo! ❤️</b>"
    )
    if update.message:
        await update.message.reply_text(texto, parse_mode="HTML", reply_markup=reply_markup)
    else:
        await update.callback_query.edit_message_text(texto, parse_mode="HTML", reply_markup=reply_markup)

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
                    "<b>🎓 ────────────────────────── 🎓</b>\n"
                    "<b>¡FELICITACIONES! 🎉</b>\n"
                    "<b>🎓 ────────────────────────── 🎓</b>\n\n"
                    "<i>Ya has respondido todas las preguntas de esta categoría.</i>\n\n"
                    "Usa /reiniciar para volver a jugar esta categoría o elige otra disponible.",
                    parse_mode="HTML"
                )
                return

            random.shuffle(preguntas_disponibles)
            ronda_preguntas = preguntas_disponibles[:5]
            context.user_data["preguntas_quiz"] = ronda_preguntas
            
        await manejar_pregunta(query, context, cat_id, 0)
    elif data.startswith("ans_"):
        await procesar_respuesta(update, context)
    elif data.startswith("showrankcat_"):
        await mostrar_ranking_cat_seleccionado(update, context)

def main():
    db.init_db()
    
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
    