# StudyRAG — Assistente acadêmico com RAG

Protótipo acadêmico: o aluno cria um **ambiente de estudo**, envia **PDFs**, faz perguntas e recebe respostas **baseadas no material**, com **arquivo e página** como fonte. Também gera **resumo** e **questões com gabarito**.

## Como o RAG funciona aqui

```
PDF → PyMuPDF (texto por página) → chunking (900 car., sobreposição 150)
    → embeddings locais (Sentence Transformers) → PostgreSQL + pgvector

Pergunta → embedding → busca por similaridade (top 5, só do ambiente)
         → se nada passar do limite mínimo: "não encontrei no material"
         → prompt com os trechos delimitados → IA responde só com o contexto
         → resposta + fontes (as mesmas páginas enviadas ao modelo)
```

## Decisões (Plan.md)

| Item | Escolha |
|---|---|
| Interface | Streamlit |
| Banco | PostgreSQL 16 + pgvector (Docker Compose) |
| Embeddings | `paraphrase-multilingual-MiniLM-L12-v2`, local (384 dim.) |
| IA de resposta | API compatível com OpenAI (ou Ollama local via `LLM_BASE_URL`) |
| PDF | PyMuPDF |

## Como executar

Requisitos: Python 3.11+, Docker, chave de uma API de IA (ou Ollama).

```bash
docker compose up -d                 # sobe o PostgreSQL com pgvector
python -m venv .venv
source .venv/bin/activate            # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env                 # Windows: copy .env.example .env  -> preencha LLM_API_KEY
streamlit run app.py
```

As tabelas são criadas sozinhas na primeira execução (`schema.sql`). Na primeira indexação, o modelo de embeddings (~120 MB) é baixado; depois funciona offline. Para execução 100% offline, use o Ollama: `LLM_BASE_URL=http://localhost:11434/v1`, `LLM_MODEL=llama3.1` e deixe `LLM_API_KEY` vazio.

## Roteiro da demonstração

1. Criar o ambiente (ex.: "Sistemas Operacionais").
2. Enviar um PDF textual pequeno e esperar "PDF processado".
3. Perguntar 3 coisas que estão no PDF e abrir as fontes (arquivo + página).
4. Perguntar algo que **não** está no PDF → aviso "não encontrei no material".
5. Gerar resumo e 5 questões com gabarito.
6. Ligar o "Modo diagnóstico" para mostrar trechos recuperados e similaridade.

## Testes

```bash
pytest
```

Cobrem: extração com página, PDF inválido/vazio/sem texto, chunking e metadados, fontes iguais aos trechos enviados, pergunta fora do material (a IA nem é chamada) e geração de questões (IA simulada).

## Ajustes úteis (.env)

`MIN_SIMILARITY` (0.30): sobe para recusar mais, desce para aceitar mais. `TOP_K`, `CHUNK_SIZE`, `CHUNK_OVERLAP`, `MAX_PDF_MB`.

## Estrutura

```
app.py                  interface Streamlit
schema.sql              migration inicial (PostgreSQL + pgvector)
studyrag/
  pdf_processor.py      extração por página e chunking
  vector_store.py       embeddings
  storage.py            todo o SQL
  documentos.py         upload e indexação
  rag_service.py        recuperação + prompt + resposta com fontes
  generation.py         resumo e questões
  llm.py                chamada à API de IA
tests/test_pipeline.py
```

## Limitações

Sem OCR (PDF escaneado é rejeitado com aviso), sem login, uso por uma pessoa por vez, só PDF. A IA pode errar: por isso cada resposta mostra a página para conferência.
