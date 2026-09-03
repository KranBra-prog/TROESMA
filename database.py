import sqlite3

DB_NAME = "quiz_game.db"

def init_db():
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS usuarios (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                nombre TEXT
            )
        """)
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS puntajes (
                user_id INTEGER,
                categoria_id TEXT,
                puntos_positivos INTEGER DEFAULT 0,
                puntos_negativos INTEGER DEFAULT 0,
                PRIMARY KEY (user_id, categoria_id),
                FOREIGN KEY (user_id) REFERENCES usuarios(user_id)
            )
        """)
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS preguntas_respondidas (
                user_id INTEGER,
                pregunta_id INTEGER,
                PRIMARY KEY (user_id, pregunta_id)
            )
        """)
        conn.commit()

def registrar_o_actualizar_usuario(user_id: int, username: str, nombre: str):
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO usuarios (user_id, username, nombre)
            VALUES (?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET username=?, nombre=?
        """, (user_id, username, nombre, username, nombre))
        conn.commit()

def actualizar_puntaje(user_id: int, categoria_id: str, es_correcto: bool):
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        field = "puntos_positivos" if es_correcto else "puntos_negativos"
            
        cursor.execute(f"""
            INSERT INTO puntajes (user_id, categoria_id, {field})
            VALUES (?, ?, 1)
            ON CONFLICT(user_id, categoria_id) DO UPDATE SET {field} = {field} + 1
        """, (user_id, categoria_id))
        conn.commit()

def registrar_pregunta_respondida(user_id: int, pregunta_id: int):
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT OR IGNORE INTO preguntas_respondidas (user_id, pregunta_id)
            VALUES (?, ?)
        """, (user_id, pregunta_id))
        conn.commit()

def obtener_ids_preguntas_respondidas(user_id: int) -> set:
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT pregunta_id FROM preguntas_respondidas WHERE user_id = ?", (user_id,))
        rows = cursor.fetchall()
        return {row[0] for row in rows}

def reiniciar_historial_usuario(user_id: int):
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM preguntas_respondidas WHERE user_id = ?", (user_id,))
        conn.commit()

def obtener_ranking_general():
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT u.nombre, 
                   SUM(p.puntos_positivos) as pos, 
                   SUM(p.puntos_negativos) as neg,
                   (SUM(p.puntos_positivos) - SUM(p.puntos_negativos)) as total
            FROM puntajes p
            JOIN usuarios u ON p.user_id = u.user_id
            GROUP BY p.user_id
            ORDER BY total DESC
            LIMIT 10
        """)
        return cursor.fetchall()

def obtener_ranking_categoria(categoria_id: str):
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT u.nombre, 
                   p.puntos_positivos, 
                   p.puntos_negativos,
                   (p.puntos_positivos - p.puntos_negativos) as total
            FROM puntajes p
            JOIN usuarios u ON p.user_id = u.user_id
            WHERE p.categoria_id = ?
            ORDER BY total DESC
            LIMIT 10
        """, (categoria_id,))
        return cursor.fetchall()
    