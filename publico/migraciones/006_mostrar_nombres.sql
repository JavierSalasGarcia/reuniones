-- Que se ve en el monitor y en la fila publica: el nombre o solo el numero.
-- Si ya tenias la base creada, importa solo este archivo.
ALTER TABLE dependencias
  ADD COLUMN mostrar_nombres TINYINT(1) NOT NULL DEFAULT 1;
