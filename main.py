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

# Servidor Flask para mantener el servicio activo en el plan Free de Render
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

# ... (MANTÉN AQUÍ TODO TU CÓDIGO EXISTENTE DE QUIZ_DATA, COMANDOS Y CALLBACKS) ...

def main():
    db.init_db()
    
    # Inicia el servidor web en segundo plano
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
