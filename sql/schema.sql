-- SEÇÃO 8-BIT — esquema de auditoria (SQLite 3)
-- Simulação acadêmica; dados fictícios; nenhum voto é registrado.

PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS execucao (
    execucao_id      TEXT PRIMARY KEY,
    criada_em        TEXT NOT NULL,
    seed             INTEGER NOT NULL,
    cenario          TEXT NOT NULL,
    politica         TEXT NOT NULL,
    politica_versao  TEXT NOT NULL,
    config_json      TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS eleitor (
    execucao_id  TEXT NOT NULL REFERENCES execucao(execucao_id),
    eleitor_id   TEXT NOT NULL,             -- ID fictício (E-0001)
    apelido      TEXT NOT NULL,             -- apelido fictício
    chegada_min  REAL NOT NULL,
    classe       TEXT NOT NULL CHECK (classe IN ('MAIS_DE_80','PREFERENCIAL','DOADOR','COMUM')),
    fundamento   TEXT NOT NULL,
    origem       TEXT NOT NULL,
    acompanha    TEXT,
    PRIMARY KEY (execucao_id, eleitor_id)
);

CREATE TABLE IF NOT EXISTS evento_auditoria (
    evento_id        TEXT PRIMARY KEY,      -- execucao_id:seq
    execucao_id      TEXT NOT NULL REFERENCES execucao(execucao_id),
    seq              INTEGER NOT NULL CHECK (seq > 0),
    instante_min     REAL NOT NULL,
    hora_simulada    TEXT NOT NULL,
    eleitor_id       TEXT,
    tipo             TEXT NOT NULL,
    estado_anterior  TEXT,
    estado_posterior TEXT,
    justificativa    TEXT NOT NULL,
    politica_versao  TEXT NOT NULL,
    dados_json       TEXT NOT NULL,
    hash_anterior    TEXT NOT NULL,
    hash             TEXT NOT NULL,
    UNIQUE (execucao_id, seq),
    FOREIGN KEY (execucao_id, eleitor_id) REFERENCES eleitor(execucao_id, eleitor_id)
);

CREATE INDEX IF NOT EXISTS ix_evento_tipo ON evento_auditoria(execucao_id, tipo);
CREATE INDEX IF NOT EXISTS ix_evento_eleitor ON evento_auditoria(execucao_id, eleitor_id);
