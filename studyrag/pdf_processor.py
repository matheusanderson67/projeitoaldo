
import re

import fitz 

from .errors import PDFError


def extract_pages(path) -> list[tuple[int, str]]:
    try:
        doc = fitz.open(str(path), filetype="pdf")
    except Exception as exc:
        raise PDFError("O arquivo não pôde ser processado: está vazio ou corrompido.") from exc

    with doc:
        pages = [(i, page.get_text("text").strip()) for i, page in enumerate(doc, start=1)]

    if not pages or not any(text for _, text in pages):
        raise PDFError(
            "Este PDF não tem texto extraível (provavelmente é escaneado). "
            "OCR não faz parte do MVP; use um PDF textual."
        )
    return pages


def chunk_text(text: str, size: int = 900, overlap: int = 150) -> list[str]:

    if overlap >= size:
        raise ValueError("overlap deve ser menor que size")
    text = re.sub(r"\s+", " ", text).strip()
    chunks, start, n = [], 0, len(text)
    while start < n:
        end = min(start + size, n)
        if end < n: 
            cut = text.rfind(". ", start, end)
            if cut < start + size // 2:
                cut = text.rfind(" ", start, end)
            if cut > start + size // 2:
                end = cut + 1
        piece = text[start:end].strip()
        if piece:
            chunks.append(piece)
        if end >= n:
            break
        start = max(end - overlap, start + 1)
    return chunks


def chunk_pages(pages, size: int = 900, overlap: int = 150) -> list[dict]:

    result, indice = [], 0
    for numero, text in pages:
        for piece in chunk_text(text, size, overlap):
            result.append({"pagina": numero, "indice": indice, "texto": piece})
            indice += 1
    return result
