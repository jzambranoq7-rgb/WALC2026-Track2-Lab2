-- PostgreSQL conserva los documentos y su texto. Los PDF siguen en conocimiento/.
-- La búsqueda vectorial de este recorrido se realiza en Pinecone.

CREATE TABLE IF NOT EXISTS documentos (
    documento TEXT NOT NULL,
    version INTEGER NOT NULL,
    titulo TEXT NOT NULL,
    archivo TEXT NOT NULL,
    tipo TEXT NOT NULL,
    sede TEXT NOT NULL,
    vigente_desde TEXT NOT NULL,
    vigente_hasta TEXT NOT NULL,
    texto TEXT NOT NULL,
    PRIMARY KEY (documento, version)
);

CREATE TABLE IF NOT EXISTS fragmentos (
    id TEXT PRIMARY KEY,
    documento TEXT NOT NULL,
    version INTEGER NOT NULL,
    pagina INTEGER NOT NULL CHECK (pagina >= 1),
    seccion TEXT NOT NULL,
    parte INTEGER NOT NULL CHECK (parte >= 1),
    texto TEXT NOT NULL,
    FOREIGN KEY (documento, version) REFERENCES documentos(documento, version)
);

-- Solo registra qué preparación se terminó de indexar, sin huellas del contenido.
-- Una escritura SQL durante la carga invalida el estado hasta confirmar Pinecone.
CREATE TABLE IF NOT EXISTS indexacion (
    namespace TEXT PRIMARY KEY,
    host TEXT NOT NULL,
    modelo TEXT NOT NULL,
    dimension INTEGER NOT NULL
);
