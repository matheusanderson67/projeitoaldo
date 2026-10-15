@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo Iniciando o StudyRAG... (nao feche esta janela)
call .venv\Scripts\activate.bat
set DATABASE_URL=postgresql://studyrag:studyrag@localhost:5433/studyrag
set LLM_API_KEY=ollama
set LLM_BASE_URL=http://localhost:11434/v1
set LLM_MODEL=llama3.2
set MIN_SIMILARITY=0.15
set MAX_CONTEXT_CHUNKS=5
docker compose up -d
streamlit run app.py
pause
