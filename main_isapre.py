import streamlit as st
import pandas as pd
import fitz  # PyMuPDF para extracción de texto desde PDF
import base64
import openai
import os
from io import BytesIO
import numpy as np
import json

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

def extract_tabla_isapre_from_blocks(blocks):
    # Buscamos la sección "AMBULATORIAS" y luego filas con "Consultas médicas"
    tabla = []
    seccion_ambul = False
    for b in blocks:
        text = b[4].strip()
        if "AMBULATORIAS" in text.upper():
            seccion_ambul = True
            continue
        if seccion_ambul:
            # Si encontramos un título de sección nuevo, dejamos de buscar
            if text.isupper() and text != "CONSULTAS MÉDICAS":
                break
            # Buscamos filas que contengan "Consultas médicas"
            if "Consultas médicas" in text:
                # Intentamos capturar celdas adyacentes en la misma línea (usando posición)
                # Buscamos bloques en la misma línea (aprox misma y0)
                y0 = b[1]
                y1 = b[3]
                line_blocks = [blk for blk in blocks if abs(blk[1]-y0)<5 and abs(blk[3]-y1)<5]
                # Ordenar por x0 para simular columnas
                line_blocks = sorted(line_blocks, key=lambda x: x[0])
                # Extraemos textos de celdas
                textos = [blk[4].strip() for blk in line_blocks]
                # Intentamos mapear a campos: prestacion, cobertura, prestadores
                # Suponemos que el primer texto es prestacion, luego cobertura, luego prestadores (si hay)
                prestacion = textos[0] if len(textos) > 0 else ""
                cobertura = textos[1] if len(textos) > 1 else ""
                prestadores = textos[2] if len(textos) > 2 else ""
                tabla.append({
                    "prestacion": prestacion,
                    "cobertura": cobertura,
                    "prestadores": prestadores
                })
            else:
                # También capturar filas que parezcan parte de la tabla (por posición y alineación)
                # Podríamos intentar capturar filas que estén en la misma área y tengan varias celdas
                pass
    return tabla

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
                blocks_all = []
                for page in doc:
                    texto_isapre += page.get_text()
                    blocks = page.get_text("blocks")
                    blocks_all.extend(blocks)
            st.session_state["texto_isapre"] = texto_isapre
            st.text_area("🧾 Texto extraído del Plan ISAPRE", texto_isapre, height=200)

            # Extraer tabla simulada desde bloques
            tabla_isapre = extract_tabla_isapre_from_blocks(blocks_all)
            st.session_state["tabla_isapre"] = tabla_isapre
            if tabla_isapre:
                st.markdown("### Tabla simulada extraída del Plan ISAPRE (sección AMBULATORIAS - Consultas médicas)")
                st.json(tabla_isapre)

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

        tabla_isapre_json = ""
        if "tabla_isapre" in st.session_state and st.session_state["tabla_isapre"]:
            tabla_isapre_json = json.dumps(st.session_state["tabla_isapre"], ensure_ascii=False, indent=2)

        prompt = f"""
Eres un asistente experto en salud previsional chilena.

Tu tarea es ayudar a un paciente a entender cuánto le cubrirán su ISAPRE y su seguro complementario para una atención médica que describe, considerando sus planes.

Los textos de los planes están en formato plano (texto), pero pueden contener información tabular implícita. Interprétalos como si fueran tablas visuales: por ejemplo, si encuentras "Consultas médicas" o "Cirugía ambulatoria" y más adelante en la misma línea un porcentaje como "80%", asume que eso es la cobertura. Si más adelante aparecen clínicas (como "Clínica Alemana", "Clínica Dávila", etc.), entiéndelo como prestadores preferentes o con convenio.

Haz lo mismo con los seguros complementarios: si encuentras secciones como "Sobre Reembolso Instituciones de Salud", interpreta que ese porcentaje se aplica al copago que no cubre la ISAPRE.

El usuario ha indicado:

📌 Motivo de atención:
{st.session_state["consulta_descripcion"]}

📄 Fragmentos relevantes del Plan ISAPRE:
{"\n\n".join(top_isapre_chunks)}

📄 Fragmentos relevantes del Seguro complementario:
{"\n\n".join(top_seguro_chunks)}

Si también hay una tabla estructurada ISAPRE, úsala como fuente prioritaria de verdad para cálculos.

Haz un análisis con desglose y explica qué cubre cada entidad y qué copago queda para el paciente.
"""

        if tabla_isapre_json:
            prompt += f"\n\nAdemás, aquí tienes una tabla estructurada extraída del plan ISAPRE que puedes usar como referencia confiable para las coberturas:\n{tabla_isapre_json}\n"

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