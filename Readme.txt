FICHERO README MQTT_POSTGRES_GATEWAY

# MQTT to PostgreSQL Gateway

Este proyecto es un conector (gateway) que se suscribe a uno o más topics MQTT, recibe mensajes en formato JSON, analiza automáticamente su estructura, 
crea las tablas necesarias en PostgreSQL (con soporte para tipos como GEOMETRY, DATE y TIMESTAMP) y almacena los datos en la base de datos.

# Notas

- El código desarrollado asume JSON planos o con objetos anidados
- Los mensajes deben ser JSON válidos. Las listas dentro del JSON se ignoran por diseño.
- No da soporte para listas de objetos y arrays de arrays
- El conector no elimina ni modifica datos existentes.
- Cada topic MQTT crea su propia tabla PostgreSQL.
- Compatible con múltiples hilos para aumentar el rendimiento de escritura. 


## 🧩 Características principales

Suscripción MQTT desde múltiples topics	✅	Se lee desde config.ini, se suscribe dinámicamente
Compatibilidad con MQTT 3.1.1 y 5.0	✅	Soporte conmutado vía parámetro version
Lectura y análisis de JSON dinámico	✅	Se infiere tipo y estructura recursivamente
Creación dinámica de tablas	✅	Usa CREATE TABLE IF NOT EXISTS, con soporte GEOMETRY
Inserción automática de datos	✅	Incluye uso de ST_GeomFromText() para geometrías
Manejo multihilo	✅	Configurable desde config.ini
Configuración externa via config.ini	✅	MQTT, PostgreSQL, QoS, número de hilos, logs
Logs con rotación	✅	RotatingFileHandler incluido
Errores y reconexiones	⚠️ parcial	Rollback básico incluido. Reconexión manual puede añadirse fácilmente si se desea
Compatibilidad con PostGIS	✅	GEOMETRY y ST_GeomFromText() integrados
Soporte para esquemas PostgreSQL personalizados  ✅  (`schema = sensores`, por ejemplo).

## ✅ Requisitos del sistema

- Python 3.10 o superior
- PostgreSQL 13+ con extensión `postgis`
- Broker MQTT (Mosquitto, EMQX, RabbitMQ con plugin MQTT, etc.)
- SO compatible: Windows / Linux

---

## 📦 Instalación

1. Clona este repositorio o copia los archivos:
   ```bash
   git clone https://tu-repo/mqtt_postgres_gateway.git
   cd mqtt_postgres_gateway

2. Crea entorno virtiual si lo ejecutas desde tu local
```bash
    python -m venv venv
    venv\Scripts\activate   # en Windows
    # o
    source venv/bin/activate   # en Linux

3. Instala dependencias
    pip install -r requirements.txt

4. Crea la base de datos y el esquema en el postgre o MySQL

5. Edita el archivo config.ini para definir las conexiones

6. Con el entorno activado ejecuta
    python mqtt_postgres_gateway.py
