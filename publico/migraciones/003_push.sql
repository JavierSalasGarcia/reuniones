-- Aviso al celular (y de ahi al reloj) cuando alguien se forma en la cola.
-- Si ya tenias la base creada, importa solo este archivo.
ALTER TABLE dependencias
  ADD COLUMN push_tema    VARCHAR(80) NOT NULL DEFAULT '',
  ADD COLUMN push_detalle TINYINT(1)  NOT NULL DEFAULT 1;
