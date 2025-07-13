import streamlit as st
import pandas as pd
import fitz  # PyMuPDF para extracción de texto desde PDF
import base64
import openai
import os
from io import BytesIO

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

        # Extraer texto del seguro complementario
        if plan_seguro.name.endswith(".pdf"):
            with fitz.open(stream=plan_seguro.read(), filetype="pdf") as doc:
                texto_seguro = ""
                for page in doc:
                    texto_seguro += page.get_text()
            st.session_state["texto_seguro"] = texto_seguro
            st.text_area("🧾 Texto extraído del Seguro Complementario", texto_seguro, height=200)

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
        "texto_seguro" in st.session_state
    ):
        st.markdown(f"📌 *Motivo:* {st.session_state['consulta_descripcion']}")

        prompt = f'''
Eres un asistente experto en salud previsional chilena. A partir del siguiente resumen de atención y los textos de un plan ISAPRE y un seguro complementario, entrega una estimación de reembolso y copago desglosada, considerando:

- Cobertura ISAPRE
- Cobertura seguro complementario
- Copago estimado del paciente
- Sugerencia de prestador si aplica

Motivo de atención:
{st.session_state["consulta_descripcion"]}

Plan ISAPRE:
{st.session_state["texto_isapre"]}

Seguro complementario:
{st.session_state["texto_seguro"]}
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