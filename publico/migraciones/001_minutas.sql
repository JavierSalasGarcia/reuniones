-- Minutas guardadas en el servidor para poder enviarlas desde aqui.
-- Si ya tenias la base creada, importa solo este archivo.
CREATE TABLE IF NOT EXISTS minutas (
  id              INT AUTO_INCREMENT PRIMARY KEY,
  dependencia_id  INT NOT NULL,
  reunion_local   INT NULL,                        -- id de la reunion en la laptop
  persona         VARCHAR(120) NOT NULL DEFAULT '',
  email           VARCHAR(160) NOT NULL DEFAULT '',
  asunto          VARCHAR(200) NOT NULL DEFAULT '',
  fecha           DATETIME NULL,                   -- fecha de la reunion
  archivo         VARCHAR(255) NOT NULL,
  nombre          VARCHAR(160) NOT NULL,
  bytes           INT NOT NULL DEFAULT 0,
  sha256          CHAR(64) NOT NULL,
  estado          VARCHAR(12) NOT NULL DEFAULT 'guardada',  -- guardada | enviada | error
  destinatario    VARCHAR(160) NOT NULL DEFAULT '',
  detalle         VARCHAR(255) NOT NULL DEFAULT '',
  creado          DATETIME NOT NULL,
  enviado         DATETIME NULL,
  UNIQUE KEY (dependencia_id, sha256),
  INDEX (dependencia_id, email, fecha)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
