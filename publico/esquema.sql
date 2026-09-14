-- Base de la parte publica (MySQL 5.7+ / MariaDB). Importar desde phpMyAdmin.
-- Aqui solo viven turnos, citas y disponibilidad. Los expedientes, las minutas
-- y los rostros nunca salen de la laptop.

CREATE TABLE IF NOT EXISTS dependencias (
  id                INT AUTO_INCREMENT PRIMARY KEY,
  clave             VARCHAR(16)  NOT NULL UNIQUE,   -- sa, dir, ...
  nombre            VARCHAR(120) NOT NULL,
  titular           VARCHAR(120) NOT NULL,
  correo_titular    VARCHAR(160) NOT NULL DEFAULT '',
  dominio_correo    VARCHAR(80)  NOT NULL DEFAULT 'uaemex.mx',
  token_hash        VARCHAR(64)  NOT NULL DEFAULT '',
  disponible        TINYINT(1)   NOT NULL DEFAULT 0,
  mensaje           VARCHAR(255) NOT NULL DEFAULT '',
  atendiendo_turno  INT          NULL,
  duracion_max      INT          NOT NULL DEFAULT 10,   -- minutos por turno
  colchon_turno     INT          NOT NULL DEFAULT 2,
  colchon_reunion   INT          NOT NULL DEFAULT 10,
  minutos_cita      VARCHAR(40)  NOT NULL DEFAULT '20,30,45',
  activa            TINYINT(1)   NOT NULL DEFAULT 1,
  creado            DATETIME     NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS horarios (
  id              INT AUTO_INCREMENT PRIMARY KEY,
  dependencia_id  INT NOT NULL,
  dia             TINYINT NOT NULL,          -- 1 lunes ... 7 domingo
  inicio          CHAR(5) NOT NULL,          -- 09:00
  fin             CHAR(5) NOT NULL,
  INDEX (dependencia_id, dia)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS excepciones (
  id              INT AUTO_INCREMENT PRIMARY KEY,
  dependencia_id  INT  NOT NULL,
  fecha           DATE NOT NULL,
  tipo            VARCHAR(10) NOT NULL DEFAULT 'cerrado',  -- cerrado | abierto
  inicio          CHAR(5) NULL,
  fin             CHAR(5) NULL,
  motivo          VARCHAR(160) NOT NULL DEFAULT '',
  INDEX (dependencia_id, fecha)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS bloqueos (
  id              INT AUTO_INCREMENT PRIMARY KEY,
  dependencia_id  INT NOT NULL,
  inicio          DATETIME NOT NULL,
  fin             DATETIME NOT NULL,
  motivo          VARCHAR(160) NOT NULL DEFAULT '',
  origen          VARCHAR(16)  NOT NULL DEFAULT 'manual',  -- manual | cita
  cita_id         INT NULL,
  INDEX (dependencia_id, inicio)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS turnos (
  id              INT AUTO_INCREMENT PRIMARY KEY,
  dependencia_id  INT NOT NULL,
  fecha           DATE NOT NULL,
  folio           INT NOT NULL,
  nombre          VARCHAR(120) NOT NULL,
  nombre_publico  VARCHAR(120) NOT NULL DEFAULT '',
  email           VARCHAR(160) NOT NULL,
  asunto          VARCHAR(200) NOT NULL DEFAULT '',
  minutos         INT NOT NULL DEFAULT 10,
  estado          VARCHAR(12) NOT NULL DEFAULT 'espera', -- espera|llamado|atendido|cancelado|ausente
  token           CHAR(32) NOT NULL,
  estimado        DATETIME NULL,
  avisado         DATETIME NULL,
  creado          DATETIME NOT NULL,
  llamado         DATETIME NULL,
  cerrado         DATETIME NULL,
  UNIQUE KEY (dependencia_id, fecha, folio),
  UNIQUE KEY (token),
  INDEX (dependencia_id, fecha, estado)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS citas (
  id              INT AUTO_INCREMENT PRIMARY KEY,
  dependencia_id  INT NOT NULL,
  nombre          VARCHAR(120) NOT NULL,
  email           VARCHAR(160) NOT NULL,
  asunto          VARCHAR(200) NOT NULL,
  descripcion     TEXT,
  minutos         INT NOT NULL DEFAULT 30,
  propuesta       DATETIME NOT NULL,
  confirmada      DATETIME NULL,
  estado          VARCHAR(12) NOT NULL DEFAULT 'solicitada', -- solicitada|aprobada|rechazada|cancelada
  motivo          VARCHAR(255) NOT NULL DEFAULT '',
  token           CHAR(32) NOT NULL,
  creado          DATETIME NOT NULL,
  resuelta        DATETIME NULL,
  UNIQUE KEY (token),
  INDEX (dependencia_id, estado, propuesta)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS adjuntos (
  id        INT AUTO_INCREMENT PRIMARY KEY,
  cita_id   INT NOT NULL,
  nombre    VARCHAR(160) NOT NULL,
  ruta      VARCHAR(255) NOT NULL,
  tipo      VARCHAR(80)  NOT NULL DEFAULT '',
  bytes     INT NOT NULL DEFAULT 0,
  creado    DATETIME NOT NULL,
  INDEX (cita_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS verificaciones (
  id              INT AUTO_INCREMENT PRIMARY KEY,
  dependencia_id  INT NOT NULL,
  email           VARCHAR(160) NOT NULL,
  codigo_hash     VARCHAR(64) NOT NULL,
  carga           TEXT NOT NULL,           -- la solicitud en espera de confirmacion
  intentos        INT NOT NULL DEFAULT 0,
  expira          DATETIME NOT NULL,
  usado           DATETIME NULL,
  ip              VARCHAR(45) NOT NULL DEFAULT '',
  creado          DATETIME NOT NULL,
  INDEX (email, creado),
  INDEX (ip, creado)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS eventos (
  id              INT AUTO_INCREMENT PRIMARY KEY,
  dependencia_id  INT NULL,
  momento         DATETIME NOT NULL,
  accion          VARCHAR(40) NOT NULL,
  detalle         VARCHAR(255) NOT NULL DEFAULT '',
  INDEX (dependencia_id, momento)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
