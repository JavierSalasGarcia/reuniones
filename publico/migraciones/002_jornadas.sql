-- Jornada de atencion por dia: a que hora llegas, hasta que hora atiendes y
-- hasta que hora se puede formar la gente en la cola.
-- Si ya tenias la base creada, importa solo este archivo.
CREATE TABLE IF NOT EXISTS jornadas (
  id              INT AUTO_INCREMENT PRIMARY KEY,
  dependencia_id  INT NOT NULL,
  fecha           DATE NOT NULL,
  apertura        CHAR(5) NOT NULL,              -- hora prevista de llegada
  cierre          CHAR(5) NOT NULL,              -- fin de la jornada
  tope            CHAR(5) NULL,                  -- ultima hora para formarse
  estado          VARCHAR(12) NOT NULL DEFAULT 'programada', -- programada|abierta|cerrada|cancelada
  nota            VARCHAR(160) NOT NULL DEFAULT '',
  abierta_en      DATETIME NULL,
  cerrada_en      DATETIME NULL,
  creado          DATETIME NOT NULL,
  UNIQUE KEY (dependencia_id, fecha)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
