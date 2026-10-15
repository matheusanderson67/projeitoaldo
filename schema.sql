-- Migration inicial do StudyRAG (executada automaticamente ao abrir o app).
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS ambientes (
    id SERIAL PRIMARY KEY,
    nome TEXT NOT NULL,
    area TEXT,
    materia TEXT,
    assunto TEXT,
    periodo TEXT,
    criado_em TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS documentos (
    id SERIAL PRIMARY KEY,
    ambiente_id INT NOT NULL REFERENCES ambientes(id) ON DELETE CASCADE,
    nome_arquivo TEXT NOT NULL,
    caminho TEXT NOT NULL,
    tamanho_bytes BIGINT NOT NULL,
    hash TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pendente',
    erro TEXT,
    num_paginas INT,
    num_trechos INT,
    criado_em TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (ambiente_id, hash)
);

CREATE TABLE IF NOT EXISTS paginas (
    id SERIAL PRIMARY KEY,
    documento_id INT NOT NULL REFERENCES documentos(id) ON DELETE CASCADE,
    numero INT NOT NULL,
    texto TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS trechos (
    id SERIAL PRIMARY KEY,
    documento_id INT NOT NULL REFERENCES documentos(id) ON DELETE CASCADE,
    ambiente_id INT NOT NULL REFERENCES ambientes(id) ON DELETE CASCADE,
    pagina INT NOT NULL,
    indice INT NOT NULL,
    texto TEXT NOT NULL,
    embedding vector(384) NOT NULL
);

CREATE INDEX IF NOT EXISTS trechos_ambiente_idx ON trechos (ambiente_id);
CREATE INDEX IF NOT EXISTS trechos_embedding_idx ON trechos USING hnsw (embedding vector_cosine_ops);

CREATE TABLE IF NOT EXISTS perguntas (
    id SERIAL PRIMARY KEY,
    ambiente_id INT NOT NULL REFERENCES ambientes(id) ON DELETE CASCADE,
    texto TEXT NOT NULL,
    criado_em TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS respostas (
    id SERIAL PRIMARY KEY,
    pergunta_id INT NOT NULL REFERENCES perguntas(id) ON DELETE CASCADE,
    texto TEXT NOT NULL,
    fontes JSONB NOT NULL DEFAULT '[]',
    criado_em TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS geracoes (
    id SERIAL PRIMARY KEY,
    ambiente_id INT NOT NULL REFERENCES ambientes(id) ON DELETE CASCADE,
    documento_id INT REFERENCES documentos(id) ON DELETE SET NULL,
    tipo TEXT NOT NULL,
    conteudo TEXT NOT NULL,
    fontes JSONB NOT NULL DEFAULT '[]',
    criado_em TIMESTAMPTZ NOT NULL DEFAULT now()
);
