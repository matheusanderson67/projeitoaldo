
import hashlib
import re
import time
from pathlib import Path

from . import config, storage
from .errors import DocumentoError, PDFError
from .pdf_processor import chunk_pages, extract_pages
from .vector_store import embed


def _nome_seguro(nome: str) -> str:
    return re.sub(r"[^\w.\-]", "_", Path(nome).name) or "documento.pdf"


def _indexar(doc_id: int, ambiente_id: int, caminho) -> dict:
    inicio = time.perf_counter()
    storage.set_status(doc_id, "processando")
    try:
        pages = extract_pages(caminho)
        chunks = chunk_pages(pages, config.CHUNK_SIZE, config.CHUNK_OVERLAP)
        vectors = embed([c["texto"] for c in chunks])
        storage.replace_index(doc_id, ambiente_id, pages, chunks, vectors)
        storage.set_status(doc_id, "processado", num_paginas=len(pages), num_trechos=len(chunks))
    except PDFError as exc:
        storage.set_status(doc_id, "erro", erro=str(exc))
        raise
    except Exception as exc:
        storage.set_status(doc_id, "erro", erro=str(exc))
        raise DocumentoError(f"Falha ao processar o PDF: {exc}") from exc
    return {
        "paginas": len(pages),
        "trechos": len(chunks),
        "segundos": time.perf_counter() - inicio,
    }


def enviar_pdf(ambiente_id: int, nome_arquivo: str, dados: bytes) -> dict:
    if not dados:
        raise DocumentoError("O arquivo está vazio.")
    if len(dados) > config.MAX_PDF_MB * 1024 * 1024:
        raise DocumentoError(
            f"O arquivo passa do limite de {config.MAX_PDF_MB} MB. Divida o PDF em partes menores."
        )
    file_hash = hashlib.sha256(dados).hexdigest()
    if storage.get_documento_by_hash(ambiente_id, file_hash):
        raise DocumentoError("Este PDF já foi enviado neste ambiente (use Reprocessar, se precisar).")

    pasta = config.UPLOAD_DIR / str(ambiente_id)
    pasta.mkdir(parents=True, exist_ok=True)
    caminho = pasta / f"{file_hash[:12]}_{_nome_seguro(nome_arquivo)}"
    caminho.write_bytes(dados)

    doc_id = storage.create_documento(ambiente_id, _nome_seguro(nome_arquivo), caminho, len(dados), file_hash)
    return _indexar(doc_id, ambiente_id, caminho)


def reprocessar(doc_id: int) -> dict:
    doc = storage.get_documento(doc_id)
    if not doc or not Path(doc["caminho"]).exists():
        raise DocumentoError("O arquivo original não foi encontrado. Envie o PDF novamente.")
    return _indexar(doc_id, doc["ambiente_id"], doc["caminho"])
