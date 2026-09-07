import os
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

def get_connection():
    """Establece conexión con la base de datos de Supabase."""
    if not DATABASE_URL:
        raise ValueError("❌ ERROR: DATABASE_URL no está configurada en las variables de entorno.")
    return psycopg2.connect(DATABASE_URL)

def init_db():
    """Crea las tablas necesarias en Supabase si no existen."""
    conn = get_connection()
    cursor = conn.cursor()
    
    # Tabla de usuarios
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS usuarios (
            user_id BIGINT PRIMARY KEY,
            username VARCHAR(255),
            first_name VARCHAR(255)
        );
    """)
    
    # Tabla de puntajes por categoría
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS puntajes (
            user_id BIGINT REFERENCES usuarios(user_id) ON DELETE CASCADE,
            categoria_id VARCHAR(100),
            puntos_positivos INT DEFAULT 0,
            puntos_negativos INT DEFAULT 0,
            total_puntos INT DEFAULT 0,
            PRIMARY KEY (user_id, categoria_id)
        );
    """)
    
    # Tabla de registro de preguntas respondidas
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS preguntas_respondidas (
            user_id BIGINT REFERENCES usuarios(user_id) ON DELETE CASCADE,
            pregunta_id VARCHAR(100),
            PRIMARY KEY (user_id, pregunta_id)
        );
    """)
    
    conn.commit()
    cursor.close()
    conn.close()

def registrar_o_actualizar_usuario(user_id: int, username: str, first_name: str):
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        INSERT INTO usuarios (user_id, username, first_name)
        VALUES (%s, %s, %s)
        ON CONFLICT (user_id) 
        DO UPDATE SET username = EXCLUDED.username, first_name = EXCLUDED.first_name;
    """, (user_id, username, first_name))
    
    conn.commit()
    cursor.close()
    conn.close()

def actualizar_puntaje(user_id: int, categoria_id: str, es_correcto: bool):
    conn = get_connection()
    cursor = conn.cursor()
    
    pos_inc = 1 if es_correcto else 0
    neg_inc = 0 if es_correcto else 1
    puntos_delta = 1 if es_correcto else -1

    cursor.execute("""
        INSERT INTO puntajes (user_id, categoria_id, puntos_positivos, puntos_negativos, total_puntos)
        VALUES (%s, %s, %s, %s, %s)
        ON CONFLICT (user_id, categoria_id) 
        DO UPDATE SET 
            puntos_positivos = puntajes.puntos_positivos + EXCLUDED.puntos_positivos,
            puntos_negativos = puntajes.puntos_negativos + EXCLUDED.puntos_negativos,
            total_puntos = puntajes.total_puntos + %s;
    """, (user_id, categoria_id, pos_inc, neg_inc, puntos_delta, puntos_delta))
    
    conn.commit()
    cursor.close()
    conn.close()

def registrar_pregunta_respondida(user_id: int, pregunta_id: str):
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        INSERT INTO preguntas_respondidas (user_id, pregunta_id)
        VALUES (%s, %s)
        ON CONFLICT DO NOTHING;
    """, (user_id, pregunta_id))
    
    conn.commit()
    cursor.close()
    conn.close()

def obtener_ids_preguntas_respondidas(user_id: int) -> list:
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT pregunta_id FROM preguntas_respondidas WHERE user_id = %s;
    """, (user_id,))
    
    rows = cursor.fetchall()
    cursor.close()
    conn.close()
    return [r[0] for r in rows]

def obtener_ranking_general():
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT 
            COALESCE(u.first_name, u.username, 'Anónimo') AS nombre,
            SUM(p.puntos_positivos) AS pos,
            SUM(p.puntos_negativos) AS neg,
            SUM(p.total_puntos) AS total
        FROM puntajes p
        JOIN usuarios u ON u.user_id = p.user_id
        GROUP BY u.user_id, u.first_name, u.username
        ORDER BY total DESC;
    """)
    
    rows = cursor.fetchall()
    cursor.close()
    conn.close()
    return rows

def obtener_ranking_categoria(categoria_id: str):
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT 
            COALESCE(u.first_name, u.username, 'Anónimo') AS nombre,
            p.puntos_positivos AS pos,
            p.puntos_negativos AS neg,
            p.total_puntos AS total
        FROM puntajes p
        JOIN usuarios u ON u.user_id = p.user_id
        WHERE p.categoria_id = %s
        ORDER BY p.total_puntos DESC;
    """, (categoria_id,))
    
    rows = cursor.fetchall()
    cursor.close()
    conn.close()
    return rows

def reiniciar_historial_usuario(user_id: int):
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute("DELETE FROM preguntas_respondidas WHERE user_id = %s;", (user_id,))
    
    conn.commit()
    cursor.close()
    conn.close()
    
