-- Version SQLite del esquema, solo para las pruebas.
CREATE TABLE dependencias (
  id INTEGER PRIMARY KEY AUTOINCREMENT, clave TEXT NOT NULL UNIQUE, nombre TEXT NOT NULL,
  titular TEXT NOT NULL, correo_titular TEXT NOT NULL DEFAULT '',
  dominio_correo TEXT NOT NULL DEFAULT 'uaemex.mx', token_hash TEXT NOT NULL DEFAULT '',
  token_reloj_hash TEXT NOT NULL DEFAULT '',
  disponible INTEGER NOT NULL DEFAULT 0, mensaje TEXT NOT NULL DEFAULT '',
  atendiendo_turno INTEGER, duracion_max INTEGER NOT NULL DEFAULT 10,
  colchon_turno INTEGER NOT NULL DEFAULT 2, colchon_reunion INTEGER NOT NULL DEFAULT 10,
  minutos_cita TEXT NOT NULL DEFAULT '20,30,45', push_tema TEXT NOT NULL DEFAULT '',
  push_detalle INTEGER NOT NULL DEFAULT 1, activa INTEGER NOT NULL DEFAULT 1, creado TEXT NOT NULL);
CREATE TABLE horarios (
  id INTEGER PRIMARY KEY AUTOINCREMENT, dependencia_id INTEGER NOT NULL, dia INTEGER NOT NULL,
  inicio TEXT NOT NULL, fin TEXT NOT NULL);
CREATE TABLE excepciones (
  id INTEGER PRIMARY KEY AUTOINCREMENT, dependencia_id INTEGER NOT NULL, fecha TEXT NOT NULL,
  tipo TEXT NOT NULL DEFAULT 'cerrado', inicio TEXT, fin TEXT, motivo TEXT NOT NULL DEFAULT '');
CREATE TABLE bloqueos (
  id INTEGER PRIMARY KEY AUTOINCREMENT, dependencia_id INTEGER NOT NULL, inicio TEXT NOT NULL,
  fin TEXT NOT NULL, motivo TEXT NOT NULL DEFAULT '', origen TEXT NOT NULL DEFAULT 'manual', cita_id INTEGER);
CREATE TABLE turnos (
  id INTEGER PRIMARY KEY AUTOINCREMENT, dependencia_id INTEGER NOT NULL, fecha TEXT NOT NULL,
  folio INTEGER NOT NULL, nombre TEXT NOT NULL, nombre_publico TEXT NOT NULL DEFAULT '',
  email TEXT NOT NULL, asunto TEXT NOT NULL DEFAULT '', minutos INTEGER NOT NULL DEFAULT 10,
  estado TEXT NOT NULL DEFAULT 'espera', token TEXT NOT NULL UNIQUE, estimado TEXT, avisado TEXT,
  creado TEXT NOT NULL, llamado TEXT, cerrado TEXT, UNIQUE (dependencia_id, fecha, folio));
CREATE TABLE citas (
  id INTEGER PRIMARY KEY AUTOINCREMENT, dependencia_id INTEGER NOT NULL, nombre TEXT NOT NULL,
  email TEXT NOT NULL, asunto TEXT NOT NULL, descripcion TEXT, minutos INTEGER NOT NULL DEFAULT 30,
  propuesta TEXT NOT NULL, confirmada TEXT, estado TEXT NOT NULL DEFAULT 'solicitada',
  motivo TEXT NOT NULL DEFAULT '', token TEXT NOT NULL UNIQUE, creado TEXT NOT NULL, resuelta TEXT);
CREATE TABLE adjuntos (
  id INTEGER PRIMARY KEY AUTOINCREMENT, cita_id INTEGER NOT NULL, nombre TEXT NOT NULL,
  ruta TEXT NOT NULL, tipo TEXT NOT NULL DEFAULT '', bytes INTEGER NOT NULL DEFAULT 0, creado TEXT NOT NULL);
CREATE TABLE verificaciones (
  id INTEGER PRIMARY KEY AUTOINCREMENT, dependencia_id INTEGER NOT NULL, email TEXT NOT NULL,
  codigo_hash TEXT NOT NULL, carga TEXT NOT NULL, intentos INTEGER NOT NULL DEFAULT 0,
  expira TEXT NOT NULL, usado TEXT, ip TEXT NOT NULL DEFAULT '', creado TEXT NOT NULL);
CREATE TABLE eventos (
  id INTEGER PRIMARY KEY AUTOINCREMENT, dependencia_id INTEGER, momento TEXT NOT NULL,
  accion TEXT NOT NULL, detalle TEXT NOT NULL DEFAULT '');
CREATE TABLE minutas (
  id INTEGER PRIMARY KEY AUTOINCREMENT, dependencia_id INTEGER NOT NULL, reunion_local INTEGER,
  persona TEXT NOT NULL DEFAULT '', email TEXT NOT NULL DEFAULT '', asunto TEXT NOT NULL DEFAULT '',
  fecha TEXT, archivo TEXT NOT NULL, nombre TEXT NOT NULL, bytes INTEGER NOT NULL DEFAULT 0,
  sha256 TEXT NOT NULL, estado TEXT NOT NULL DEFAULT 'guardada', destinatario TEXT NOT NULL DEFAULT '',
  detalle TEXT NOT NULL DEFAULT '', creado TEXT NOT NULL, enviado TEXT,
  UNIQUE (dependencia_id, sha256));
CREATE TABLE jornadas (
  id INTEGER PRIMARY KEY AUTOINCREMENT, dependencia_id INTEGER NOT NULL, fecha TEXT NOT NULL,
  apertura TEXT NOT NULL, cierre TEXT NOT NULL, tope TEXT,
  estado TEXT NOT NULL DEFAULT 'programada', nota TEXT NOT NULL DEFAULT '',
  abierta_en TEXT, cerrada_en TEXT, creado TEXT NOT NULL,
  UNIQUE (dependencia_id, fecha));
