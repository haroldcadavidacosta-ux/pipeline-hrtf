"""Spike 2 — clic sobre la malla real. Sin alineación, sin guardar nada."""
import numpy as np
import plotly.graph_objects as go
import streamlit as st
import trimesh
from scipy.spatial import cKDTree

st.title("Prueba 2 — clic sobre la malla real")

ruta = st.text_input("Ruta de la malla", r"datos\entrada\3Dmesh_orig.stl")
if not ruta:
    st.stop()


@st.cache_data(show_spinner="Cargando malla…")
def cargar(ruta, n_nube):
    m = trimesh.load(ruta, process=False)
    v = np.asarray(m.vertices, dtype=float)
    paso = max(1, len(v) // n_nube)
    return v, v[::paso]


@st.cache_resource
def arbol(_vert, clave):
    return cKDTree(_vert)


try:
    vert, nube = cargar(ruta, 50_000)
except Exception as e:
    st.error(f"No se pudo cargar: {e}")
    st.stop()

dim = vert.max(0) - vert.min(0)
st.write(f"Vértices totales: {len(vert):,}  ·  mostrados: {len(nube):,}")
st.write(f"Caja envolvente: {dim[0]:.1f} × {dim[1]:.1f} × {dim[2]:.1f}")

fig = go.Figure(go.Scatter3d(
    x=nube[:, 0], y=nube[:, 1], z=nube[:, 2], mode="markers",
    marker=dict(size=1.6, color="#2a78d6", opacity=0.6), hoverinfo="skip"))
fig.update_layout(height=650, margin=dict(l=0, r=0, t=0, b=0),
                  showlegend=False, scene=dict(aspectmode="data"))

ev = st.plotly_chart(fig, use_container_width=True, on_select="rerun", key="visor")

sel = (ev or {}).get("selection", {}).get("points", [])
if sel:
    s = sel[-1]
    xyz = np.array([s["x"], s["y"], s["z"]]) if "x" in s else nube[s["point_index"]]
    dist, i = arbol(vert, ruta).query(xyz)
    st.success(
        f"Clic en {np.round(xyz, 3)}  →  vértice {i} "
        f"en {np.round(vert[i], 3)}  (a {dist:.4f} de distancia)")
else:
    st.info("Gira la cabeza, acércate a una oreja, y haz clic sobre ella.")
