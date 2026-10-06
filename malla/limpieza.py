"""Limpieza automática de escaneos de cabeza (KIRI Engine). Solo geometría, sin interfaz.

Se ejecuta desde limpiar_malla.py (raíz del repo). Decisiones de diseño: malla/LIMPIEZA.md

Pasos:
  1. Carga la malla y la lleva al sistema anatómico usando la matriz del JSON de
     landmarks (+x adelante, +y izquierda, +z arriba, origen interaural).
  2. Quita las piezas flotantes: se queda SOLO con la componente conexa más grande.
  3. Quita la "cresta": la parte superior de la cabeza que el escáner no vio y que
     la reconstrucción rellenó con una especie de carpa. Se ajusta un elipsoide
     al cráneo (banda lateral, que sí está bien escaneada) y en el casquete
     superior se eliminan los vértices que no coinciden con él.
  4. Reparación topológica básica.
  5. Reconstrucción Screened Poisson: puntos originales + puntos del elipsoide
     donde quedó el hueco + tapa plana en el cuello  ->  malla cerrada.
  6. Alisado del casco (pelo, pozos, pliegues) y del ruido fino de la cara, sin tocar
     las orejas -> 3_suavizada.ply (--suavizar 0 desactiva los dos).
  7. Control de calidad: topología + proporciones del cráneo (+ escala, si la hay). Si
     falla -> pedir nuevo escaneo. Avisa (sin bloquear) si una concha salió poco profunda.
  8. Escala real (opcional): con el AID o la circunferencia medidos en la persona se
     escala a milímetros -> malla_final_mm.ply.

Todas las distancias se expresan como fracción del AID (distancia interaural),
así no dependen de la escala arbitraria del escaneo.
"""
import json
import shutil
import tempfile
import uuid
from pathlib import Path

import numpy as np
import pymeshlab
from scipy.optimize import least_squares
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import connected_components
from scipy.spatial import Delaunay, cKDTree

import config
from malla.oreja import largos as largos_oreja
from malla.oreja import metricas as metricas_oreja

# --- Parámetros (en unidades de AID) -----------------------------------------
BANDA_AJUSTE = (0.25, 0.85)     # alturas usadas para ajustar el elipsoide del cráneo
CARA_X, CARA_Z = 0.45, 0.60     # se excluye la cara (x > CARA_X y z < CARA_Z) del ajuste
INICIO_CASQUETE = 0.70          # el casquete empieza en z = cz + 0.70 * radio vertical
# |distancia al elipsoide| aceptada en el casquete. Se prueba en orden: si Poisson sale
# con túneles (genus > 0) se reintenta con la siguiente, más estricta.
TOLERANCIAS = (0.06, 0.045, 0.035, 0.025)   # 0.06 AID ~ 9 mm
COS_NORMAL = 0.5                # la normal debe apuntar hacia afuera del elipsoide (cos > 0.5)
ANILLOS_EXTRA = 4               # anillos de vecinos que se quitan alrededor de lo detectado
MARGEN_CUELLO = 0.02            # el corte del cuello queda justo por encima del borde abierto
CUELLO_MAS_BAJO = -1.6          # AID: hasta dónde se busca un plano limpio para la tapa del cuello
PASO_CUELLO = 0.02              # AID: paso de esa búsqueda (~3 mm)
BAJADA_CUELLO_MIN = 0.05        # AID (~7 mm): la tapa solo baja de la regla del borde si gana al menos esto
PROFUNDIDAD_POISSON = 10
SIGMA_RELLENO = 0.08            # ancho del promedio gaussiano que pega el relleno a los datos
SIGMA_CASCO = 0.08              # ancho del alisado del casco (~12 mm); 0 = no alisar
CASCO_DESDE, CASCO_HASTA = -0.10, 0.05   # rampa del alisado, en AID respecto al centro del cráneo
PASOS_TAUBIN = 20               # relajación final tras el alisado
PASOS_HC_CARA = 10              # pasadas de HC Laplaciano contra el ruido fino (cara, cejas); 0 = no
NUCA_X, NUCA_Z = 0.15, -0.45    # el alisado también cubre x < -0.15 AID (detrás de las orejas) y z > -0.45 AID
PROFUNDIDAD_CONCHA_MIN = 0.02   # AID (~3 mm): por debajo se avisa de concha mal capturada
CIRCUNFERENCIA_Z = (0.35, 0.80) # AID: alturas donde se busca el perímetro máximo (sobre las orejas)
DISCREPANCIA_ESCALA_MAX = 0.02  # si hay dos medidas, sus factores de escala deben coincidir al 2 %
# Discrepancia máxima entre los factores de orejas y circunferencia. Sin fijar (None =
# solo se informa): falta validar con medidas reales de personas (ver LIMPIEZA.md).
DISCREPANCIA_OREJAS_MAX = None
# Rangos anatómicos plausibles (en AID) para el control de calidad
LARGO_CRANEO = (0.55, 0.95)     # semieje adelante-atrás
ANCHO_CRANEO = (0.50, 0.75)     # semieje lateral (= vertical)
TOPE_CRANEO = (0.85, 1.30)      # altura del tope sobre el eje interaural
RADIO_OREJA = 0.30              # radio (en AID) alrededor de cada canal auditivo que NO se alisa
# Túneles que deja Poisson (genus > 0): se localizan con barridos y se reparan en local
TUNEL_MAX = 0.10                # AID (~15 mm): un túnel más grande es un defecto del escaneo, no se toca
MARGEN_TUNEL = 0.01             # AID (~1.5 mm) alrededor de la caja del túnel que también se rehace
PASO_BARRIDO = 0.005            # AID: precisión con que se ubica la caja del túnel


# --- Utilidades ---------------------------------------------------------------
# PyMeshLab no puede escribir (y a veces leer) rutas con tildes en Windows ("Prueba á"),
# así que la E/S pasa por un archivo temporal con nombre ASCII.
def cargar(ms: pymeshlab.MeshSet, ruta: Path):
    ruta = Path(ruta)
    if str(ruta.resolve()).isascii():
        ms.load_new_mesh(str(ruta))
        return
    tmp = Path(tempfile.gettempdir()) / f"limpieza_{uuid.uuid4().hex}{ruta.suffix}"
    shutil.copy(ruta, tmp)
    try:
        ms.load_new_mesh(str(tmp))
    finally:
        tmp.unlink(missing_ok=True)


def guardar(ms: pymeshlab.MeshSet, ruta: Path):
    tmp = Path(tempfile.gettempdir()) / f"limpieza_{uuid.uuid4().hex}{Path(ruta).suffix}"
    ms.save_current_mesh(str(tmp), save_vertex_color=False)
    shutil.move(tmp, ruta)


def a_malla(ms: pymeshlab.MeshSet, V, F):
    ms.add_mesh(pymeshlab.Mesh(vertex_matrix=V, face_matrix=F))


def quitar_vertices(V, F, conservar):
    """Deja solo los vértices marcados (y las caras que los usan todos)."""
    F = F[conservar[F].all(axis=1)]
    nuevo = -np.ones(len(V), dtype=np.int64)
    usados = np.unique(F)
    nuevo[usados] = np.arange(len(usados))
    return V[usados], nuevo[F]


def componente_mayor(V, F):
    n = len(V)
    A = coo_matrix((np.ones(3 * len(F)),
                    (np.r_[F[:, 0], F[:, 1], F[:, 2]], np.r_[F[:, 1], F[:, 2], F[:, 0]])),
                   shape=(n, n))
    _, lab = connected_components(A, directed=False)
    cuenta = np.bincount(lab[F[:, 0]], minlength=lab.max() + 1)
    return quitar_vertices(V, F, lab == np.argmax(cuenta)), len(cuenta)


def vertices_borde(F):
    E = np.sort(np.r_[F[:, [0, 1]], F[:, [1, 2]], F[:, [2, 0]]], axis=1)
    u, c = np.unique(E, axis=0, return_counts=True)
    return np.unique(u[c == 1])


def cabeza_sobre_plano(V, F, z):
    """Vértices del trozo de la cabeza por encima del plano z: la componente conexa más grande
    de las caras que quedan enteras por encima (lo que queda suelto, p. ej. un trozo de
    espalda, no cuenta)."""
    Fa = F[(V[F, 2] > z).all(axis=1)]
    n = len(V)
    A = coo_matrix((np.ones(3 * len(Fa)),
                    (np.r_[Fa[:, 0], Fa[:, 1], Fa[:, 2]], np.r_[Fa[:, 1], Fa[:, 2], Fa[:, 0]])),
                   shape=(n, n))
    _, lab = connected_components(A, directed=False)
    mayor = np.argmax(np.bincount(lab[Fa[:, 0]]))
    cab = np.zeros(n, dtype=bool)
    cab[np.unique(Fa[lab[Fa[:, 0]] == mayor])] = True
    return cab


def plano_cuello_mas_bajo(V, F, aid, z_desde):
    """El plano más bajo (entre z_desde y CUELLO_MAS_BAJO) en que el trozo de la cabeza no
    toca el borde abierto del escaneo por debajo de las orejas, es decir, en que el cuello
    queda como un anillo completo que se puede tapar. None si ninguno lo cumple."""
    borde = vertices_borde(F)
    borde = borde[V[borde, 2] < 0]
    limpio = None
    for z in np.arange(z_desde, CUELLO_MAS_BAJO * aid, -PASO_CUELLO * aid):
        if not cabeza_sobre_plano(V, F, z)[borde].any():
            limpio = z
    return limpio


def segmentos_corte(V, F, z0):
    """Segmentos (x0, y0, x1, y1) de la intersección de la malla con el plano z = z0."""
    s = V[F, 2] - z0                                    # (caras, 3)
    cruza = (s.min(1) < 0) & (s.max(1) > 0)
    segs = []
    for Fi, si in zip(F[cruza], s[cruza]):
        pts = [V[Fi[i]] + (V[Fi[j]] - V[Fi[i]]) * si[i] / (si[i] - si[j])
               for i, j in ((0, 1), (1, 2), (2, 0)) if si[i] * si[j] < 0]
        if len(pts) == 2:
            segs.append(np.r_[pts[0][:2], pts[1][:2]])
    return np.array(segs).reshape(-1, 4)


def circunferencia(V, F, aid):
    """Perímetro horizontal máximo de la cabeza por encima de las orejas (≈ cinta métrica)."""
    mejor = (0.0, 0.0)
    for z in np.linspace(*CIRCUNFERENCIA_Z, 46) * aid:
        S = segmentos_corte(V, F, z)
        perimetro = float(np.linalg.norm(S[:, 2:] - S[:, :2], axis=1).sum())
        mejor = max(mejor, (perimetro, float(z)))
    return mejor                                         # (perímetro, altura), unidades del modelo


def tapa_plana(V, F, z0, paso):
    """Rejilla de puntos en el plano z = z0, solo DENTRO de la sección real de la malla.

    La sección no es convexa (cuello + hombros), así que se usa la regla par-impar
    contra los segmentos triángulo ∩ plano en vez del casco convexo.
    """
    S = segmentos_corte(V, F, z0)
    x0, y0, x1, y1 = S.T
    xs = np.arange(min(x0.min(), x1.min()), max(x0.max(), x1.max()), paso)
    ys = np.arange(min(y0.min(), y1.min()), max(y0.max(), y1.max()), paso)
    g = np.stack(np.meshgrid(xs, ys), -1).reshape(-1, 2)
    dentro = np.zeros(len(g), dtype=bool)
    for k in range(0, len(g), 2000):                    # rayo hacia +x, contar cruces
        px, py = g[k:k + 2000, :1], g[k:k + 2000, 1:]
        entre = (y0 > py) != (y1 > py)
        with np.errstate(divide="ignore", invalid="ignore"):
            xc = x0 + (py - y0) * (x1 - x0) / (y1 - y0)
        dentro[k:k + 2000] = (entre & (xc > px)).sum(1) % 2 == 1
    g = g[dentro]
    # no pegar puntos al contorno: evita capas dobles con las paredes del cuello
    borde = np.r_[S[:, :2], S[:, 2:]]
    g = g[cKDTree(borde).query(g)[0] > 1.5 * paso]
    return np.c_[g, np.full(len(g), z0)]


def desfase_suave(elip, datos, P, sigma):
    """Distancia datos-elipsoide interpolada en P con núcleo gaussiano (tiende a 0 lejos)."""
    d, _ = elip.distancia(datos)
    arbol = cKDTree(datos)
    out = np.zeros(len(P))
    for i, vec in enumerate(arbol.query_ball_point(P, 3 * sigma)):
        if vec:
            w = np.exp(-np.sum((datos[vec] - P[i]) ** 2, axis=1) / (2 * sigma ** 2))
            out[i] = np.sum(w * d[vec]) / (w.sum() + 1.0)   # +1: peso del "elipsoide puro"
    return out


def suavizar_casco(ms, elip, aid, sigma):
    """Alisa pelo, pozos y pliegues de la parte alta de la cabeza sin encogerla.

    La superficie se trata como un "relieve" sobre el elipsoide del cráneo: se mide la
    distancia de cada vértice al elipsoide, esa distancia se difunde sobre la malla
    (≈ promedio gaussiano de ancho sigma) y el vértice se mueve sobre la normal del
    elipsoide hasta la distancia alisada. El efecto entra gradualmente desde las cejas
    hacia arriba (y en la nuca, detrás de las orejas) y se apaga alrededor de las orejas.
    """
    m = ms.current_mesh()
    V, F = m.vertex_matrix().copy(), m.face_matrix()
    d, n = elip.distancia(V)
    cz = elip.centro[2]

    def rampa(t):
        t = np.clip(t, 0, 1)
        return t * t * (3 - 2 * t)
    w = rampa((V[:, 2] - (cz + CASCO_DESDE * aid)) / ((CASCO_HASTA - CASCO_DESDE) * aid))
    # nuca: detrás del plano de las orejas y hasta el cuello alto (pliegues/nudos del gorro)
    nuca = rampa((-V[:, 0] / aid - NUCA_X) / 0.15) * rampa((V[:, 2] / aid - NUCA_Z) / 0.15)
    w = np.maximum(w, nuca)
    for lado in (1, -1):                               # canales auditivos en (0, ±AID/2, 0)
        r = np.linalg.norm(V - [0, lado * aid / 2, 0], axis=1) / (RADIO_OREJA * aid)
        w *= rampa((r - 1) / 0.5)                      # 0 dentro del radio, 1 a 1.5 radios

    # difusión en la zona afectada (y un margen), con paseo aleatorio perezoso
    zona = V[:, 2] > min(cz + CASCO_DESDE * aid, NUCA_Z * aid) - 2 * sigma * aid
    idx = np.flatnonzero(zona)
    loc = -np.ones(len(V), dtype=np.int64)
    loc[idx] = np.arange(len(idx))
    E = np.r_[F[:, [0, 1]], F[:, [1, 2]], F[:, [2, 0]]]
    E = loc[E[zona[E].all(axis=1)]]
    A = coo_matrix((np.ones(2 * len(E)), (np.r_[E[:, 0], E[:, 1]], np.r_[E[:, 1], E[:, 0]])),
                   shape=(len(idx),) * 2).tocsr()
    A.data[:] = 1.0
    grado = np.asarray(A.sum(axis=1)).ravel()
    arista = np.median(np.linalg.norm(V[F[:, 0]] - V[F[:, 1]], axis=1))
    pasos = int(4 * (sigma * aid / arista) ** 2)      # varianza del paseo ≈ pasos·arista²/4
    ds = d[idx].copy()
    for _ in range(pasos):
        ds = 0.5 * ds + 0.5 * (A @ ds) / grado
    mover = np.zeros(len(V))
    mover[idx] = (ds - d[idx]) * w[idx]
    V += mover[:, None] * n

    ms.clear()
    ms.add_mesh(pymeshlab.Mesh(vertex_matrix=V, face_matrix=F, v_scalar_array=w))
    # relaja pliegues finos sin encoger, solo donde hubo alisado (las orejas quedan intactas)
    ms.compute_selection_by_condition_per_vertex(condselect="q > 0")
    ms.compute_selection_transfer_vertex_to_face(inclusive=False)
    ms.apply_coord_taubin_smoothing(stepsmoothnum=PASOS_TAUBIN, selected=True)
    ms.set_selection_none()
    ms.compute_normal_per_vertex()
    return {"sigma_AID": sigma, "pasos_difusion": pasos,
            "desplazamiento_max_AID": round(float(np.abs(mover).max() / aid), 4)}


def alisar_cara(ms, aid, pasos=PASOS_HC_CARA):
    """Quita el ruido fino que el alisado del casco no cubre (cejas, pestañas, reflejos de
    los ojos, barba, poros de la cara): el gradado lo toma por curvatura y lo llena de
    elementos. HC Laplaciano (encoge poco) en toda la cabeza salvo las orejas, con la
    misma protección que el casco: 0 dentro de RADIO_OREJA y entrada gradual hasta 1.5
    radios. Taubin se queda corto y el de dos pasos conserva justo el ruido (LIMPIEZA.md)."""
    m = ms.current_mesh()
    V0, F = m.vertex_matrix().copy(), m.face_matrix()

    def rampa(t):
        t = np.clip(t, 0, 1)
        return t * t * (3 - 2 * t)
    w = np.ones(len(V0))
    for lado in (1, -1):                               # canales auditivos en (0, ±AID/2, 0)
        r = np.linalg.norm(V0 - [0, lado * aid / 2, 0], axis=1) / (RADIO_OREJA * aid)
        w *= rampa((r - 1) / 0.5)

    for _ in range(pasos):
        ms.apply_coord_hc_laplacian_smoothing()
    V = V0 + w[:, None] * (ms.current_mesh().vertex_matrix() - V0)
    ms.clear()
    ms.add_mesh(pymeshlab.Mesh(vertex_matrix=V, face_matrix=F))
    ms.compute_normal_per_vertex()
    return {"pasos_hc": pasos,
            "desplazamiento_max_AID": round(float(np.linalg.norm(V - V0, axis=1).max() / aid), 4)}


def topologia(ms):
    t = ms.get_topological_measures()
    return {k: t[k] for k in ("vertices_number", "faces_number", "connected_components_number",
                              "boundary_edges", "non_two_manifold_edges",
                              "non_two_manifold_vertices", "is_mesh_two_manifold", "genus")} | {
        "caras_autointersecadas": autointersecciones(ms)}


def reparar_autointersecciones(ms, intentos=5):
    """Borra las caras que se cruzan (con un margen), cierra el agujero y alisa el parche.

    Devuelve cuántas rondas hicieron falta (0 = no había nada que reparar).
    """
    for i in range(intentos):
        ms.compute_selection_by_self_intersections_per_face()
        if ms.current_mesh().selected_face_number() == 0:
            return i
        for _ in range(2 + 2 * i):                    # cada ronda abarca un poco más
            ms.apply_selection_dilatation()
        ms.meshing_remove_selected_faces()
        ms.meshing_remove_unreferenced_vertices()
        ms.meshing_remove_connected_component_by_diameter(
            mincomponentdiag=pymeshlab.PercentageValue(10))
        ms.meshing_close_holes(maxholesize=2000, newfaceselected=True, selfintersection=False)
        ms.meshing_surface_subdivision_midpoint(iterations=2, selected=True,
                                                threshold=pymeshlab.PercentageValue(0.3))
        ms.apply_selection_dilatation()
        ms.apply_coord_laplacian_smoothing(stepsmoothnum=10, selected=True)
        ms.set_selection_none()
    ms.compute_normal_per_vertex()
    return intentos


def genus_region(F, sel):
    """Genus del trozo de malla formado por las caras `sel`.

    Con la característica de Euler de una superficie con bordes:
    χ = V − E + F = 2·piezas − 2·genus − bordes. Un túnel solo cuenta si el trozo lo
    contiene entero; si el borde del trozo lo corta, el asa queda partida y no cuenta.
    """
    F = F[sel]
    if not len(F):
        return 0
    _, Fl = np.unique(F, return_inverse=True)
    Fl = Fl.reshape(F.shape)
    nv = int(Fl.max()) + 1
    E = np.sort(np.r_[Fl[:, [0, 1]], Fl[:, [1, 2]], Fl[:, [2, 0]]], axis=1)
    clave, cuenta = np.unique(E[:, 0] * nv + E[:, 1], return_counts=True)
    chi = nv - len(clave) + len(F)
    a, b = clave // nv, clave % nv
    piezas = connected_components(coo_matrix((np.ones(len(a)), (a, b)), shape=(nv, nv)), directed=False)[0]
    ab, bb = a[cuenta == 1], b[cuenta == 1]               # aristas de borde
    bordes = 0
    if len(ab):
        n_borde = len(np.unique(np.r_[ab, bb]))
        bordes = connected_components(coo_matrix((np.ones(len(ab)), (ab, bb)), shape=(nv, nv)),
                                      directed=False)[0] - (nv - n_borde)
    return (2 * piezas - bordes - chi) // 2


def localizar_tunel(C, F, paso):
    """Caja (lo, hi) que encierra entero al menos un túnel, en las unidades de C (centros
    de cara). Barre un plano por cada lado de cada eje: el genus del trozo salta justo
    donde el plano deja de cortar el túnel. Cada barrido restringe la región del siguiente."""
    sel = np.ones(len(F), dtype=bool)
    lo, hi = C.min(0) - paso, C.max(0) + paso
    for i in (2, 0, 1):
        # borde inferior: el mayor t que deja un túnel entero en C_i > t (búsqueda binaria)
        a, b = lo[i], hi[i]
        while b - a > paso:
            t = (a + b) / 2
            a, b = (t, b) if genus_region(F, sel & (C[:, i] > t)) >= 1 else (a, t)
        lo[i] = a
        sel &= C[:, i] > a
        a, b = lo[i], hi[i]                  # borde superior: el menor t con túnel en C_i < t
        while b - a > paso:
            t = (a + b) / 2
            a, b = (a, t) if genus_region(F, sel & (C[:, i] < t)) >= 1 else (t, b)
        hi[i] = b
        sel &= C[:, i] < b
    return lo, hi


def reparar_tuneles(ms, aid, intentos_por_tunel=2):
    """Quita los túneles (asas) que deja Poisson: localiza cada uno, borra las caras de su
    caja (más un margen), cierra los agujeros y alisa solo el parche. Si un túnel es
    grande (> TUNEL_MAX) o cae cerca de una oreja (RADIO_OREJA), no se toca y la malla
    seguirá rechazada por el control de calidad. Ver LIMPIEZA.md."""
    genus = ms.get_topological_measures()["genus"]
    informe = {"encontrados": int(genus), "reparados": [], "sin_reparar": None}
    while genus > 0:
        m = ms.current_mesh()
        V, F = m.vertex_matrix().copy(), m.face_matrix().copy()
        C = V[F].mean(axis=1) / aid
        lo, hi = localizar_tunel(C, F, PASO_BARRIDO)
        caja = {"desde_AID": lo.round(3).tolist(), "hasta_AID": hi.round(3).tolist()}
        if (hi - lo).max() > TUNEL_MAX:
            informe["sin_reparar"] = caja | {"motivo": f"túnel de más de {TUNEL_MAX} AID"}
            break
        cerca = [lado for lado in (1, -1)
                 if np.linalg.norm(np.clip([0, lado / 2, 0], lo, hi) - [0, lado / 2, 0]) < RADIO_OREJA]
        if cerca:
            informe["sin_reparar"] = caja | {"motivo": "túnel en la zona de una oreja"}
            break
        for intento in range(intentos_por_tunel):
            margen = MARGEN_TUNEL * (1 + intento)          # si no alcanza, un parche más grande
            dentro = ((C > lo - margen) & (C < hi + margen)).all(axis=1)
            ms.clear()
            ms.add_mesh(pymeshlab.Mesh(vertex_matrix=V, face_matrix=F[~dentro]))
            ms.meshing_remove_unreferenced_vertices()
            ms.meshing_remove_connected_component_by_diameter(
                mincomponentdiag=pymeshlab.PercentageValue(10))
            ms.meshing_repair_non_manifold_edges(method="Remove Faces")
            ms.meshing_repair_non_manifold_vertices()
            ms.meshing_close_holes(maxholesize=2000, newfaceselected=True, selfintersection=False)
            ms.meshing_surface_subdivision_midpoint(iterations=2, selected=True,
                                                    threshold=pymeshlab.PercentageValue(0.3))
            ms.apply_selection_dilatation()
            ms.apply_coord_laplacian_smoothing(stepsmoothnum=10, selected=True)
            ms.set_selection_none()
            t = ms.get_topological_measures()
            if t["genus"] < genus and t["boundary_edges"] == 0 and t["connected_components_number"] == 1:
                informe["reparados"].append(caja | {"caras_borradas": int(dentro.sum()),
                                                    "margen_AID": margen})
                genus = t["genus"]
                break
        else:                                              # ningún intento redujo el genus
            ms.clear()
            ms.add_mesh(pymeshlab.Mesh(vertex_matrix=V, face_matrix=F))
            informe["sin_reparar"] = caja | {"motivo": "el parche no quitó el túnel"}
            break
    ms.compute_normal_per_vertex()
    return informe


def autointersecciones(ms):
    ms.compute_selection_by_self_intersections_per_face()
    n = ms.current_mesh().selected_face_number()
    ms.set_selection_none()
    return n


# --- Elipsoide del cráneo: ejes alineados, radio vertical = radio lateral -----
class Elipsoide:
    def __init__(self, P):
        def resid(q):
            cx, cy, cz, a, b = q
            return np.sqrt(((P[:, 0] - cx) / a) ** 2 + ((P[:, 1] - cy) / b) ** 2
                           + ((P[:, 2] - cz) / b) ** 2) - 1
        c0 = P.mean(0)
        q = least_squares(resid, [*c0, 0.3, 0.3], loss="soft_l1", f_scale=0.02).x
        self.centro, self.radios = q[:3], np.array([q[3], q[4], q[4]])

    def distancia(self, P):
        """Distancia aproximada con signo (+ afuera) y normal unitaria hacia afuera."""
        u = (P - self.centro) / self.radios
        f = np.sum(u ** 2, axis=1) - 1
        grad = 2 * u / self.radios
        ng = np.linalg.norm(grad, axis=1)
        return f / ng, grad / ng[:, None]

    def muestrear(self, paso):
        a, b, c = self.radios
        n_th = int(np.pi * max(a, c) / paso)
        pts = []
        for th in np.linspace(0, np.pi, n_th):
            r_eq = max(a, b) * np.sin(th)
            n_ph = max(1, int(2 * np.pi * r_eq / paso))
            ph = np.linspace(0, 2 * np.pi, n_ph, endpoint=False)
            pts.append(np.c_[a * np.sin(th) * np.cos(ph), b * np.sin(th) * np.sin(ph),
                             np.full(n_ph, c * np.cos(th))])
        P = np.vstack(pts) + self.centro
        _, N = self.distancia(P)
        return P, N


# --- Pipeline -----------------------------------------------------------------
def limpiar(ruta_malla: Path, ruta_json: Path, salida: Path, tolerancia: float = TOLERANCIAS[0],
            sigma_casco: float = SIGMA_CASCO):
    salida.mkdir(parents=True, exist_ok=True)
    datos = json.loads(ruta_json.read_text(encoding="utf-8"))
    T, aid = np.array(datos["matriz"]), float(datos["aid"])
    informe = {"entrada": str(ruta_malla), "aid": aid, "tolerancia_casquete": tolerancia}

    ms = pymeshlab.MeshSet()
    cargar(ms, ruta_malla)
    ms.meshing_remove_duplicate_vertices()      # el OBJ texturizado duplica vértices en las costuras
    ms.meshing_remove_unreferenced_vertices()
    m = ms.current_mesh()
    V = m.vertex_matrix() @ T[:3, :3].T + T[:3, 3]
    F = m.face_matrix()
    informe["original"] = {"vertices": len(V), "caras": len(F)}

    # 2. Piezas flotantes
    (V, F), n_comp = componente_mayor(V, F)
    informe["componentes_eliminadas"] = n_comp - 1

    # 3. Cresta
    z = V[:, 2] / aid
    banda = (z > BANDA_AJUSTE[0]) & (z < BANDA_AJUSTE[1]) & ~((V[:, 0] / aid > CARA_X) & (z < CARA_Z))
    elip = Elipsoide(V[banda])
    z_casquete = elip.centro[2] + INICIO_CASQUETE * elip.radios[2]

    ms.clear()
    a_malla(ms, V, F)
    ms.compute_normal_per_vertex()
    N = ms.current_mesh().vertex_normal_matrix()
    d, n_elip = elip.distancia(V)
    cos = np.sum(N * n_elip, axis=1)
    en_casquete = V[:, 2] > z_casquete
    coincide = (np.abs(d) < tolerancia * aid) & (cos > COS_NORMAL)
    # por encima del centro del cráneo: pliegues (normal hacia adentro) y salientes (ala de pelo)
    pliegue = (V[:, 2] > elip.centro[2]) & ((cos < 0) | (d > tolerancia * aid))
    cresta = (en_casquete & ~coincide) | pliegue
    for _ in range(ANILLOS_EXTRA):                 # crecer la selección para no dejar alas sueltas
        cresta[F[cresta[F].any(axis=1)]] = True
    V, F = quitar_vertices(V, F, ~cresta)
    (V, F), _ = componente_mayor(V, F)          # restos de la carpa que quedaron sueltos
    informe["elipsoide"] = {"centro": elip.centro.round(4).tolist(), "radios": elip.radios.round(4).tolist(),
                            "tope_z_en_AID": round(float((elip.centro[2] + elip.radios[2]) / aid), 3),
                            "inicio_casquete_z": round(float(z_casquete), 4)}
    informe["vertices_cresta_eliminados"] = int(cresta.sum())

    # 4. Reparación
    ms.clear()
    a_malla(ms, V, F)
    ms.meshing_remove_duplicate_faces()
    ms.meshing_remove_null_faces()
    ms.meshing_repair_non_manifold_edges(method="Remove Faces")
    ms.meshing_repair_non_manifold_vertices()
    ms.meshing_remove_connected_component_by_face_number(mincomponentsize=50)
    ms.meshing_remove_unreferenced_vertices()
    ms.compute_normal_per_vertex()
    guardar(ms, salida / "1_limpia_abierta.ply")
    informe["limpia_abierta"] = topologia(ms)

    # 5. Nube de puntos para Poisson
    m = ms.current_mesh()
    V, F, N = m.vertex_matrix(), m.face_matrix(), m.vertex_normal_matrix()
    paso = np.median(np.linalg.norm(V[F[:, 0]] - V[F[:, 1]], axis=1))

    # tapa del cuello: se recorta plano justo por encima del borde abierto y se tapa
    zb = V[vertices_borde(F), 2]
    z_cuello = zb[zb < 0].max() + MARGEN_CUELLO * aid   # z < 0: debajo de las orejas (el hueco de arriba no cuenta)
    # Si el punto más alto del borde está lejos del cuello (un trozo de espalda que el escaneo
    # cortó alto: A1, a 19 cm detrás de los canales), esa regla sube la tapa y se lleva el
    # cuello. Entonces la tapa baja al plano más bajo en que el cuello es un anillo completo, y a
    # Poisson solo entra el trozo de la cabeza. Si no hay uno claramente más abajo, se queda la
    # regla de siempre (las mallas que ya salían bien no cambian).
    z_limpio = plano_cuello_mas_bajo(V, F, aid, z_cuello)
    if z_limpio is not None and z_limpio < z_cuello - BAJADA_CUELLO_MIN * aid:
        informe["tapa_cuello"] = {"regla": "plano limpio más bajo", "z_AID": round(float(z_limpio / aid), 3),
                                  "z_por_borde_AID": round(float(z_cuello / aid), 3)}
        z_cuello = z_limpio
        arriba = cabeza_sobre_plano(V, F, z_cuello)
        tapa = tapa_plana(V, F[arriba[F].any(axis=1)], z_cuello, paso)
    else:
        informe["tapa_cuello"] = {"regla": "borde", "z_AID": round(float(z_cuello / aid), 3)}
        arriba = V[:, 2] > z_cuello
        tapa = tapa_plana(V, F, z_cuello, paso)
    Vp, Np = V[arriba], N[arriba]

    # hueco superior: puntos del elipsoide en el casquete, solo donde no hay datos reales.
    # (La banda de pliegues quitados, más abajo, NO se rellena con el elipsoide: en la nuca
    # los datos se separan de él y Poisson crearía túneles. Esa zona se alisa en el paso 6.)
    Pe, Ne = elip.muestrear(paso)
    lejos = cKDTree(Vp).query(Pe)[0] > 4 * paso
    sel = (Pe[:, 2] > z_casquete) & lejos
    Pe, Ne = Pe[sel], Ne[sel]
    # el relleno se desplaza sobre su normal según cuánto se separan del elipsoide los datos
    # cercanos (promedio gaussiano, continuo); lejos de los datos tiende al elipsoide puro.
    # Así el parche arranca donde termina la superficie real, sin escalones.
    Pe = Pe + desfase_suave(elip, Vp[Vp[:, 2] > elip.centro[2] - 0.1 * aid], Pe, SIGMA_RELLENO * aid)[:, None] * Ne
    informe["puntos_relleno"] = {"elipsoide": len(Pe), "tapa_cuello": len(tapa)}

    P = np.vstack([Vp, Pe, tapa])
    Nn = np.vstack([Np, Ne, np.tile([0, 0, -1.0], (len(tapa), 1))])
    ms.clear()
    ms.add_mesh(pymeshlab.Mesh(vertex_matrix=P, v_normals_matrix=Nn))
    ms.generate_surface_reconstruction_screened_poisson(depth=PROFUNDIDAD_POISSON, preclean=True)
    ms.meshing_remove_connected_component_by_diameter(
        mincomponentdiag=pymeshlab.PercentageValue(10))
    ms.meshing_remove_duplicate_vertices()
    ms.meshing_remove_duplicate_faces()
    ms.meshing_remove_null_faces()
    ms.meshing_repair_non_manifold_edges(method="Remove Faces")
    ms.meshing_repair_non_manifold_vertices()
    ms.meshing_remove_unreferenced_vertices()
    ms.meshing_close_holes(maxholesize=100)
    informe["reparacion_autointersecciones"] = {"poisson": reparar_autointersecciones(ms)}
    # túneles (genus > 0): solo se toca la malla si los hay, así que las que ya salían
    # con genus 0 quedan idénticas y su informe no cambia. El genus se cuenta en numpy:
    # get_topological_measures() de PyMeshLab altera su estado interno y el alisado
    # posterior salía distinto (hasta 0.2 mm) aunque no hubiera túneles.
    F_poisson = ms.current_mesh().face_matrix()
    if genus_region(F_poisson, np.ones(len(F_poisson), dtype=bool)) > 0:
        informe["tuneles"] = reparar_tuneles(ms, aid)
        if informe["tuneles"]["reparados"]:              # el parche alisado puede cruzarse
            informe["reparacion_autointersecciones"]["tuneles"] = reparar_autointersecciones(ms)

    guardar(ms, salida / "2_cerrada_poisson.ply")
    informe["cerrada_poisson"] = topologia(ms)

    # 6. Alisado del casco (pelo, pozos, pliegues) y del ruido fino de la cara,
    #    protegiendo los pabellones
    if sigma_casco:
        informe["suavizada"] = suavizar_casco(ms, elip, aid, sigma_casco)
        if PASOS_HC_CARA:
            informe["suavizada"]["cara"] = alisar_cara(ms, aid)
        informe["reparacion_autointersecciones"]["suavizada"] = reparar_autointersecciones(ms)
        guardar(ms, salida / "3_suavizada.ply")
        informe["suavizada"] |= topologia(ms)

    # 7a. Calidad de las orejas (profundidad de concha, facetado) sobre la malla final
    m = ms.current_mesh()
    informe["oreja"] = metricas_oreja(m.vertex_matrix(), m.face_matrix(), aid)

    (salida / "informe_limpieza.json").write_text(json.dumps(informe, indent=2, default=int), encoding="utf-8")
    return informe


def control_calidad(informe):
    """Compuerta final: la malla solo sigue al pipeline si pasa todos los chequeos."""
    fallas = []
    final = informe.get("suavizada") or informe["cerrada_poisson"]
    if final["connected_components_number"] != 1:
        fallas.append(f"{final['connected_components_number']} piezas (debe ser 1)")
    if final["boundary_edges"] or not final["is_mesh_two_manifold"]:
        fallas.append("malla abierta o no-manifold")
    if final["genus"] != 0:
        fallas.append(f"genus {final['genus']}: túneles; suele indicar huecos o capas dobles en el escaneo")
    if final["caras_autointersecadas"]:
        fallas.append(f"{final['caras_autointersecadas']} caras autointersecadas")
    radios = np.array(informe["elipsoide"]["radios"]) / informe["aid"]
    for nombre, r, (lo, hi) in (("largo", radios[0], LARGO_CRANEO), ("ancho", radios[1], ANCHO_CRANEO)):
        if not lo <= r <= hi:
            fallas.append(f"semieje {nombre} del cráneo {r:.2f} AID fuera de [{lo}, {hi}]: revisar landmarks")
    tope = informe["elipsoide"]["tope_z_en_AID"]
    if not TOPE_CRANEO[0] <= tope <= TOPE_CRANEO[1]:
        fallas.append(f"tope del cráneo a {tope} AID fuera de {list(TOPE_CRANEO)}: revisar landmarks")
    esc = informe.get("escala")
    if esc and esc["factor"]:
        lo, hi = config.AID_MIN_MM, config.AID_MAX_MM
        if not lo <= esc["aid_mm"] <= hi:
            fallas.append(f"AID escalado de {esc['aid_mm']:.1f} mm fuera de [{lo}, {hi}]: revisar la medida")
        if esc.get("discrepancia") is not None and esc["discrepancia"] > DISCREPANCIA_ESCALA_MAX:
            fallas.append(f"el AID y la circunferencia dan escalas que difieren un "
                          f"{100 * esc['discrepancia']:.1f} %: revisar medidas o landmarks")
        if DISCREPANCIA_OREJAS_MAX is not None:
            for fuente, dif in esc.get("discrepancias", {}).items():
                if dif > DISCREPANCIA_OREJAS_MAX:
                    fallas.append(f"la escala por {fuente} se aparta un {100 * dif:.1f} % de la "
                                  "elegida: revisar esa medida o sus puntos en la malla")
    # Avisos (no bloquean): la concha casi siempre sale poco profunda con fotogrametría de
    # celular, así que rechazar por esto dejaría fuera casi todos los escaneos.
    avisos = [f"oreja {lado}: concha de {o['profundidad_concha_AID']} AID (< {PROFUNDIDAD_CONCHA_MIN}); "
              "probablemente rellena por el escaneo, o landmark del canal mal ubicado"
              for lado, o in informe.get("oreja", {}).items()
              if o["profundidad_concha_AID"] < PROFUNDIDAD_CONCHA_MIN]
    if not (esc and esc["factor"]):
        avisos.append("sin escala real: la malla sigue en las unidades arbitrarias de KIRI "
                      "(dar el largo de las orejas y/o la circunferencia)")
    corte = informe.get("corte_cuello")
    if corte and not corte["aplicado"]:
        avisos.append(f"corte del cuello no aplicado ({corte['motivo']}); malla_final_mm.ply "
                      "queda sin cortar")
    return {"aprobado": not fallas, "fallas": fallas, "avisos": avisos}


def escalar(salida: Path, informe, aid_mm=None, circunferencia_mm=None, orejas_mm=(None, None)):
    """Factor de escala a milímetros a partir de medidas reales de la persona.

    Con el AID el factor es directo (los landmarks ya lo miden en la malla). Con la
    circunferencia se compara contra el perímetro horizontal máximo sobre las orejas.
    Con el largo de una oreja (hélix -> lóbulo, medido con regla) se compara contra la
    distancia entre esos dos puntos marcados en la malla (informe["largo_oreja_modelo"]).

    Si se da el AID, manda el AID y la circunferencia sirve de control. Si no, se usa la
    mediana de los factores de circunferencia y orejas (provisional: falta validar cuál
    es más fiable, ver LIMPIEZA.md); con tres medidas, una mala no arrastra el resultado.
    """
    final = salida / ("3_suavizada.ply" if "suavizada" in informe else "2_cerrada_poisson.ply")
    ms = pymeshlab.MeshSet()
    cargar(ms, final)
    m = ms.current_mesh()
    V, F, aid = m.vertex_matrix(), m.face_matrix(), informe["aid"]
    perimetro, z = circunferencia(V, F, aid)
    esc = {"circunferencia_modelo": round(perimetro, 5), "altura_circunferencia_AID": round(z / aid, 3),
           "factor": None}
    f_aid = aid_mm / aid if aid_mm else None
    f_circ = circunferencia_mm / perimetro if circunferencia_mm else None
    if f_aid and f_circ:
        esc["discrepancia"] = round(abs(f_aid - f_circ) / f_aid, 4)

    largos = informe.get("largo_oreja_modelo", {})
    factores = {"circunferencia": f_circ} if f_circ else {}
    for lado, mm in zip(("izq", "der"), orejas_mm):
        if mm:
            if lado not in largos:
                raise ValueError(f"se dio el largo de la oreja {lado} pero en el JSON de landmarks "
                                 "faltan sus puntos (hélix y lóbulo): marcarlos en app.py")
            factores[f"oreja_{lado}"] = mm / largos[lado]
    f_otros = float(np.median(list(factores.values()))) if factores else None

    factor = f_aid or f_otros
    if factor:
        fuente = "aid" if f_aid else ("+".join(factores) if len(factores) == 1 else
                                      "mediana(" + ", ".join(factores) + ")")
        esc |= {"factor": factor, "fuente": fuente,
                "aid_mm": round(aid * factor, 2), "circunferencia_mm": round(perimetro * factor, 1)}
        todos = ({"aid": f_aid} if f_aid else {}) | factores
        if len(todos) > 1:
            esc["factores"] = {k: round(v, 6) for k, v in todos.items()}
            # la de la circunferencia contra el AID ya está en "discrepancia" (se juzga aparte)
            dif = {k: round(abs(v - factor) / factor, 4) for k, v in factores.items()
                   if not (f_aid and k == "circunferencia")}
            if dif:
                esc["discrepancias"] = dif
        if largos:
            esc["largo_oreja_mm"] = {lado: round(d * factor, 1) for lado, d in largos.items()}
        ms.clear()
        ms.add_mesh(pymeshlab.Mesh(vertex_matrix=V * factor, face_matrix=F))
        guardar(ms, salida / "malla_final_mm.ply")
    return esc


# --- Corte del cuello (sobre la malla ya en mm) --------------------------------
def cortar_por_plano(V, F, z0):
    """Se queda con la parte de la malla por encima de z = z0, partiendo exactamente las
    caras que cruzan el plano. Cada punto de corte se crea una sola vez por arista, así
    las dos caras que la comparten usan el mismo vértice y el borde queda sin grietas."""
    s = V[:, 2] - z0
    arriba = s > 0
    n_arriba = arriba[F].sum(axis=1)
    nuevos, indice, caras = [], {}, []

    def punto(i, j):
        clave = (min(i, j), max(i, j))
        if clave not in indice:
            indice[clave] = len(V) + len(nuevos)
            p = V[i] + s[i] / (s[i] - s[j]) * (V[j] - V[i])
            p[2] = z0                                          # exacto sobre el plano
            nuevos.append(p)
        return indice[clave]

    for f in F[(n_arriba == 1) | (n_arriba == 2)]:
        a = arriba[f]
        k = int(np.flatnonzero(a if a.sum() == 1 else ~a)[0])   # el vértice solitario primero
        p, q, r = f[k], f[(k + 1) % 3], f[(k + 2) % 3]           # (conserva la orientación)
        if a.sum() == 1:                                           # p arriba; q y r abajo
            caras.append([p, punto(p, q), punto(r, p)])
        else:                                                      # p abajo; q y r arriba
            pq, rp = punto(p, q), punto(r, p)
            caras += [[pq, q, r], [pq, r, rp]]
    V2 = np.vstack([V, np.reshape(nuevos, (-1, 3))])
    F2 = np.vstack([F[n_arriba == 3], np.reshape(caras, (-1, 3)).astype(F.dtype)])
    return quitar_vertices(V2, F2, np.ones(len(V2), dtype=bool))


def lazos_de_borde(F):
    """Lazos del borde como listas ordenadas de vértices (siguiendo las medias aristas).
    None si el borde no son lazos simples (algún vértice con más o menos de una arista
    de borde entrando y saliendo)."""
    H = np.r_[F[:, [0, 1]], F[:, [1, 2]], F[:, [2, 0]]]
    todas = set(map(tuple, H.tolist()))
    borde = [(a, b) for a, b in H.tolist() if (b, a) not in todas]
    siguiente = dict(borde)
    if len(siguiente) != len(borde) or set(siguiente.values()) != set(siguiente):
        return None
    lazos, vistos = [], set()
    for inicio in siguiente:
        lazo, v = [], inicio
        while v not in vistos:
            vistos.add(v)
            lazo.append(v)
            v = siguiente[v]
        if lazo:
            lazos.append(lazo)
    return lazos


def dentro_poligono(Q, P):
    """Regla par-impar: qué puntos Q (n, 2) caen dentro del polígono P (m, 2)."""
    x0, y0 = P[:, 0], P[:, 1]
    x1, y1 = np.roll(x0, -1), np.roll(y0, -1)
    dentro = np.zeros(len(Q), dtype=bool)
    for k in range(0, len(Q), 2000):
        px, py = Q[k:k + 2000, :1], Q[k:k + 2000, 1:]
        entre = (y0 > py) != (y1 > py)
        with np.errstate(divide="ignore", invalid="ignore"):
            xc = x0 + (py - y0) * (x1 - x0) / (y1 - y0)
        dentro[k:k + 2000] = (entre & (xc > px)).sum(1) % 2 == 1
    return dentro


def tapar_lazo(V, lazo, paso):
    """Tapa plana y bien formada para un lazo de borde plano: rejilla interior (sin
    pegarse al borde) + Delaunay, quedándose con los triángulos de dentro, mirando hacia
    abajo (hacia fuera de la cabeza). Devuelve (puntos nuevos, triángulos) con índices
    sobre [V, puntos nuevos]."""
    P = V[lazo, :2]
    lo, hi = P.min(0), P.max(0)
    g = np.stack(np.meshgrid(np.arange(lo[0] + paso / 2, hi[0], paso),
                             np.arange(lo[1] + paso / 2, hi[1], paso)), -1).reshape(-1, 2)
    g = g[dentro_poligono(g, P)]
    g = g[cKDTree(P).query(g)[0] > 0.75 * paso]
    todos = np.vstack([P, g])
    T = Delaunay(todos).simplices
    T = T[dentro_poligono(todos[T].mean(axis=1), P)]
    n = ((todos[T[:, 1], 0] - todos[T[:, 0], 0]) * (todos[T[:, 2], 1] - todos[T[:, 0], 1])
         - (todos[T[:, 1], 1] - todos[T[:, 0], 1]) * (todos[T[:, 2], 0] - todos[T[:, 0], 0]))
    T[n > 0] = T[n > 0][:, ::-1]                                  # normal hacia -z
    mapa = np.r_[np.asarray(lazo), len(V) + np.arange(len(g))]
    z0 = V[lazo[0], 2]
    return np.c_[g, np.full(len(g), z0)], mapa[T]


def comprobar_cerrada(V, F):
    """Problemas de una malla que debe ser cerrada, orientable y de genus 0 (lista vacía = bien)."""
    problemas = []
    H = np.r_[F[:, [0, 1]], F[:, [1, 2]], F[:, [2, 0]]].astype(np.int64)
    n = len(V)
    clave = H[:, 0] * n + H[:, 1]
    if len(np.unique(clave)) != len(clave):
        problemas.append("medias aristas repetidas (orientación incoherente o no-manifold)")
    if not np.isin(H[:, 1] * n + H[:, 0], clave).all():
        problemas.append("aristas de borde (malla abierta)")
    g = genus_region(F, np.ones(len(F), dtype=bool))
    if g != 0:
        problemas.append(f"genus {g}")
    volumen = np.einsum("ij,ij->i", V[F[:, 0]], np.cross(V[F[:, 1]], V[F[:, 2]])).sum() / 6
    if volumen <= 0:
        problemas.append("normales hacia dentro")
    return problemas


def cortar_cuello(ruta: Path, z_mm: float):
    """Corta la malla en mm con el plano z = z_mm (respecto del eje interaural) y la tapa.
    Solo se sobrescribe el archivo si el resultado queda cerrado y sano; si no, se deja
    como estaba y el motivo queda en el informe (y como aviso en el control de calidad)."""
    ms = pymeshlab.MeshSet()
    cargar(ms, ruta)
    V, F = ms.current_mesh().vertex_matrix(), ms.current_mesh().face_matrix()
    info = {"z_mm": z_mm, "aplicado": False}
    if V[:, 2].min() >= z_mm:
        return info | {"motivo": f"la malla ya termina por encima de z = {z_mm} mm"}
    arista = float(np.median(np.linalg.norm(V[F[:, 0]] - V[F[:, 1]], axis=1)))
    z = z_mm
    while np.any(V[:, 2] == z):                  # ningún vértice justo sobre el plano
        z = np.nextafter(z, np.inf)
    V2, F2 = cortar_por_plano(V, F, z)
    # si el plano pasa casi rozando un vértice, el corte deja puntos casi coincidentes en
    # el borde (Delaunay los perdería): se fusionan y se quitan las caras degeneradas.
    # Solo los puntos del plano: fusionar en toda la malla abre agujeros donde el escaneo
    # trae vértices muy juntos (pasó en la punta de la nariz)
    en_plano = np.flatnonzero(V2[:, 2] == z)
    rep = np.arange(len(V2))

    def raiz(i):
        while rep[i] != i:
            i = rep[i]
        return i

    for i, j in cKDTree(V2[en_plano]).query_pairs(0.02 * arista):
        a, b = raiz(en_plano[i]), raiz(en_plano[j])
        rep[max(a, b)] = min(a, b)
    rep = np.array([raiz(i) for i in range(len(V2))])
    F2 = rep[F2]
    F2 = F2[(F2[:, 0] != F2[:, 1]) & (F2[:, 1] != F2[:, 2]) & (F2[:, 2] != F2[:, 0])]
    F2 = F2[np.sort(np.unique(np.sort(F2, axis=1), axis=0, return_index=True)[1])]
    V2, F2 = quitar_vertices(V2, F2, np.ones(len(V2), dtype=bool))
    # el plano puede dejar sueltos trozos de hombro que suben por encima del corte; la
    # herramienta de gradado se cae con piezas extra, así que solo queda la cabeza
    (V2, F2), piezas = componente_mayor(V2, F2)
    lazos = lazos_de_borde(F2)
    if lazos is None:
        return info | {"motivo": "el borde del corte no quedó como lazos simples"}
    nuevos, tapa = [], []
    for lazo in lazos:
        P, T = tapar_lazo(V2, lazo, 3 * arista)
        tapa.append(T + np.where(T >= len(V2), sum(len(p) for p in nuevos), 0))
        nuevos.append(P)
    V3 = np.vstack([V2, *nuevos])
    tapa = np.vstack(tapa)
    F3 = np.vstack([F2, tapa])
    # comprobaciones: cerrada y sana, y la tapa cubre exactamente la sección (sin solapes)
    problemas = comprobar_cerrada(V3, F3)
    d = V3[tapa]
    area_tapa = 0.5 * np.abs((d[:, 1, 0] - d[:, 0, 0]) * (d[:, 2, 1] - d[:, 0, 1])
                             - (d[:, 1, 1] - d[:, 0, 1]) * (d[:, 2, 0] - d[:, 0, 0])).sum()
    area_seccion = sum(0.5 * abs(np.sum(V2[l, 0] * np.roll(V2[l, 1], -1) - np.roll(V2[l, 0], -1) * V2[l, 1]))
                       for l in map(np.asarray, lazos))
    if abs(area_tapa - area_seccion) > 1e-6 * area_seccion:
        problemas.append(f"la tapa ({area_tapa:.1f} mm²) no coincide con la sección ({area_seccion:.1f} mm²)")
    if len(componente_mayor(V3, F3)[0][1]) != len(F3):
        problemas.append("más de una pieza")
    info |= {"z_mm": round(z, 4), "lazos": len(lazos), "piezas_sueltas_quitadas": piezas - 1,
             "caras_antes": len(F), "caras_despues": len(F3),
             "area_seccion_mm2": round(float(area_seccion), 1)}
    if problemas:
        return info | {"motivo": "; ".join(problemas)}
    ms.clear()
    ms.add_mesh(pymeshlab.Mesh(vertex_matrix=V3, face_matrix=F3))
    guardar(ms, ruta)
    return info | {"aplicado": True}


def limpiar_auto(ruta_malla: Path, ruta_json: Path, salida: Path, sigma_casco: float = SIGMA_CASCO,
                 aid_mm: float | None = None, circunferencia_mm: float | None = None,
                 orejas_mm: tuple[float | None, float | None] = (None, None)):
    """Repite la limpieza con tolerancias cada vez más estrictas hasta obtener genus 0,
    escala a mm si hay medidas, y aplica el control de calidad (queda en informe_limpieza.json).

    orejas_mm: largo (hélix -> lóbulo) de la oreja izquierda y derecha medido en la persona.
    """
    for tol in TOLERANCIAS:
        informe = limpiar(ruta_malla, ruta_json, salida, tol, sigma_casco)
        t = informe["cerrada_poisson"]
        print(f"tolerancia {tol}: genus {t['genus']}, bordes {t['boundary_edges']}")
        if t["genus"] == 0 and t["boundary_edges"] == 0 and t["is_mesh_two_manifold"]:
            break
    # largo de las orejas en la malla (solo si el JSON trae hélix y lóbulo; los JSON de
    # 3 puntos no los tienen y el informe queda como antes)
    largos = largos_oreja(json.loads(ruta_json.read_text(encoding="utf-8"))["puntos"])
    if largos:
        informe["largo_oreja_modelo"] = {lado: round(d, 6) for lado, d in largos.items()}
    informe["escala"] = escalar(salida, informe, aid_mm, circunferencia_mm, orejas_mm)
    # el corte del cuello va en mm (config.CORTE_CUELLO_MM), así que solo hay corte si hay escala
    if informe["escala"]["factor"]:
        informe["corte_cuello"] = cortar_cuello(salida / "malla_final_mm.ply", config.CORTE_CUELLO_MM)
    informe["control_calidad"] = control_calidad(informe)
    (salida / "informe_limpieza.json").write_text(json.dumps(informe, indent=2, default=int), encoding="utf-8")
    return informe
