import streamlit as st

st.title("Hola")
nombre = st.text_input("¿Cómo te llamas?")
if nombre:
    st.write(f"Mucho gusto, {nombre}")
