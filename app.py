from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import sqlite3
import os
import shutil
from datetime import datetime, timedelta
import logging
from typing import Optional, Dict, List
import traceback

app = Flask(__name__)
CORS(app)

# =============================================
# CONFIGURACIÓN GENERAL
# =============================================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATABASE = os.path.join(BASE_DIR, 'sensory_club.db')
BACKUP_DIR = os.path.join(BASE_DIR, 'backups')

os.makedirs(BACKUP_DIR, exist_ok=True)

# Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(os.path.join(BASE_DIR, 'sensory_club.log')),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# =============================================
# CONFIGURAR RUTA DEL FRONTEND (LINUX)
# =============================================
FRONTEND_DIR = r"/root/Downloads/sensoryclub/Sensoryclud/fronted"

print(f"[INFO] Frontend cargado desde: {FRONTEND_DIR}")

# =============================================
# RUTAS PARA SERVIR EL FRONTEND
# =============================================
@app.route('/')
def serve_frontend():
    return send_from_directory(FRONTEND_DIR, "f64996808_Sens_ry_Club.html")

@app.route('/<path:path>')
def serve_static(path):
    return send_from_directory(FRONTEND_DIR, path)

# =============================================
# PRECIOS Y CONFIGURACIONES - ACTUALIZADOS
# =============================================
PRECIOS = {
    'semana': {
        10: 10,
        15: 15,
        20: 20,
        30: 25,
        60: 40
    },
    'fin_semana': {
        10: 10,
        15: 15,
        20: 20,
        30: 25,
        60: 50
    }
}

GENEROS = ['Masculino', 'Femenino']

CATEGORIAS_GASTOS = [
    'materiales', 'servicios', 'alquiler',
    'sueldos', 'mantenimiento', 'otros'
]

# =============================================
# FUNCIONES AUXILIARES - ACTUALIZADAS
# =============================================
def get_db_connection():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

def safe_str(value):
    if value is None:
        return ""
    return str(value).strip()

def safe_int(value, default=0):
    try:
        return int(value)
    except:
        return default

def safe_float(value, default=0.0):
    try:
        return float(value)
    except:
        return default

def safe_convert_id(user_id):
    if user_id is None:
        return None
    if isinstance(user_id, int):
        return user_id
    if isinstance(user_id, str):
        cleaned = ''.join(c for c in user_id if c.isdigit() or c == '-')
        if cleaned.isdigit() or (cleaned.startswith('-') and cleaned[1:].isdigit()):
            return int(cleaned)
    return None

def calcular_precio(minutos, fecha=None, es_cumpleanos=False, es_6ta_visita=False):
    if fecha is None:
        fecha = datetime.now()

    # ✅ CORREGIDO: Sistema de visitas gratis
    if es_6ta_visita:
        return 0  # 6ta visita es GRATIS
    if es_cumpleanos and minutos in [10, 30]:
        return 0  # Cumpleaños: 10 y 30 min GRATIS

    dia_semana = fecha.weekday()
    es_fin_semana = dia_semana >= 4  # Viernes, Sábado, Domingo

    precios = PRECIOS['fin_semana'] if es_fin_semana else PRECIOS['semana']
    return precios.get(minutos, 0)

def obtener_nombre_dia(fecha=None):
    if fecha is None:
        fecha = datetime.now()
    dias = ['Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes', 'Sábado', 'Domingo']
    return dias[fecha.weekday()]

def es_fin_de_semana(fecha=None):
    if fecha is None:
        fecha = datetime.now()
    return fecha.weekday() >= 4  # Viernes, Sábado, Domingo

def es_cumpleanos(nino_fecha_nacimiento):
    if not nino_fecha_nacimiento:
        return False
    try:
        fecha_nac = datetime.strptime(nino_fecha_nacimiento, '%Y-%m-%d').date()
        hoy = datetime.now().date()
        return fecha_nac.month == hoy.month and fecha_nac.day == hoy.day
    except:
        return False

def es_6ta_visita(sesiones_totales):
    return sesiones_totales > 0 and (sesiones_totales + 1) % 6 == 0

# =============================================
# INICIALIZACIÓN DE BASE DE DATOS
# =============================================
def init_db():
    conn = None
    try:
        conn = sqlite3.connect(DATABASE)
        cursor = conn.cursor()

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS ninos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                dni TEXT UNIQUE,
                nombre_completo TEXT NOT NULL,
                edad INTEGER DEFAULT 0,
                meses INTEGER DEFAULT 0,
                fecha_nacimiento TEXT,
                genero TEXT,
                nombre_apoderado TEXT,
                telefono_mama TEXT,
                telefono_papa TEXT,
                distrito TEXT,
                fecha_registro TEXT DEFAULT CURRENT_TIMESTAMP,
                ultima_visita TEXT,
                estado TEXT DEFAULT 'Inactivo',
                sesiones_totales INTEGER DEFAULT 0,
                sesiones_pagadas INTEGER DEFAULT 0,
                minutos_asignados INTEGER DEFAULT 0
            )
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS observaciones (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                usuario_id INTEGER NOT NULL,
                nombre TEXT NOT NULL,
                fecha TEXT DEFAULT CURRENT_TIMESTAMP,
                observacion TEXT NOT NULL
            )
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS visitas (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                usuario_id INTEGER NOT NULL,
                nombre TEXT NOT NULL,
                minutos INTEGER NOT NULL,
                precio REAL NOT NULL,
                fecha TEXT DEFAULT CURRENT_TIMESTAMP,
                dia TEXT,
                es_fin_semana BOOLEAN DEFAULT FALSE,
                es_gratis BOOLEAN DEFAULT FALSE,
                tipo_tarifa TEXT DEFAULT 'normal',
                es_cumpleanos BOOLEAN DEFAULT FALSE,
                es_6ta_visita BOOLEAN DEFAULT FALSE,
                motivo_gratis TEXT
            )
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS ganancias_diarias (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                fecha TEXT NOT NULL UNIQUE,
                dia_semana TEXT NOT NULL,
                total_ingresos REAL DEFAULT 0,
                total_visitas INTEGER DEFAULT 0,
                visitas_gratis INTEGER DEFAULT 0,
                visitas_pagadas INTEGER DEFAULT 0,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS gastos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                descripcion TEXT NOT NULL,
                monto REAL NOT NULL,
                categoria TEXT NOT NULL,
                fecha TEXT DEFAULT CURRENT_TIMESTAMP,
                dia TEXT,
                observaciones TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        cursor.execute('CREATE INDEX IF NOT EXISTS idx_visitas_fecha ON visitas(fecha)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_ganancias_fecha ON ganancias_diarias(fecha)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_gastos_fecha ON gastos(fecha)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_ninos_nombre ON ninos(nombre_completo)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_ninos_dni ON ninos(dni)')

        conn.commit()
        logger.info("✅ Base de datos inicializada correctamente")

    except Exception as e:
        logger.error(f"❌ Error inicializando base de datos: {e}")
        logger.error(traceback.format_exc())
    finally:
        if conn:
            conn.close()

# =============================================
# ENDPOINT PARA ACTUALIZAR BASE DE DATOS
# =============================================
@app.route('/api/actualizar-bd', methods=['POST'])
def actualizar_bd():
    """Endpoint para actualizar el esquema de la base de datos"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Verificar si existen las columnas nuevas
        cursor.execute("PRAGMA table_info(visitas)")
        columnas_existentes = [col[1] for col in cursor.fetchall()]
        
        columnas_faltantes = []
        
        # Agregar columnas faltantes
        if 'es_cumpleanos' not in columnas_existentes:
            cursor.execute('ALTER TABLE visitas ADD COLUMN es_cumpleanos BOOLEAN DEFAULT FALSE')
            columnas_faltantes.append('es_cumpleanos')
            logger.info("✅ Columna 'es_cumpleanos' agregada a la tabla visitas")
        
        if 'es_6ta_visita' not in columnas_existentes:
            cursor.execute('ALTER TABLE visitas ADD COLUMN es_6ta_visita BOOLEAN DEFAULT FALSE')
            columnas_faltantes.append('es_6ta_visita')
            logger.info("✅ Columna 'es_6ta_visita' agregada a la tabla visitas")
        
        if 'motivo_gratis' not in columnas_existentes:
            cursor.execute('ALTER TABLE visitas ADD COLUMN motivo_gratis TEXT')
            columnas_faltantes.append('motivo_gratis')
            logger.info("✅ Columna 'motivo_gratis' agregada a la tabla visitas")
        
        if 'tipo_tarifa' not in columnas_existentes:
            cursor.execute('ALTER TABLE visitas ADD COLUMN tipo_tarifa TEXT DEFAULT "normal"')
            columnas_faltantes.append('tipo_tarifa')
            logger.info("✅ Columna 'tipo_tarifa' agregada a la tabla visitas")
        
        conn.commit()
        conn.close()
        
        if columnas_faltantes:
            return jsonify({
                'success': True,
                'message': f'Base de datos actualizada. Columnas agregadas: {", ".join(columnas_faltantes)}',
                'columnas_agregadas': columnas_faltantes
            }), 200
        else:
            return jsonify({
                'success': True,
                'message': 'La base de datos ya está actualizada',
                'columnas_agregadas': []
            }), 200
            
    except Exception as e:
        logger.error(f"❌ ERROR actualizando base de datos: {e}")
        logger.error(traceback.format_exc())
        return jsonify({'error': f'Error actualizando base de datos: {str(e)}'}), 500

# =============================================
# FUNCIONES DE GANANCIAS - CORREGIDAS
# =============================================
def actualizar_ganancias_diarias(fecha_visita, precio, es_gratis):
    """Actualiza las ganancias diarias cuando se registra una visita"""
    conn = None
    try:
        conn = get_db_connection()
        
        # Formatear fecha para agrupar por día
        fecha_str = fecha_visita.date().isoformat()
        dia_semana = obtener_nombre_dia(fecha_visita)
        
        # Verificar si ya existe registro para este día
        ganancia_existente = conn.execute(
            'SELECT * FROM ganancias_diarias WHERE fecha = ?', 
            (fecha_str,)
        ).fetchone()
        
        if ganancia_existente:
            # Actualizar registro existente
            nuevo_total = ganancia_existente['total_ingresos'] + precio
            nuevas_visitas = ganancia_existente['total_visitas'] + 1
            nuevas_gratis = ganancia_existente['visitas_gratis'] + (1 if es_gratis else 0)
            nuevas_pagadas = ganancia_existente['visitas_pagadas'] + (0 if es_gratis else 1)
            
            conn.execute('''
                UPDATE ganancias_diarias SET
                    total_ingresos = ?,
                    total_visitas = ?,
                    visitas_gratis = ?,
                    visitas_pagadas = ?,
                    updated_at = ?
                WHERE fecha = ?
            ''', (nuevo_total, nuevas_visitas, nuevas_gratis, nuevas_pagadas, 
                  datetime.now().isoformat(), fecha_str))
        else:
            # Crear nuevo registro
            conn.execute('''
                INSERT INTO ganancias_diarias 
                (fecha, dia_semana, total_ingresos, total_visitas, visitas_gratis, visitas_pagadas)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (fecha_str, dia_semana, precio, 1, 1 if es_gratis else 0, 0 if es_gratis else 1))
        
        conn.commit()
        logger.info(f"✅ Ganancias diarias actualizadas para {fecha_str} - Precio: {precio}, Gratis: {es_gratis}")
        
    except Exception as e:
        logger.error(f"❌ ERROR actualizando ganancias diarias: {e}")
        logger.error(traceback.format_exc())
    finally:
        if conn:
            conn.close()

# =============================================
# ENDPOINTS DE USUARIOS - CORREGIDOS
# =============================================

@app.route('/api/registrar', methods=['POST'])
def registrar_usuario():
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'Datos JSON requeridos'}), 400
        
        nombre_completo = data.get('nombre', '').strip()
        if not nombre_completo:
            return jsonify({'error': 'El nombre completo es obligatorio'}), 400
        
        conn = get_db_connection()
        
        # Verificar si ya existe un niño con el mismo DNI
        dni = safe_str(data.get('dni', ''))
        if dni:
            existente = conn.execute('SELECT * FROM ninos WHERE dni = ?', (dni,)).fetchone()
            if existente:
                conn.close()
                return jsonify({'error': 'Ya existe un niño registrado con este DNI'}), 400
        
        if not dni:
            dni = None
        
        genero = safe_str(data.get('genero', ''))
        if genero and genero not in GENEROS:
            genero = None
        
        # Insertar niño
        cursor = conn.execute('''
            INSERT INTO ninos (
                dni, nombre_completo, edad, meses, fecha_nacimiento, genero,
                nombre_apoderado, telefono_mama, telefono_papa, distrito, estado,
                minutos_asignados, sesiones_totales, sesiones_pagadas
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            dni,
            nombre_completo,
            safe_int(data.get('edad', 0)),
            safe_int(data.get('meses', 0)),
            data.get('fecha_nacimiento') or None,
            genero,
            safe_str(data.get('nombre_apoderado', '')) or None,
            safe_str(data.get('telefono_mama', '')) or None,
            safe_str(data.get('telefono_papa', '')) or None,
            safe_str(data.get('distrito', '')) or None,
            'Inactivo',  # estado
            0,  # minutos_asignados
            0,  # sesiones_totales  
            0   # sesiones_pagadas
        ))
        
        nino_id = cursor.lastrowid
        conn.commit()
        
        # Obtener el niño recién creado
        nino = conn.execute('SELECT * FROM ninos WHERE id = ?', (nino_id,)).fetchone()
        conn.close()
        
        nino_dict = dict(nino)
        
        return jsonify({
            'success': True, 
            'usuario': nino_dict,
            'message': 'Niño registrado exitosamente'
        }), 200

    except Exception as e:
        logger.error(f"❌ ERROR registrando usuario: {e}")
        logger.error(traceback.format_exc())
        return jsonify({'error': 'Error interno al registrar usuario'}), 500

@app.route('/api/actualizar-nino', methods=['POST'])
def actualizar_nino():
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'Datos JSON requeridos'}), 400
            
        logger.info(f"Datos recibidos para actualizar niño: {data}")
        
        nino_id = safe_convert_id(data.get('id'))
        if not nino_id:
            return jsonify({'error': 'ID del niño es requerido'}), 400
        
        conn = get_db_connection()
        
        # Verificar que el niño existe
        nino_existente = conn.execute('SELECT * FROM ninos WHERE id = ?', (nino_id,)).fetchone()
        if not nino_existente:
            conn.close()
            return jsonify({'error': 'Niño no encontrado'}), 404
        
        # Validar género
        genero = safe_str(data.get('genero', ''))
        if genero and genero not in GENEROS:
            genero = None
        
        # Obtener DNI actual para preservarlo si es necesario
        dni_actual = nino_existente['dni']
        dni_nuevo = safe_str(data.get('dni', ''))
        
        # ✅ CORREGIDO: Si el nuevo DNI está vacío, mantener el actual o usar NULL
        if not dni_nuevo:
            if dni_actual and dni_actual.startswith('SIN-DNI'):
                # Si el DNI actual es temporal, cambiarlo a NULL
                dni_final = None
            else:
                # Mantener el DNI actual si es válido
                dni_final = dni_actual
        else:
            # Usar el nuevo DNI proporcionado
            dni_final = dni_nuevo

        # Actualizar el niño
        conn.execute('''
            UPDATE ninos SET
                dni = ?, nombre_completo = ?, edad = ?, meses = ?, 
                fecha_nacimiento = ?, genero = ?, nombre_apoderado = ?,
                telefono_mama = ?, telefono_papa = ?, distrito = ?
            WHERE id = ?
        ''', (
            dni_final,
            safe_str(data.get('nombre', data.get('nombre_completo', ''))),
            safe_int(data.get('edad', 0)),
            safe_int(data.get('meses', 0)),
            data.get('fecha_nacimiento') or None,
            genero,
            safe_str(data.get('nombre_apoderado', '')) or None,
            safe_str(data.get('telefono_mama', '')) or None,
            safe_str(data.get('telefono_papa', '')) or None,
            safe_str(data.get('distrito', '')) or None,
            nino_id
        ))
        
        conn.commit()
        
        # Obtener datos actualizados del niño
        nino_actualizado = conn.execute('SELECT * FROM ninos WHERE id = ?', (nino_id,)).fetchone()
        conn.close()
        
        logger.info(f"✅ Niño actualizado exitosamente - ID: {nino_id}")
        
        return jsonify({
            'success': True,
            'nino': dict(nino_actualizado),
            'message': 'Datos del niño actualizados correctamente'
        }), 200
        
    except Exception as e:
        logger.error(f"❌ ERROR actualizando niño: {e}")
        logger.error(traceback.format_exc())
        return jsonify({'error': f'Error interno al actualizar datos del niño: {str(e)}'}), 500

# =============================================
# ENDPOINTS DE CONSULTA
# =============================================

@app.route('/api/usuarios', methods=['GET'])
def get_usuarios():
    try:
        conn = get_db_connection()
        ninos = conn.execute('''
            SELECT * FROM ninos 
            ORDER BY nombre_completo
        ''').fetchall()
        
        usuarios_formateados = [dict(nino) for nino in ninos]
        conn.close()
        
        return jsonify(usuarios_formateados)
    except Exception as e:
        logger.error(f"❌ ERROR obteniendo usuarios: {e}")
        logger.error(traceback.format_exc())
        return jsonify({'error': 'Error interno al obtener usuarios'}), 500

@app.route('/api/nino/<int:nino_id>', methods=['GET'])
def get_nino_completo(nino_id):
    try:
        conn = get_db_connection()
        
        nino = conn.execute('SELECT * FROM ninos WHERE id = ?', (nino_id,)).fetchone()
        if not nino:
            return jsonify({'error': 'Niño no encontrado'}), 404
        
        conn.close()
        
        return jsonify({
            'nino': dict(nino)
        }), 200
        
    except Exception as e:
        logger.error(f"❌ ERROR obteniendo niño completo: {e}")
        logger.error(traceback.format_exc())
        return jsonify({'error': 'Error interno'}), 500

# =============================================
# ENDPOINT DE BÚSQUEDA MEJORADO
# =============================================

@app.route('/api/buscar', methods=['POST'])
def buscar_usuario():
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'Datos JSON requeridos'}), 400
            
        termino = safe_str(data.get('termino', ''))
        
        if not termino:
            return jsonify({'error': 'Término de búsqueda requerido'}), 400
        
        conn = get_db_connection()
        
        # ✅ CORREGIDO: Buscar tanto por DNI como por nombre completo
        ninos = conn.execute('''
            SELECT * FROM ninos 
            WHERE (nombre_completo LIKE ? OR dni LIKE ?)
            ORDER BY 
                CASE 
                    WHEN nombre_completo LIKE ? THEN 1
                    WHEN dni LIKE ? THEN 2
                    ELSE 3
                END,
                nombre_completo
        ''', (
            f'%{termino}%', 
            f'%{termino}%',
            f'%{termino}%',
            f'%{termino}%'
        )).fetchall()
        
        resultados = [dict(nino) for nino in ninos]
        
        conn.close()
        
        logger.info(f"✅ Búsqueda realizada - Término: '{termino}', Resultados: {len(resultados)}")
        
        return jsonify(resultados), 200
        
    except Exception as e:
        logger.error(f"❌ ERROR buscando usuario: {e}")
        logger.error(traceback.format_exc())
        return jsonify({'error': 'Error interno al buscar usuario'}), 500

# =============================================
# ENDPOINT FINALIZAR VISITA - COMPLETAMENTE CORREGIDO
# =============================================

@app.route('/api/finalizar-visita', methods=['POST'])
def finalizar_visita():
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'Datos JSON requeridos'}), 400

        usuario_id = data.get('id')
        minutos_utilizados = safe_int(data.get('minutos_utilizados', 0))
        visita_gratis = data.get('visita_gratis', False)
        precio_proporcionado = safe_float(data.get('precio', 0))

        logger.info(f"Finalizando visita - usuario_id: {usuario_id}, minutos: {minutos_utilizados}, gratis: {visita_gratis}, precio_proporcionado: {precio_proporcionado}")

        if not usuario_id:
            logger.error("❌ ERROR: usuario_id es null o vacío en finalizar-visita")
            return jsonify({'error': 'ID de usuario es requerido'}), 400

        conn = get_db_connection()

        # Convertir ID de forma segura
        usuario_id_int = safe_convert_id(usuario_id)
        if not usuario_id_int:
            conn.close()
            logger.error(f"❌ ERROR: ID de usuario inválido - recibido: {usuario_id}")
            return jsonify({'error': 'ID de usuario inválido'}), 400

        # Buscar usuario
        usuario = conn.execute(
            'SELECT * FROM ninos WHERE id = ?', 
            (usuario_id_int,)
        ).fetchone()
        if not usuario:
            conn.close()
            return jsonify({'error': 'Niño no encontrado'}), 404

        # ⚡ Lógica de cálculo CORREGIDA
        fecha_actual = datetime.now()
        es_cumple = es_cumpleanos(usuario['fecha_nacimiento'])
        es_6ta = es_6ta_visita(usuario['sesiones_totales'] or 0)

        # ✅ CALCULAR PRECIO CORRECTAMENTE
        if visita_gratis:
            precio_calculado = 0
        elif precio_proporcionado > 0:
            precio_calculado = precio_proporcionado
        else:
            precio_calculado = calcular_precio(minutos_utilizados, fecha_actual, es_cumple, es_6ta)

        es_gratis_final = precio_calculado == 0

        # Motivo gratis
        if es_gratis_final:
            if es_cumple and minutos_utilizados in [10, 30]:
                motivo_gratis = f"Cumpleaños - {minutos_utilizados} min gratis"
            elif es_6ta:
                motivo_gratis = f"6ta visita - {minutos_utilizados} min gratis"
            elif visita_gratis:
                motivo_gratis = "Visita gratuita manual"
            else:
                motivo_gratis = "Gratis por configuración de precio"
        else:
            motivo_gratis = None

        precio_guardar = 0.0 if es_gratis_final else precio_calculado

        # Actualizar sesiones del usuario
        sesiones_totales_actuales = usuario['sesiones_totales'] or 0
        sesiones_pagadas_actuales = usuario['sesiones_pagadas'] or 0

        nuevas_sesiones_totales = sesiones_totales_actuales + 1
        nuevas_sesiones_pagadas = sesiones_pagadas_actuales + (0 if es_gratis_final else 1)

        # Registrar visita
        conn.execute('''
            INSERT INTO visitas (
                usuario_id, nombre, minutos, precio, fecha, dia, 
                es_fin_semana, es_gratis, tipo_tarifa, 
                es_cumpleanos, es_6ta_visita, motivo_gratis
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            usuario_id_int,
            usuario['nombre_completo'],
            minutos_utilizados,
            precio_guardar,
            fecha_actual.isoformat(),
            obtener_nombre_dia(fecha_actual),
            es_fin_de_semana(fecha_actual),
            es_gratis_final,
            'fin_semana' if es_fin_de_semana(fecha_actual) else 'semana',
            es_cumple,
            es_6ta,
            motivo_gratis
        ))

        # Actualizar niño
        conn.execute('''
            UPDATE ninos
            SET sesiones_totales = ?, 
                sesiones_pagadas = ?, 
                estado = 'Inactivo',
                minutos_asignados = 0, 
                ultima_visita = ?
            WHERE id = ?
        ''', (
            nuevas_sesiones_totales,
            nuevas_sesiones_pagadas,
            fecha_actual.isoformat(),
            usuario_id_int
        ))

        conn.commit()

        # Obtener datos actualizados ANTES de cerrar la conexión
        usuario_actualizado = conn.execute(
            "SELECT * FROM ninos WHERE id = ?",
            (usuario_id_int,)
        ).fetchone()

        conn.close()

        # Actualizar ganancias diarias
        actualizar_ganancias_diarias(fecha_actual, precio_guardar, es_gratis_final)

        # Respuesta final
        return jsonify({
            'success': True,
            'sesiones_totales': nuevas_sesiones_totales,
            'sesiones_pagadas': nuevas_sesiones_pagadas,
            'visita_gratis': es_gratis_final,
            'precio': precio_guardar,
            'minutos_utilizados': minutos_utilizados,
            'nombre': usuario['nombre_completo'],
            'fecha_visita': fecha_actual.isoformat(),
            'es_cumpleanos': es_cumple,
            'es_6ta_visita': es_6ta,
            'motivo_gratis': motivo_gratis,
            'usuario_actualizado': dict(usuario_actualizado) if usuario_actualizado else None
        }), 200

    except Exception as e:
        logger.error(f"❌ ERROR finalizando visita: {e}")
        logger.error(traceback.format_exc())
        return jsonify({'error': f'Error interno al finalizar visita: {str(e)}'}), 500

# =============================================
# NUEVO ENDPOINT PARA VISITAS RECIENTES
# =============================================

@app.route('/api/visitas/recientes', methods=['GET'])
def get_visitas_recientes():
    """Obtener las visitas más recientes para el dashboard"""
    try:
        conn = get_db_connection()
        
        visitas = conn.execute('''
            SELECT 
                v.*,
                n.nombre_completo as nombre_nino
            FROM visitas v
            LEFT JOIN ninos n ON v.usuario_id = n.id
            ORDER BY v.fecha DESC, v.id DESC
            LIMIT 10
        ''').fetchall()
        
        conn.close()
        
        visitas_formateadas = []
        for visita in visitas:
            visita_dict = dict(visita)
            # Usar nombre del niño si está disponible
            if visita_dict.get('nombre_nino'):
                visita_dict['nombre'] = visita_dict['nombre_nino']
            
            visitas_formateadas.append(visita_dict)
        
        logger.info(f"✅ Visitas recientes obtenidas - Total: {len(visitas_formateadas)}")
        
        return jsonify(visitas_formateadas), 200
        
    except Exception as e:
        logger.error(f"❌ ERROR obteniendo visitas recientes: {e}")
        logger.error(traceback.format_exc())
        return jsonify({'error': 'Error interno al obtener visitas recientes'}), 500

# =============================================
# ENDPOINTS DE GANANCIAS Y ESTADÍSTICAS
# =============================================

@app.route('/api/visitas', methods=['GET'])
def get_todas_visitas():
    """Obtener todas las visitas para estadísticas"""
    try:
        conn = get_db_connection()
        
        visitas = conn.execute('''
            SELECT 
                v.*,
                n.nombre_completo as nombre_nino
            FROM visitas v
            LEFT JOIN ninos n ON v.usuario_id = n.id
            ORDER BY v.fecha DESC
        ''').fetchall()
        
        conn.close()
        
        visitas_formateadas = []
        for visita in visitas:
            visita_dict = dict(visita)
            # Usar nombre del niño si está disponible
            if visita_dict.get('nombre_nino'):
                visita_dict['nombre'] = visita_dict['nombre_nino']
            
            visitas_formateadas.append(visita_dict)
        
        logger.info(f"✅ Todas las visitas obtenidas - Total: {len(visitas_formateadas)}")
        
        return jsonify(visitas_formateadas), 200
        
    except Exception as e:
        logger.error(f"❌ ERROR obteniendo todas las visitas: {e}")
        logger.error(traceback.format_exc())
        return jsonify({'error': 'Error interno al obtener visitas'}), 500

# =============================================
# ENDPOINTS DE GASTOS
# =============================================

@app.route('/api/gastos', methods=['GET'])
def get_gastos():
    """Obtener todos los gastos"""
    try:
        conn = get_db_connection()
        
        gastos = conn.execute('''
            SELECT * FROM gastos 
            ORDER BY fecha DESC, created_at DESC
        ''').fetchall()
        
        conn.close()
        
        gastos_formateados = [dict(gasto) for gasto in gastos]
        logger.info(f"✅ Gastos obtenidos - Total: {len(gastos_formateados)}")
        
        return jsonify(gastos_formateados), 200
        
    except Exception as e:
        logger.error(f"❌ ERROR obteniendo gastos: {e}")
        logger.error(traceback.format_exc())
        return jsonify({'error': 'Error interno al obtener gastos'}), 500

@app.route('/api/gasto', methods=['POST'])
def agregar_gasto():
    """Agregar un nuevo gasto"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'Datos JSON requeridos'}), 400
            
        descripcion = safe_str(data.get('descripcion', ''))
        monto = safe_float(data.get('monto', 0))
        categoria = safe_str(data.get('categoria', ''))
        observaciones = safe_str(data.get('observaciones', ''))
        
        # Validaciones
        if not descripcion:
            return jsonify({'error': 'La descripción es requerida'}), 400
            
        if monto <= 0:
            return jsonify({'error': 'El monto debe ser mayor a 0'}), 400
            
        if categoria not in CATEGORIAS_GASTOS:
            return jsonify({'error': 'Categoría no válida'}), 400
        
        # Fecha actual
        fecha_actual = datetime.now()
        fecha = fecha_actual.date().isoformat()
        dia = obtener_nombre_dia(fecha_actual)
        
        conn = get_db_connection()
        
        # Insertar gasto
        cursor = conn.execute('''
            INSERT INTO gastos (descripcion, monto, categoria, fecha, dia, observaciones)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (descripcion, monto, categoria, fecha, dia, observaciones or None))
        
        gasto_id = cursor.lastrowid
        conn.commit()
        
        # Obtener el gasto recién creado
        nuevo_gasto = conn.execute('SELECT * FROM gastos WHERE id = ?', (gasto_id,)).fetchone()
        conn.close()
        
        logger.info(f"✅ Gasto agregado exitosamente - ID: {gasto_id}, Descripción: {descripcion}, Monto: S/. {monto:.2f}, Categoría: {categoria}")
        
        return jsonify({
            'success': True,
            'gasto': dict(nuevo_gasto),
            'message': 'Gasto registrado correctamente'
        }), 200
        
    except Exception as e:
        logger.error(f"❌ ERROR agregando gasto: {e}")
        logger.error(traceback.format_exc())
        return jsonify({'error': f'Error interno al agregar gasto: {str(e)}'}), 500

# =============================================
# ENDPOINTS RESTANTES
# =============================================

@app.route('/api/observaciones/<int:usuario_id>', methods=['GET'])
def get_observaciones_usuario(usuario_id):
    try:
        conn = get_db_connection()
        
        # Verificar que el usuario existe
        usuario_existente = conn.execute('SELECT id FROM ninos WHERE id = ?', (usuario_id,)).fetchone()
        if not usuario_existente:
            conn.close()
            return jsonify({'error': 'Usuario no encontrado'}), 404
        
        # Obtener observaciones
        observaciones = conn.execute('''
            SELECT * FROM observaciones 
            WHERE usuario_id = ?
            ORDER BY fecha DESC
        ''', (usuario_id,)).fetchall()
        
        conn.close()
        
        return jsonify([dict(row) for row in observaciones]), 200
        
    except Exception as e:
        logger.error(f"❌ ERROR obteniendo observaciones: {e}")
        logger.error(traceback.format_exc())
        return jsonify({'error': 'Error interno al obtener observaciones'}), 500

@app.route('/api/observacion', methods=['POST'])
def add_observacion():
    try:
        data = request.get_json()
        logger.info(f"Datos recibidos para observación: {data}")
        
        if not data:
            return jsonify({'error': 'Datos JSON requeridos'}), 400
            
        # Obtener datos con valores por defecto
        usuario_id = data.get('usuario_id')
        nombre = safe_str(data.get('nombre', ''))
        observacion_texto = safe_str(data.get('observacion', ''))
        
        logger.info(f"Procesando observación - usuario_id: {usuario_id}, nombre: {nombre}")
        
        # Validaciones
        if not observacion_texto:
            return jsonify({'error': 'La observación no puede estar vacía'}), 400
            
        if not usuario_id:
            logger.error("❌ ERROR: usuario_id es null o vacío")
            return jsonify({'error': 'ID de usuario es requerido'}), 400
        
        # Convertir ID de forma segura
        usuario_id_int = safe_convert_id(usuario_id)
        if not usuario_id_int:
            logger.error(f"❌ ERROR: ID de usuario inválido - recibido: {usuario_id}, tipo: {type(usuario_id)}")
            return jsonify({'error': 'ID de usuario inválido'}), 400
        
        conn = get_db_connection()
        
        # Verificar que el usuario existe y obtener nombre
        usuario_existente = conn.execute('SELECT id, nombre_completo FROM ninos WHERE id = ?', (usuario_id_int,)).fetchone()
        if not usuario_existente:
            conn.close()
            logger.error(f"❌ ERROR: Usuario no encontrado - ID: {usuario_id_int}")
            return jsonify({'error': 'Usuario no encontrado'}), 404
        
        # Usar el nombre de la base de datos si no se proporcionó
        if not nombre or nombre == "Usuario sin nombre":
            nombre_final = usuario_existente['nombre_completo']
            logger.info(f"✅ Nombre obtenido de BD: {nombre_final}")
        else:
            nombre_final = nombre
        
        # Insertar observación
        cursor = conn.execute('''
            INSERT INTO observaciones (usuario_id, nombre, observacion)
            VALUES (?, ?, ?)
        ''', (usuario_id_int, nombre_final, observacion_texto))
        
        observacion_id = cursor.lastrowid
        conn.commit()
        
        # Obtener la observación recién creada
        nueva_observacion = conn.execute('SELECT * FROM observaciones WHERE id = ?', (observacion_id,)).fetchone()
        conn.close()
        
        logger.info(f"✅ Observación guardada exitosamente - ID: {observacion_id}, Usuario: {usuario_id_int}, Nombre: {nombre_final}")
        
        return jsonify({
            'success': True,
            'observacion': dict(nueva_observacion),
            'message': 'Observación guardada correctamente'
        }), 200
        
    except Exception as e:
        logger.error(f"❌ ERROR agregando observación: {e}")
        logger.error(traceback.format_exc())
        return jsonify({'error': f'Error interno al agregar observación: {str(e)}'}), 500

@app.route('/api/actualizar-tiempo', methods=['POST'])
def actualizar_tiempo():
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'Datos JSON requeridos'}), 400
            
        usuario_id = data.get('id')
        minutos = safe_int(data.get('minutos', 0))
        
        logger.info(f"Actualizando tiempo - usuario_id: {usuario_id}, minutos: {minutos}")
        
        if not usuario_id:
            logger.error("❌ ERROR: usuario_id es null o vacío en actualizar-tiempo")
            return jsonify({'error': 'ID de usuario es requerido'}), 400
            
        if minutos <= 0:
            return jsonify({'error': 'Minutos válidos son requeridos'}), 400
            
        conn = get_db_connection()

        # Convertir ID de forma segura
        usuario_id_int = safe_convert_id(usuario_id)
        if not usuario_id_int:
            conn.close()
            logger.error(f"❌ ERROR: ID de usuario inválido - recibido: {usuario_id}")
            return jsonify({'error': 'ID de usuario inválido'}), 400
        
        # Verificar que el niño existe
        nino = conn.execute('SELECT * FROM ninos WHERE id = ?', (usuario_id_int,)).fetchone()
        if not nino:
            conn.close()
            return jsonify({'error': 'Niño no encontrado'}), 404
        
        # Actualizar el niño
        conn.execute('''
            UPDATE ninos 
            SET minutos_asignados = ?, estado = 'Activo'
            WHERE id = ?
        ''', (minutos, usuario_id_int))
        
        conn.commit()
        conn.close()
        
        logger.info(f"✅ Tiempo actualizado exitosamente - Usuario: {usuario_id_int}, Minutos: {minutos}")
        return jsonify({'success': True}), 200

    except Exception as e:
        logger.error(f"❌ ERROR actualizando tiempo: {e}")
        logger.error(traceback.format_exc())
        return jsonify({'error': 'Error interno al actualizar tiempo'}), 500

@app.route('/api/agregar-tiempo-extra', methods=['POST'])
def agregar_tiempo_extra():
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'Datos JSON requeridos'}), 400
            
        usuario_id = data.get('id')
        minutos_extra = safe_int(data.get('minutos_extra', 0))
        reemplazar = data.get('reemplazar', False)
        
        logger.info(f"Agregando tiempo extra - usuario_id: {usuario_id}, minutos_extra: {minutos_extra}, reemplazar: {reemplazar}")
        
        if not usuario_id:
            return jsonify({'error': 'ID de usuario es requerido'}), 400
            
        if minutos_extra <= 0:
            return jsonify({'error': 'Minutos extra válidos son requeridos'}), 400
            
        conn = get_db_connection()

        # Convertir ID de forma segura
        usuario_id_int = safe_convert_id(usuario_id)
        if not usuario_id_int:
            conn.close()
            return jsonify({'error': 'ID de usuario inválido'}), 400
        
        # Verificar que el niño existe
        nino = conn.execute('SELECT * FROM ninos WHERE id = ?', (usuario_id_int,)).fetchone()
        if not nino:
            conn.close()
            return jsonify({'error': 'Niño no encontrado'}), 404
        
        # ✅ CORREGIDO: Si es reemplazo, usar los minutos directamente
        if reemplazar:
            nuevos_minutos = minutos_extra
        else:
            # Si no es reemplazo, sumar (comportamiento anterior)
            minutos_actuales = nino['minutos_asignados'] or 0
            nuevos_minutos = minutos_actuales + minutos_extra
        
        # Actualizar el niño con tiempo extra
        conn.execute('''
            UPDATE ninos 
            SET minutos_asignados = ?, estado = 'Activo'
            WHERE id = ?
        ''', (nuevos_minutos, usuario_id_int))
        
        conn.commit()
        conn.close()
        
        logger.info(f"✅ Tiempo {'reemplazado' if reemplazar else 'agregado'} exitosamente - Usuario: {usuario_id_int}, Minutos totales: {nuevos_minutos}")
        return jsonify({
            'success': True,
            'minutos_totales': nuevos_minutos,
            'minutos_extra_agregados': minutos_extra,
            'reemplazado': reemplazar
        }), 200

    except Exception as e:
        logger.error(f"❌ ERROR agregando tiempo extra: {e}")
        logger.error(traceback.format_exc())
        return jsonify({'error': 'Error interno al agregar tiempo extra'}), 500

# =============================================
# NUEVOS ENDPOINTS PARA EL FRONTEND
# =============================================

@app.route('/api/alarmas-activas', methods=['GET'])
def get_alarmas_activas():
    """Obtener alarmas activas (para notificaciones)"""
    try:
        # Por ahora retornar lista vacía - se puede implementar después
        return jsonify([]), 200
    except Exception as e:
        logger.error(f"❌ ERROR obteniendo alarmas activas: {e}")
        return jsonify({'error': 'Error interno al obtener alarmas'}), 500

@app.route('/api/desactivar-alarma', methods=['POST'])
def desactivar_alarma():
    """Desactivar alarma manualmente"""
    try:
        data = request.get_json()
        usuario_id = data.get('id')
        
        logger.info(f"✅ Alarma desactivada manualmente para usuario: {usuario_id}")
        
        return jsonify({
            'success': True,
            'message': 'Alarma desactivada correctamente'
        }), 200
        
    except Exception as e:
        logger.error(f"❌ ERROR desactivando alarma: {e}")
        return jsonify({'error': 'Error interno al desactivar alarma'}), 500

# =============================================
# INICIALIZACIÓN Y EJECUCIÓN
# =============================================

@app.route('/api/test', methods=['GET'])
def test_connection():
    """Endpoint de prueba para verificar que el servidor está funcionando"""
    return jsonify({
        'status': 'success',
        'message': 'Conexión exitosa con el backend Flask',
        'timestamp': datetime.now().isoformat()
    })

if __name__ == '__main__':
    # Inicializar base de datos
    init_db()
    
    # Ejecutar la aplicación
    logger.info("✅ Servidor Flask iniciado correctamente")
    logger.info("📊 Sistema de Sensory Club funcionando")
    logger.info("🌐 API disponible en: http://127.0.0.1:5000")
    logger.info("🎂 PRECIOS ESPECIALES ACTIVADOS:")
    logger.info("   - Cumpleaños: 10 y 30 min GRATIS")
    logger.info("   - 6ta visita: TODOS los tiempos GRATIS")
    logger.info("💰 SISTEMA DE GASTOS IMPLEMENTADO")
    logger.info("🔄 Endpoint de actualización de BD disponible en: POST /api/actualizar-bd")
    
    app.run(debug=False, host='0.0.0.0', port=5000)