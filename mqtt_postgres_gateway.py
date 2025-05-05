# mqtt_postgres_gateway.py
# Versión final con soporte para GEOMETRY, TIMESTAMP, DATE
# Requiere: paho-mqtt, psycopg[binary], shapely, postgis habilitado en PostgreSQL

import configparser
import logging
from logging.handlers import RotatingFileHandler
import threading
from queue import Queue
import time
import json
import re
import datetime
import psycopg
import paho.mqtt.client as mqtt
from shapely import wkt

# Sanitizar nombres para uso en SQL
def sanitize_name(name):
    sanitized = re.sub(r'[^0-9a-zA-Z_]', '_', str(name))
    if sanitized and sanitized[0].isdigit():
        sanitized = '_' + sanitized
    return sanitized.lower()

# Inferencia de tipos SQL
def is_date(value):
    try:
        datetime.datetime.strptime(value, "%Y-%m-%d")
        return True
    except:
        return False

def is_timestamp(value):
    try:
        datetime.datetime.strptime(value, "%Y-%m-%dT%H:%M:%S")
        return True
    except:
        return False

def is_geometry(value):
    try:
        return wkt.loads(value).is_valid
    except:
        return False

def infer_sql_type(value):
    if isinstance(value, bool): return "BOOLEAN"
    if isinstance(value, int): return "BIGINT"
    if isinstance(value, float): return "DOUBLE PRECISION"
    if isinstance(value, str):
        if is_date(value): return "DATE"
        if is_timestamp(value): return "TIMESTAMP"
        if is_geometry(value): return "GEOMETRY"
        return "TEXT"
    if isinstance(value, datetime.date): return "DATE"
    if isinstance(value, datetime.datetime): return "TIMESTAMP"
    return "TEXT"

# Construir esquema
schema_registry = {}

def build_schema(topic, data):
    topic_table = sanitize_name(topic)
    def build_node(table_name, obj, parent_table=None):
        node = {
            "table": sanitize_name(table_name),
            "columns": [], "types": {},
            "parent_table": sanitize_name(parent_table) if parent_table else None,
            "nested": {}
        }
        for key, val in obj.items():
            if isinstance(val, (dict, list)): continue
            col = sanitize_name(key)
            if col == "id": col = "json_id"
            node["columns"].append(col)
            node["types"][col] = infer_sql_type(val)
        for key, val in obj.items():
            if isinstance(val, dict):
                sub = build_node(f"{table_name}_{key}", val, parent_table=table_name)
                node["nested"][key] = sub
        return node
    return build_node(topic_table, data)

# Crear tablas
def build_create_table_sql(schema_node):
    stmts = []
    def build(schema):
        table = schema['table']
        cols = ["id BIGSERIAL PRIMARY KEY"]
        if schema.get("parent_table"):
            parent_col = f"{schema['parent_table']}_id"
            cols.append(f"{parent_col} BIGINT REFERENCES {schema['parent_table']}(id)")
        for col in schema['columns']:
            col_type = schema['types'].get(col, "TEXT")
            if col_type == "GEOMETRY":
                cols.append(f"{col} GEOMETRY")
            else:
                cols.append(f"{col} {col_type}")
        sql = f"CREATE TABLE IF NOT EXISTS {table} (\n    " + ",\n    ".join(cols) + "\n);"
        stmts.append(sql)
        for child in schema.get("nested", {}).values():
            build(child)
    build(schema_node)
    return stmts

# Insertar datos
def build_insert_query(table, columns, types, parent_table=None):
    all_cols = list(columns)
    if parent_table:
        all_cols.append(f"{parent_table}_id")
    placeholders = []
    for col in columns:
        if types.get(col) == "GEOMETRY":
            placeholders.append("ST_GeomFromText(%s, 4326)")
        else:
            placeholders.append("%s")
    if parent_table:
        placeholders.append("%s")
    sql = f"INSERT INTO {table} ({', '.join(all_cols)}) VALUES ({', '.join(placeholders)}) RETURNING id;"
    return sql

def insert_single_row(conn, data, schema, parent_id=None):
    table = schema['table']
    cols = schema['columns']
    values = [data.get('id') if c == 'json_id' else data.get(c) for c in cols]
    if parent_id and schema.get('parent_table'):
        values.append(parent_id)
    sql = build_insert_query(table, cols, schema['types'], schema.get('parent_table'))
    cur = conn.execute(sql, values)
    return cur.fetchone()[0]

def insert_data(conn, data, schema, parent_id=None):
    if not isinstance(data, dict): return
    new_id = insert_single_row(conn, data, schema, parent_id)
    for field, child_schema in schema.get('nested', {}).items():
        if field in data:
            insert_data(conn, data[field], child_schema, new_id)

# Hilo BD
def db_worker(db_cfg, queue, logger):
    conn = None
    while True:
        topic, payload = queue.get()
        if conn is None or conn.closed:
            conn = psycopg.connect(**db_cfg)
            conn.autocommit = False
        try:
            msg = json.loads(payload)
            if topic not in schema_registry:
                schema = build_schema(topic, msg)
                stmts = build_create_table_sql(schema)
                for sql in stmts:
                    conn.execute(sql)
                schema_registry[topic] = schema
                conn.commit()
            insert_data(conn, msg, schema_registry[topic])
            conn.commit()
            logger.info(f"[DB] Insertado mensaje en topic {topic}")
        except Exception as e:
            logger.error(f"[DB] Error: {e}", exc_info=True)
            if conn and not conn.closed:    # si ocurre una excepción o la conexión a base de datos está cerrada, el código realiza un roollback
                conn.rollback()

# MQTT callbacks
def on_connect(client, userdata, flags, rc, props=None):
    if rc == 0:
        userdata['logger'].info("Conectado a MQTT")
        for topic in userdata['topics']:
            client.subscribe(topic, qos=userdata['qos'])

def on_message(client, userdata, msg):
    userdata['queue'].put((msg.topic, msg.payload.decode('utf-8')))

def on_disconnect(client, userdata, rc):
    userdata['logger'].warning("Desconectado de MQTT. Intentando reconectar...")
    while True:
        try:
            client.reconnect()
            break
        except Exception as e:
            userdata['logger'].error(f"Error al reconectar: {e}")
            time.sleep(5)  # Esperar antes de intentar reconectar

# Main
def main():
    config = configparser.ConfigParser()
    config.read("config.ini")

    required_keys = ['host', 'port', 'database', 'user', 'password']
    for key in required_keys:
        if key not in config['postgres']:
            raise ValueError(f"Falta la clave '{key}' en la sección [postgres] del archivo de configuración.")

    db_cfg = {
        'host': config['postgres']['host'],
        'port': config.getint('postgres', 'port'),
        'dbname': config['postgres']['database'],
        'user': config['postgres']['user'],
        'password': config['postgres']['password']
    }

    log_file = config['service'].get('log_file', 'gateway.log')
    log_level = config['service'].get('log_level', 'INFO')
    logger = logging.getLogger("MQTT2PG")
    logger.setLevel(log_level)
    fh = RotatingFileHandler(log_file, maxBytes=10_000_000, backupCount=5)
    fh.setFormatter(logging.Formatter('%(asctime)s %(levelname)s %(message)s'))
    logger.addHandler(fh)

    queue = Queue(maxsize=1000)  # Limitar la cola a 1000 mensajes
    num_threads = config.getint('service', 'threads', fallback=4)
    for _ in range(num_threads):
        threading.Thread(target=db_worker, args=(db_cfg, queue, logger), daemon=True).start()

    mqtt_cfg = config['mqtt']
    protocol_version = int(mqtt_cfg.get('version', 3))
    client = mqtt.Client(protocol=mqtt.MQTTv5 if protocol_version == 5 else mqtt.MQTTv311)
    client.username_pw_set(mqtt_cfg.get('username'), mqtt_cfg.get('password'))
    topics = [t.strip() for t in mqtt_cfg['topics'].split(',')]
    client.user_data_set({'queue': queue, 'logger': logger, 'topics': topics, 'qos': mqtt_cfg.getint('qos', fallback=1)})
    client.on_connect = on_connect
    client.on_message = on_message
    client.on_disconnect = on_disconnect
    client.connect(mqtt_cfg['host'], mqtt_cfg.getint('port'))
    client.loop_forever()

if __name__ == "__main__":
    main()
