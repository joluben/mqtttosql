FICHERO README MQTT_POSTGRES_GATEWAY

El código desarrollado asume JSON planos o con objetos anidados, no da soporte para listas de objetos y arrays de arrays, que no se mencionaron como requeridos. 
En caso de requerirse habría que actualizar el código.

Funcionalidades:
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