import streamlit as st

from studyrag import documentos, generation, rag_service, storage
from studyrag.errors import StudyRAGError

st.set_page_config(page_title="StudyRAG", page_icon="📚", layout="wide")


@st.cache_resource
def _init_db() -> bool:
    storage.init_db()
    return True


try:
    _init_db()
except Exception as exc:
    st.error(
        "Não consegui conectar ao PostgreSQL. Suba o banco com `docker compose up -d` "
        "e confira o `DATABASE_URL` no `.env`."
    )
    st.code(str(exc))
    st.stop()


def mostrar_fontes(fontes):
    if not fontes:
        return
    st.markdown("**Fontes utilizadas**")
    for f in fontes:
        sim = f" · similaridade {f['similaridade']:.2f}" if "similaridade" in f else ""
        titulo = f"{f['arquivo']} — página {f['pagina']}{sim}"
        if f.get("trecho"):
            with st.expander(titulo):
                st.write(f["trecho"])
        else:
            st.caption(titulo)


def seletor_documento(docs, key):
    nomes = {d["id"]: d["nome_arquivo"] for d in docs}
    return st.selectbox(
        "Material",
        [None] + list(nomes),
        format_func=lambda i: "Todos os PDFs do ambiente" if i is None else nomes[i],
        key=key,
    )


st.sidebar.title("Study")
st.sidebar.caption("Protótipo acadêmico de apoio ao estudo. As respostas podem conter erros: confira a página-fonte.")

ambientes = storage.list_ambientes()

with st.sidebar.expander("Novo ambiente de estudo", expanded=not ambientes):
    with st.form("novo_ambiente", clear_on_submit=True):
        nome = st.text_input("Nome *", placeholder="Banco de Dados — 3º período")
        area = st.text_input("Área", placeholder="Computação")
        materia = st.text_input("Matéria", placeholder="Banco de Dados")
        assunto = st.text_input("Assunto", placeholder="Normalização")
        periodo = st.text_input("Período", placeholder="3º período")
        if st.form_submit_button("Criar ambiente"):
            if not nome.strip():
                st.error("Informe pelo menos o nome do ambiente.")
            else:
                storage.create_ambiente(nome.strip(), area.strip(), materia.strip(), assunto.strip(), periodo.strip())
                st.rerun()

if not ambientes:
    st.info("Crie seu primeiro ambiente de estudo na barra lateral para começar.")
    st.stop()

amb = st.sidebar.selectbox("Ambiente ativo", ambientes, format_func=lambda a: a["nome"])
diagnostico = st.sidebar.checkbox("Modo diagnóstico")

detalhes = " · ".join(x for x in [amb["area"], amb["materia"], amb["assunto"], amb["periodo"]] if x)
st.title(amb["nome"])
if detalhes:
    st.caption(detalhes)

tab_docs, tab_perg, tab_resumo, tab_quest, tab_hist = st.tabs(
    ["Documentos", "Perguntar", "Resumo", "Questões", "Histórico"]
)

with tab_docs:
    arquivo = st.file_uploader("Enviar PDF", type=["pdf"], key=f"upload_{amb['id']}")
    if arquivo and st.button("Processar PDF"):
        with st.spinner("Extraindo texto e gerando embeddings (a primeira vez baixa o modelo)..."):
            try:
                r = documentos.enviar_pdf(amb["id"], arquivo.name, arquivo.getvalue())
                st.success(f"PDF processado em {r['segundos']:.1f}s: {r['paginas']} páginas, {r['trechos']} trechos.")
            except StudyRAGError as exc:
                st.error(str(exc))

    docs = storage.list_documentos(amb["id"])
    if not docs:
        st.info("Nenhum PDF neste ambiente ainda.")
    for d in docs:
        c1, c2 = st.columns([5, 1])
        info = f"**{d['nome_arquivo']}** — {d['status']}"
        if d["status"] == "processado":
            info += f" ({d['num_paginas']} páginas, {d['num_trechos']} trechos)"
        c1.markdown(info)
        if d["erro"] and d["status"] == "erro":
            c1.caption(d["erro"])
        if c2.button("Reprocessar", key=f"re_{d['id']}"):
            with st.spinner("Reprocessando..."):
                try:
                    documentos.reprocessar(d["id"])
                    st.rerun()
                except StudyRAGError as exc:
                    st.error(str(exc))

docs = storage.list_documentos(amb["id"])
prontos = [d for d in docs if d["status"] == "processado"]
SEM_PDF = "Nenhum PDF processado. Envie um arquivo na aba Documentos."

with tab_perg:
    if not prontos:
        st.warning(SEM_PDF)
    else:
        doc_id = seletor_documento(prontos, f"doc_perg_{amb['id']}")
        pergunta = st.text_input("Sua pergunta sobre o material", key=f"perg_{amb['id']}")
        if st.button("Perguntar") :
            with st.spinner("Buscando trechos e gerando a resposta..."):
                try:
                    st.session_state[f"resp_{amb['id']}"] = rag_service.responder(amb["id"], pergunta, doc_id)
                except StudyRAGError as exc:
                    st.error(str(exc))
        r = st.session_state.get(f"resp_{amb['id']}")
        if r:
            (st.write if r["encontrou"] else st.warning)(r["texto"])
            mostrar_fontes(r["fontes"])
            if diagnostico:
                st.json(r["diagnostico"])

with tab_resumo:
    if not prontos:
        st.warning(SEM_PDF)
    else:
        doc_id = seletor_documento(prontos, f"doc_res_{amb['id']}")
        if st.button("Gerar resumo"):
            with st.spinner("Gerando resumo..."):
                try:
                    st.session_state[f"res_{amb['id']}"] = generation.gerar_resumo(amb["id"], doc_id)
                except StudyRAGError as exc:
                    st.error(str(exc))
        r = st.session_state.get(f"res_{amb['id']}")
        if r:
            st.markdown(r["texto"])
            paginas = ", ".join(f"{f['arquivo']} p.{f['pagina']}" for f in r["fontes"])
            st.caption(f"Trechos considerados: {paginas}")

with tab_quest:
    if not prontos:
        st.warning(SEM_PDF)
    else:
        doc_id = seletor_documento(prontos, f"doc_q_{amb['id']}")
        qtd = st.slider("Quantidade de questões", 3, 10, 5)
        if st.button("Gerar questões"):
            with st.spinner("Gerando questões..."):
                try:
                    st.session_state[f"q_{amb['id']}"] = generation.gerar_questoes(amb["id"], doc_id, qtd)
                except StudyRAGError as exc:
                    st.error(str(exc))
        r = st.session_state.get(f"q_{amb['id']}")
        if r:
            for i, q in enumerate(r["questoes"], start=1):
                st.markdown(f"**{i}. {q['pergunta']}**")
                with st.expander("Ver gabarito"):
                    st.write(q["resposta"])
                    if q.get("pagina"):
                        st.caption(f"Página {q['pagina']}")

with tab_hist:
    hist = storage.list_historico(amb["id"])
    if not hist:
        st.info("Nenhuma pergunta feita neste ambiente ainda.")
    for h in hist:
        st.markdown(f"**{h['pergunta']}**")
        st.write(h["resposta"])
        if h["fontes"]:
            st.caption("Fontes: " + "; ".join(f"{f['arquivo']} p.{f['pagina']}" for f in h["fontes"]))
        st.divider()
