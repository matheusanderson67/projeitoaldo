from contextlib import contextmanager
from pathlib import Path

import psycopg
from pgvector.psycopg import register_vector
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from . import config

SCHEMA_PATH = Path(__file__).resolve().parent.parent / "schema.sql"


def init_db() -> None:
    with psycopg.connect(config.DATABASE_URL, autocommit=True) as c:
        for stmt in SCHEMA_PATH.read_text(encoding="utf-8").split(";"):
            if stmt.strip():
                c.execute(stmt)


@contextmanager
def conn():
    c = psycopg.connect(config.DATABASE_URL, row_factory=dict_row)
    try:
        register_vector(c)
        yield c
        c.commit()
    except Exception:
        c.rollback()
        raise
    finally:
        c.close()


def create_ambiente(nome, area=None, materia=None, assunto=None, periodo=None) -> int:
    with conn() as c:
        row = c.execute(
            "INSERT INTO ambientes (nome, area, materia, assunto, periodo) "
            "VALUES (%s, %s, %s, %s, %s) RETURNING id",
            (nome, area or None, materia or None, assunto or None, periodo or None),
        ).fetchone()
        return row["id"]


def list_ambientes() -> list[dict]:
    with conn() as c:
        return c.execute("SELECT * FROM ambientes ORDER BY id DESC").fetchall()


def create_documento(ambiente_id, nome_arquivo, caminho, tamanho, file_hash) -> int:
    with conn() as c:
        row = c.execute(
            "INSERT INTO documentos (ambiente_id, nome_arquivo, caminho, tamanho_bytes, hash, status) "
            "VALUES (%s, %s, %s, %s, %s, 'pendente') RETURNING id",
            (ambiente_id, nome_arquivo, str(caminho), tamanho, file_hash),
        ).fetchone()
        return row["id"]


def get_documento(doc_id) -> dict | None:
    with conn() as c:
        return c.execute("SELECT * FROM documentos WHERE id = %s", (doc_id,)).fetchone()


def get_documento_by_hash(ambiente_id, file_hash) -> dict | None:
    with conn() as c:
        return c.execute(
            "SELECT * FROM documentos WHERE ambiente_id = %s AND hash = %s",
            (ambiente_id, file_hash),
        ).fetchone()


def list_documentos(ambiente_id) -> list[dict]:
    with conn() as c:
        return c.execute(
            "SELECT * FROM documentos WHERE ambiente_id = %s ORDER BY id", (ambiente_id,)
        ).fetchall()


def set_status(doc_id, status, erro=None, num_paginas=None, num_trechos=None) -> None:
    with conn() as c:
        c.execute(
            "UPDATE documentos SET status = %s, erro = %s, "
            "num_paginas = COALESCE(%s, num_paginas), num_trechos = COALESCE(%s, num_trechos) "
            "WHERE id = %s",
            (status, erro, num_paginas, num_trechos, doc_id),
        )


def replace_index(doc_id, ambiente_id, pages, chunks, vectors) -> None:
    with conn() as c:
        c.execute("DELETE FROM trechos WHERE documento_id = %s", (doc_id,))
        c.execute("DELETE FROM paginas WHERE documento_id = %s", (doc_id,))
        with c.cursor() as cur:
            cur.executemany(
                "INSERT INTO paginas (documento_id, numero, texto) VALUES (%s, %s, %s)",
                [(doc_id, n, t) for n, t in pages],
            )
            cur.executemany(
                "INSERT INTO trechos (documento_id, ambiente_id, pagina, indice, texto, embedding) "
                "VALUES (%s, %s, %s, %s, %s, %s)",
                [
                    (doc_id, ambiente_id, ch["pagina"], ch["indice"], ch["texto"], vec)
                    for ch, vec in zip(chunks, vectors)
                ],
            )


def search(ambiente_id, query_vec, k, documento_id=None) -> list[dict]:
    with conn() as c:
        return c.execute(
            """
            SELECT t.texto, t.pagina, d.nome_arquivo AS arquivo,
                   1 - (t.embedding <=> %(q)s) AS similaridade
            FROM trechos t JOIN documentos d ON d.id = t.documento_id
            WHERE t.ambiente_id = %(amb)s
              AND (%(doc)s::int IS NULL OR t.documento_id = %(doc)s)
            ORDER BY t.embedding <=> %(q)s
            LIMIT %(k)s
            """,
            {"q": query_vec, "amb": ambiente_id, "doc": documento_id, "k": k},
        ).fetchall()


def get_chunks(ambiente_id, documento_id=None) -> list[dict]:
    with conn() as c:
        return c.execute(
            """
            SELECT t.texto, t.pagina, d.nome_arquivo AS arquivo
            FROM trechos t JOIN documentos d ON d.id = t.documento_id
            WHERE t.ambiente_id = %(amb)s
              AND (%(doc)s::int IS NULL OR t.documento_id = %(doc)s)
            ORDER BY t.documento_id, t.pagina, t.indice
            """,
            {"amb": ambiente_id, "doc": documento_id},
        ).fetchall()


def save_qa(ambiente_id, pergunta, resposta, fontes) -> None:
    with conn() as c:
        pid = c.execute(
            "INSERT INTO perguntas (ambiente_id, texto) VALUES (%s, %s) RETURNING id",
            (ambiente_id, pergunta),
        ).fetchone()["id"]
        c.execute(
            "INSERT INTO respostas (pergunta_id, texto, fontes) VALUES (%s, %s, %s)",
            (pid, resposta, Jsonb(fontes)),
        )


def list_historico(ambiente_id, limit=50) -> list[dict]:
    with conn() as c:
        return c.execute(
            "SELECT p.texto AS pergunta, r.texto AS resposta, r.fontes, p.criado_em "
            "FROM perguntas p JOIN respostas r ON r.pergunta_id = p.id "
            "WHERE p.ambiente_id = %s ORDER BY p.id DESC LIMIT %s",
            (ambiente_id, limit),
        ).fetchall()


def save_geracao(ambiente_id, documento_id, tipo, conteudo, fontes) -> None:
    with conn() as c:
        c.execute(
            "INSERT INTO geracoes (ambiente_id, documento_id, tipo, conteudo, fontes) "
            "VALUES (%s, %s, %s, %s, %s)",
            (ambiente_id, documento_id, tipo, conteudo, Jsonb(fontes)),
        )
