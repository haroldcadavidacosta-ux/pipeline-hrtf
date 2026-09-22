import streamlit as st
import plotly.graph_objects as go

st.title("Prueba de clic en 3D")
st.write("Gira la escena arrastrando, y luego haz clic sobre una de las bolas.")

fig = go.Figure(go.Scatter3d(
    x=[0, 1, 2], y=[0, 1, 0], z=[0, 0, 1],
    mode="markers", marker=dict(size=14)))
fig.update_layout(height=500, margin=dict(l=0, r=0, t=0, b=0))

evento = st.plotly_chart(fig, on_select="rerun", key="spike")

st.write("Evento recibido:")
st.json(evento)
