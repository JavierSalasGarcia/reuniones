-- Llave aparte para el reloj: solo puede leer la vista de la muneca.
-- Si ya tenias la base creada, importa solo este archivo.
ALTER TABLE dependencias
  ADD COLUMN token_reloj_hash VARCHAR(64) NOT NULL DEFAULT '';
