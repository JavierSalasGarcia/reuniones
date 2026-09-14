-- Esquema de la base local. Todo vive en la laptop; nada de esto viaja a la nube.
PRAGMA journal_mode = WAL;
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS personas (
    id                  INTEGER PRIMARY KEY,
    nombre              TEXT    NOT NULL,
    email               TEXT    NOT NULL UNIQUE COLLATE NOCASE,
    foto                TEXT,                  -- ruta relativa a la carpeta de datos
    alternativas        TEXT,                  -- rutas alternas separadas por '|'
    video               TEXT,                  -- ruta del video del alta (se borra solo)
    video_expira        TEXT,                  -- fecha ISO tras la cual se borra el video
    adscripcion         TEXT,
    tipo                TEXT DEFAULT 'otro',   -- alumno | profesor | administrativo | otro
    notas               TEXT,
    reservado           INTEGER NOT NULL DEFAULT 0,  -- 1 = caso delicado, ocultar nombre en pantalla
    consentimiento      TEXT,                  -- fecha ISO en que acepto el aviso de privacidad
    creado              TEXT NOT NULL,
    actualizado         TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS rostros (
    id          INTEGER PRIMARY KEY,
    persona_id  INTEGER NOT NULL REFERENCES personas(id) ON DELETE CASCADE,
    vector      BLOB    NOT NULL,              -- float32 normalizado
    dimension   INTEGER NOT NULL,
    calidad     REAL    NOT NULL DEFAULT 0,
    origen      TEXT    NOT NULL DEFAULT 'alta',
    creado      TEXT    NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_rostros_persona ON rostros(persona_id);

CREATE TABLE IF NOT EXISTS reuniones (
    id          INTEGER PRIMARY KEY,
    persona_id  INTEGER NOT NULL REFERENCES personas(id) ON DELETE CASCADE,
    inicio      TEXT    NOT NULL,              -- ISO local
    fin         TEXT,
    asunto      TEXT    NOT NULL DEFAULT '',
    categoria   TEXT    DEFAULT '',            -- academico | administrativo | becas | disciplinario | otro
    notas       TEXT,
    origen      TEXT    NOT NULL DEFAULT 'presencial',
    creado      TEXT    NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_reuniones_persona ON reuniones(persona_id, inicio DESC);
CREATE INDEX IF NOT EXISTS idx_reuniones_inicio ON reuniones(inicio DESC);

CREATE TABLE IF NOT EXISTS archivos (
    id          INTEGER PRIMARY KEY,
    reunion_id  INTEGER NOT NULL REFERENCES reuniones(id) ON DELETE CASCADE,
    clase       TEXT    NOT NULL,              -- original | minuta | adjunto
    ruta        TEXT    NOT NULL,              -- relativa a la carpeta de datos
    nombre      TEXT    NOT NULL,
    sello       TEXT,                          -- yyyymmdd_hhmm tomado del nombre original
    sha256      TEXT,
    bytes       INTEGER NOT NULL DEFAULT 0,
    creado      TEXT    NOT NULL,
    UNIQUE(reunion_id, clase, sello)
);
CREATE INDEX IF NOT EXISTS idx_archivos_reunion ON archivos(reunion_id);

CREATE TABLE IF NOT EXISTS bandeja (
    id          INTEGER PRIMARY KEY,
    ruta        TEXT    NOT NULL UNIQUE,
    nombre      TEXT    NOT NULL,
    clase       TEXT    NOT NULL,
    sello       TEXT,
    motivo      TEXT    NOT NULL,              -- por que no se pudo asociar solo
    detectado   TEXT    NOT NULL,
    resuelto    TEXT
);

CREATE TABLE IF NOT EXISTS acuerdos (
    id          INTEGER PRIMARY KEY,
    reunion_id  INTEGER NOT NULL REFERENCES reuniones(id) ON DELETE CASCADE,
    texto       TEXT    NOT NULL,
    responsable TEXT    DEFAULT '',
    compromiso  TEXT,                          -- fecha ISO
    estado      TEXT    NOT NULL DEFAULT 'abierto',  -- abierto | cerrado
    creado      TEXT    NOT NULL,
    cerrado     TEXT
);
CREATE INDEX IF NOT EXISTS idx_acuerdos_reunion ON acuerdos(reunion_id);
CREATE INDEX IF NOT EXISTS idx_acuerdos_estado ON acuerdos(estado, compromiso);

CREATE TABLE IF NOT EXISTS envios (
    id           INTEGER PRIMARY KEY,
    reunion_id   INTEGER NOT NULL REFERENCES reuniones(id) ON DELETE CASCADE,
    destinatario TEXT    NOT NULL,
    asunto       TEXT    NOT NULL,
    estado       TEXT    NOT NULL,             -- enviado | error
    detalle      TEXT,
    enviado      TEXT    NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_envios_reunion ON envios(reunion_id);

CREATE TABLE IF NOT EXISTS fragmentos (
    id          INTEGER PRIMARY KEY,
    reunion_id  INTEGER NOT NULL REFERENCES reuniones(id) ON DELETE CASCADE,
    archivo_id  INTEGER REFERENCES archivos(id) ON DELETE CASCADE,
    clase       TEXT    NOT NULL,
    orden       INTEGER NOT NULL DEFAULT 0,
    texto       TEXT    NOT NULL,
    vector      BLOB,
    dimension   INTEGER
);
CREATE INDEX IF NOT EXISTS idx_fragmentos_reunion ON fragmentos(reunion_id);

CREATE VIRTUAL TABLE IF NOT EXISTS fragmentos_fts USING fts5(
    texto, content='fragmentos', content_rowid='id', tokenize='unicode61 remove_diacritics 2'
);

CREATE TRIGGER IF NOT EXISTS fragmentos_ai AFTER INSERT ON fragmentos BEGIN
    INSERT INTO fragmentos_fts(rowid, texto) VALUES (new.id, new.texto);
END;
CREATE TRIGGER IF NOT EXISTS fragmentos_ad AFTER DELETE ON fragmentos BEGIN
    INSERT INTO fragmentos_fts(fragmentos_fts, rowid, texto) VALUES('delete', old.id, old.texto);
END;
CREATE TRIGGER IF NOT EXISTS fragmentos_au AFTER UPDATE ON fragmentos BEGIN
    INSERT INTO fragmentos_fts(fragmentos_fts, rowid, texto) VALUES('delete', old.id, old.texto);
    INSERT INTO fragmentos_fts(rowid, texto) VALUES (new.id, new.texto);
END;

CREATE TABLE IF NOT EXISTS ajustes (
    clave TEXT PRIMARY KEY,
    valor TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS bitacora (
    id       INTEGER PRIMARY KEY,
    momento  TEXT NOT NULL,
    accion   TEXT NOT NULL,
    detalle  TEXT
);
