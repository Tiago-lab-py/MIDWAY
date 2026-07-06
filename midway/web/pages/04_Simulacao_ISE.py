import streamlit as st
from dotenv import load_dotenv

from midway.web.library.ise_janela_component import mostrar_simulacao_ise_por_janela


load_dotenv()

st.title("Simulação ISE")
st.caption("Simulação por janelas específicas, com regional, período e cálculo sob demanda.")

mostrar_simulacao_ise_por_janela()
