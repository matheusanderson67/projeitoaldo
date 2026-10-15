import fitz
import numpy as np
import pytest

from studyrag import generation, rag_service
from studyrag.errors import LLMError, PDFError
from studyrag.pdf_processor import chunk_pages, chunk_text, extract_pages


def make_pdf(path, paginas):
    doc = fitz.open()
    for texto in paginas:
        page = doc.new_page()
        if texto:
            page.insert_text((72, 72), texto)
    doc.save(str(path))
    doc.close()


# ---------- extração e chunking ----------
def test_extrai_texto_com_numero_da_pagina(tmp_path):
    pdf = tmp_path / "aula.pdf"
    make_pdf(pdf, ["Processo e programa em execucao", "Thread e fluxo de execucao"])
    pages = extract_pages(pdf)
    assert [n for n, _ in pages] == [1, 2]
    assert "Processo" in pages[0][1] and "Thread" in pages[1][1]


def test_pdf_invalido_ou_vazio_gera_erro_tratado(tmp_path):
    ruim = tmp_path / "ruim.pdf"
    ruim.write_bytes(b"isto nao e um pdf")
    vazio = tmp_path / "vazio.pdf"
    vazio.write_bytes(b"")
    for caminho in (ruim, vazio):
        with pytest.raises(PDFError):
            extract_pages(caminho)


def test_pdf_sem_texto_gera_erro_tratado(tmp_path):
    pdf = tmp_path / "branco.pdf"
    make_pdf(pdf, [""])
    with pytest.raises(PDFError, match="OCR"):
        extract_pages(pdf)


def test_chunking_respeita_tamanho_e_sobreposicao():
    texto = " ".join(f"palavra{i}" for i in range(600))
    chunks = chunk_text(texto, size=900, overlap=150)
    assert len(chunks) > 1
    assert all(len(c) <= 900 for c in chunks)
    assert chunks[1][:20] in chunks[0]  # sobreposição


def test_chunks_mantem_pagina_de_origem():
    pages = [(1, "texto da pagina um " * 5), (2, ""), (3, "texto da pagina tres " * 5)]
    chunks = chunk_pages(pages, size=900, overlap=150)
    assert [c["pagina"] for c in chunks] == [1, 3]
    assert [c["indice"] for c in chunks] == [0, 1]


# ---------- RAG (banco, embeddings e IA simulados) ----------
def preparar(monkeypatch, hits, resposta_llm):
    chamadas = []
    monkeypatch.setattr(rag_service, "embed", lambda t: np.zeros((len(t), 384), dtype=np.float32))
    monkeypatch.setattr(rag_service.storage, "search", lambda *a, **k: hits)
    monkeypatch.setattr(rag_service.storage, "save_qa", lambda *a, **k: None)
    monkeypatch.setattr(rag_service, "llm_chat", lambda s, u, **k: chamadas.append(u) or resposta_llm)
    return chamadas


HIT = {"texto": "Thread é a menor unidade de execução.", "pagina": 5, "arquivo": "aula02.pdf", "similaridade": 0.7}


def test_resposta_traz_fontes_dos_trechos_enviados_ao_modelo(monkeypatch):
    chamadas = preparar(monkeypatch, [HIT], "Uma thread é... (aula02.pdf, p. 5)")
    r = rag_service.responder(1, "O que é thread?")
    assert r["encontrou"] and r["fontes"][0]["arquivo"] == "aula02.pdf" and r["fontes"][0]["pagina"] == 5
    assert "página 5" in chamadas[0]


def test_pergunta_fora_do_material_nao_chama_a_ia(monkeypatch):
    longe = dict(HIT, similaridade=0.05)
    chamadas = preparar(monkeypatch, [longe], "não deveria ser usado")
    r = rag_service.responder(1, "Quem ganhou a Copa de 1994?")
    assert not r["encontrou"] and r["fontes"] == [] and chamadas == []
    assert "Não encontrei" in r["texto"]


def test_modelo_pode_recusar_quando_contexto_nao_responde(monkeypatch):
    preparar(monkeypatch, [HIT], "NAO_ENCONTRADO")
    r = rag_service.responder(1, "Qual a capital da França?")
    assert not r["encontrou"] and r["fontes"] == []


# ---------- resumo e questões ----------
def test_parse_questoes_aceita_json_com_cerca_de_codigo():
    bruto = '```json\n{"questoes": [{"pergunta": "P?", "resposta": "R", "pagina": 2}]}\n```'
    assert generation.parse_questoes(bruto)[0]["resposta"] == "R"


def test_parse_questoes_formato_invalido():
    with pytest.raises(LLMError):
        generation.parse_questoes("desculpe, não consegui")


def test_gerar_questoes_com_mock(monkeypatch):
    chunks = [{"texto": "conteúdo", "pagina": 1, "arquivo": "a.pdf"}]
    monkeypatch.setattr(generation.storage, "get_chunks", lambda *a: chunks)
    monkeypatch.setattr(generation.storage, "save_geracao", lambda *a, **k: None)
    monkeypatch.setattr(
        generation, "llm_chat", lambda *a, **k: '{"questoes": [{"pergunta": "P", "resposta": "R", "pagina": 1}]}'
    )
    r = generation.gerar_questoes(1, None, 1)
    assert r["questoes"][0]["pergunta"] == "P" and r["fontes"] == [{"arquivo": "a.pdf", "pagina": 1}]
