import streamlit as st
import pandas as pd
import fitz  # PyMuPDF para extracción de texto desde PDF
import base64
import openai
import os
from io import BytesIO
import numpy as np

client = openai.OpenAI(api_key=st.secrets["OPENAI_API_KEY"])

st.set_page_config(page_title="Simulador ISAPRE y Seguro Complementario", page_icon="💊")
st.title("💊 Simulador de Reembolsos de Salud - ISAPRE + Seguro Complementario")

# Tabs
tab1, tab2, tab3, tab4 = st.tabs([
    "📥 Subir planes",
    "💬 Consulta médica",
    "💰 Simular reembolso",
    "🏥 Prestadores sugeridos"
])

def chunk_text(text, max_len=500):
    paragraphs = text.split('\n')
    chunks = []
    current_chunk = ""
    for para in paragraphs:
        if len(current_chunk) + len(para) + 1 <= max_len:
            current_chunk += para + "\n"
        else:
            if current_chunk:
                chunks.append(current_chunk.strip())
            current_chunk = para + "\n"
    if current_chunk:
        chunks.append(current_chunk.strip())
    return chunks

def get_embedding(text):
    response = client.embeddings.create(
        input=text,
        model="text-embedding-ada-002"
    )
    return np.array(response.data[0].embedding)

def cosine_similarity(a, b):
    return np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b))

# Tab 1: Subir planes
with tab1:
    st.header("📥 Subir tus planes")
    st.markdown("Sube aquí tu plan de ISAPRE y tu seguro complementario en formato PDF, Excel o imagen (lo leeremos y estructuraremos).")

    plan_isapre = st.file_uploader("📄 Plan ISAPRE", type=["pdf", "xlsx", "jpg", "png"])
    plan_seguro = st.file_uploader("📄 Seguro Complementario", type=["pdf", "xlsx", "jpg", "png"])

    if plan_isapre:
        st.success("Plan ISAPRE subido correctamente.")
    if plan_seguro:
        st.success("Seguro complementario subido correctamente.")

    if plan_isapre and plan_seguro:
        st.info("Ambos documentos subidos. Puedes continuar a la siguiente pestaña.")

        # Extraer texto del plan ISAPRE
        if plan_isapre.name.endswith(".pdf"):
            with fitz.open(stream=plan_isapre.read(), filetype="pdf") as doc:
                texto_isapre = ""
                for page in doc:
                    texto_isapre += page.get_text()
            st.session_state["texto_isapre"] = texto_isapre
            st.text_area("🧾 Texto extraído del Plan ISAPRE", texto_isapre, height=200)

            # Crear chunks y embeddings para ISAPRE
            chunks_isapre = chunk_text(texto_isapre, max_len=500)
            embeddings_isapre = [get_embedding(chunk) for chunk in chunks_isapre]
            st.session_state["chunks_isapre"] = list(zip(chunks_isapre, embeddings_isapre))

        # Extraer texto del seguro complementario
        if plan_seguro.name.endswith(".pdf"):
            with fitz.open(stream=plan_seguro.read(), filetype="pdf") as doc:
                texto_seguro = ""
                for page in doc:
                    texto_seguro += page.get_text()
            st.session_state["texto_seguro"] = texto_seguro
            st.text_area("🧾 Texto extraído del Seguro Complementario", texto_seguro, height=200)

            # Crear chunks y embeddings para seguro complementario
            chunks_seguro = chunk_text(texto_seguro, max_len=500)
            embeddings_seguro = [get_embedding(chunk) for chunk in chunks_seguro]
            st.session_state["chunks_seguro"] = list(zip(chunks_seguro, embeddings_seguro))

        # (nada)

# Tab 2: Consulta médica
with tab2:
    st.header("💬 ¿Qué atención médica necesitas?")
    consulta_texto = st.text_area("Describe tu atención en lenguaje natural", placeholder="Ej: Tengo un dolor abdominal y quiero ir al gastroenterólogo...")

    if consulta_texto:
        st.success("Consulta registrada. Pronto estimaremos tu cobertura.")
        st.session_state["consulta_descripcion"] = consulta_texto

# Tab 3: Simulación
with tab3:
    st.header("💰 Estimación de Reembolso")
    if (
        "consulta_descripcion" in st.session_state and
        "texto_isapre" in st.session_state and
        "texto_seguro" in st.session_state and
        "chunks_isapre" in st.session_state and
        "chunks_seguro" in st.session_state
    ):
        st.markdown(f"📌 *Motivo:* {st.session_state['consulta_descripcion']}")

        # Embedding consulta
        consulta_embedding = get_embedding(st.session_state["consulta_descripcion"])

        # Función para obtener top 3 chunks más similares
        def get_top_chunks(chunks_with_embeds, query_emb, top_k=3):
            sims = []
            for chunk, emb in chunks_with_embeds:
                sim = cosine_similarity(query_emb, emb)
                sims.append((sim, chunk))
            sims.sort(key=lambda x: x[0], reverse=True)
            return [chunk for _, chunk in sims[:top_k]]

        top_isapre_chunks = get_top_chunks(st.session_state["chunks_isapre"], consulta_embedding, top_k=3)
        top_seguro_chunks = get_top_chunks(st.session_state["chunks_seguro"], consulta_embedding, top_k=3)

        prompt = f'''
Eres un asistente experto en salud previsional chilena. A partir del siguiente resumen de atención y los textos relevantes de un plan ISAPRE y un seguro complementario, entrega una estimación de reembolso y copago desglosada, considerando:

- Cobertura ISAPRE
- Cobertura seguro complementario
- Copago estimado del paciente
- Sugerencia de prestador si aplica

Motivo de atención:
{st.session_state["consulta_descripcion"]}

Fragmentos relevantes del Plan ISAPRE:
{"\n\n".join(top_isapre_chunks)}

Fragmentos relevantes del Seguro complementario:
{"\n\n".join(top_seguro_chunks)}
'''

        with st.spinner("Analizando cobertura y calculando estimación..."):
            response = client.chat.completions.create(
                model="gpt-4",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3
            )
            resultado = response.choices[0].message.content.strip()
            st.markdown("### 💸 Resultado de la estimación")
            st.markdown(resultado)
    else:
        st.warning("Por favor completa la descripción y asegúrate de haber subido ambos planes.")

# Tab 4: Prestadores sugeridos
with tab4:
    st.header("🏥 Prestadores sugeridos")
    if "consulta_descripcion" in st.session_state:
        st.markdown("Según tu plan, estos son los prestadores donde podrías atenderte con menor copago:")
        st.markdown("- Clínica Alemana (convenio preferente)")
        st.markdown("- UC Christus (reembolso 90%)")
        st.markdown("- Integramédica (bonificación inmediata)")
        st.info("🔄 Esta sugerencia será dinámica cuando integremos tu plan real.")
    else:
        st.warning("Completa tu motivo de consulta para ver recomendaciones.")