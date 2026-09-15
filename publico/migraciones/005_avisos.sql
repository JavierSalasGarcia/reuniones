-- Avisos al reloj que dependen del reloj de la pared (reunion pasada de tiempo,
-- cita proxima, cola vacia) y la memoria para no repetirlos.
-- Si ya tenias la base creada, importa solo este archivo.
ALTER TABLE dependencias
  ADD COLUMN push_avisos VARCHAR(80) NOT NULL DEFAULT 'formado,excedido,cita,vacia';

CREATE TABLE IF NOT EXISTS senales (
  id              INT AUTO_INCREMENT PRIMARY KEY,
  dependencia_id  INT NOT NULL,
  clave           VARCHAR(80) NOT NULL,
  valor           VARCHAR(80) NOT NULL DEFAULT '',
  momento         DATETIME NOT NULL,
  UNIQUE KEY (dependencia_id, clave)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
