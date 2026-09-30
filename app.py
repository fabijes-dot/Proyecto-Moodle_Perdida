"""
app.py — Dashboard: Alerta temprana de pérdida de materias (EVA Moodle)
==================================================================
Ejecutar desde la carpeta del proyecto:   streamlit run app.py

Lee los datos YA ANONIMIZADOS de data/procesados/ (se generan con: python -m src.preparar_datos).
Los datos son SINTÉTICOS: simulan una exportación de calificaciones de EVA Moodle.
"""
import os
import pandas as pd
import plotly.express as px
import streamlit as st

st.set_page_config(page_title="Alerta temprana EVA Moodle", page_icon="🎓", layout="wide")

CARPETA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "procesados")
MIN_GRUPO = 5                  # privacidad: no se muestran grupos con menos de 5 registros
NOTA_MINIMA = 70
COLOR = {"Aprobado": "#2E86AB", "Reprobado": "#E4572E"}
ROJO = "#E4572E"


# --------------------------------------------------------------------------- #
# 1. Carga de datos (se guarda en caché para que el dashboard sea rápido)
# --------------------------------------------------------------------------- #
@st.cache_data
def cargar():
    cursos = pd.read_csv(os.path.join(CARPETA, "cursos_anon.csv"))
    act = pd.read_csv(os.path.join(CARPETA, "calificaciones_anon.csv"),
                      usecols=["id_estudiante", "course_id", "evaluacion", "componente", "semana",
                               "nota_obtenida", "porcentaje", "atrasado"])
    act = act[act["componente"].notna()].copy()          # solo actividades PRF / PAE / AA
    # "ASISTIDO POR EL PROFESOR: PRF ││ 10 PTOS ││ Tarea 1 ││ FECHA..." → "Tarea 1 (PRF, sem. 5)"
    act["actividad"] = (act["evaluacion"].str.split("││").str[2].str.strip() + " ("
                        + act["componente"] + ", sem. " + act["semana"].astype(int).astype(str) + ")")
    act["entregada"] = act["nota_obtenida"].notna()
    act["nota_0"] = act["porcentaje"].fillna(0)         # no entregada = 0
    act = act.merge(cursos[["id_estudiante", "course_id", "estado"]], on=["id_estudiante", "course_id"])
    cursos["rango_acceso"] = pd.cut(cursos["dias_primer_acceso"], [-1, 3, 7, 14, 200],
                                    labels=["0-3 días", "4-7 días", "8-14 días", "Más de 14 días"])
    return cursos, act


@st.cache_data
def indicadores_inicio(act, semana_corte):
    """Entregas y promedio de cada estudiante-curso hasta la semana elegida."""
    ini = act[act["semana"] <= semana_corte]
    return (ini.groupby(["id_estudiante", "course_id"])
               .agg(entregas_corte=("entregada", "mean"), promedio_corte=("nota_0", "mean"))
               .mul([100, 1]).reset_index())


def tasa_por(data, col):
    """% de reprobación por grupo, ocultando grupos pequeños."""
    t = data.groupby(col, observed=True)["reprobo"].agg(reprobacion="mean", n="size").reset_index()
    t["reprobacion"] = (t["reprobacion"] * 100).round(1)
    return t[t["n"] >= MIN_GRUPO]


def barras(t, col, titulo, horizontal=False):
    t = t.sort_values("reprobacion") if horizontal else t
    fig = px.bar(t, x="reprobacion" if horizontal else col, y=col if horizontal else "reprobacion",
                 orientation="h" if horizontal else "v", text="reprobacion", hover_data=["n"], title=titulo)
    fig.update_traces(marker_color=ROJO, texttemplate="%{text:.1f}%", textposition="outside", cliponaxis=False)
    tope = [0, max(t["reprobacion"].max() * 1.2, 5)]
    if horizontal:
        fig.update_xaxes(range=tope)
    else:
        fig.update_yaxes(range=tope)
    fig.update_layout(xaxis_title="% reprobación" if horizontal else "",
                      yaxis_title="" if horizontal else "% reprobación", margin=dict(t=50, b=10))
    return fig


cursos, act = cargar()

# --------------------------------------------------------------------------- #
# 2. Filtros
# --------------------------------------------------------------------------- #
st.sidebar.header("Filtros")
f_carrera = st.sidebar.multiselect("Carrera", sorted(cursos["carrera"].unique()), placeholder="Todas")
f_nivel = st.sidebar.multiselect("Ciclo", sorted(cursos["nivel"].unique()), placeholder="Todos")
st.sidebar.divider()
st.sidebar.caption(f"**Alcance:** ciclos 1 a 5 (primeros ciclos de la carrera).\n\n"
                   f"Ciclo: 15/03/2026 – 07/08/2026 · Aprueba con {NOTA_MINIMA} %.\n\n"
                   f"Por privacidad no se muestran grupos con menos de {MIN_GRUPO} registros "
                   "y los estudiantes aparecen solo con un código (hash).")
st.sidebar.info("⚠️ Datos **sintéticos** con la estructura de EVA Moodle. No corresponden a estudiantes reales.")

c = cursos.copy()
if f_carrera:
    c = c[c["carrera"].isin(f_carrera)]
if f_nivel:
    c = c[c["nivel"].isin(f_nivel)]
a = act.merge(c[["id_estudiante", "course_id"]], on=["id_estudiante", "course_id"])

if len(c) < MIN_GRUPO:
    st.warning("Con estos filtros hay muy pocos datos. Amplía la selección.")
    st.stop()

# --------------------------------------------------------------------------- #
# 3. Encabezado e indicadores
# --------------------------------------------------------------------------- #
st.title("🎓 Alerta temprana de pérdida de materias")
st.markdown("**Pregunta:** ¿qué factores se relacionan con que un estudiante repruebe, "
            "y se puede identificar el riesgo **en las primeras semanas** del ciclo?")

k = st.columns(5)
k[0].metric("Estudiantes", f"{c['id_estudiante'].nunique():,}")
k[1].metric("Matrículas (estudiante-curso)", f"{len(c):,}")
k[2].metric("% reprobación", f"{c['reprobo'].mean() * 100:.1f}%")
k[3].metric("Mediana nota final", f"{c['nota_final'].median():.1f}%")
k[4].metric("Actividades entregadas", f"{a['entregada'].mean() * 100:.1f}%")

tab1, tab2, tab3, tab4, tab5 = st.tabs(["📍 ¿Dónde se pierde?", "⏱️ Inicio del ciclo",
                                        "🚨 Alerta temprana", "💡 Hallazgos", "🔒 Datos y privacidad"])

# --------------------------------------------------------------------------- #
# 4. ¿Dónde se pierde más? (segmentación)
# --------------------------------------------------------------------------- #
with tab1:
    c1, c2 = st.columns(2)
    c1.plotly_chart(barras(tasa_por(c, "carrera"), "carrera", "Reprobación por carrera", True), width="stretch")
    top = tasa_por(c, "materia").sort_values("reprobacion", ascending=False).head(8)
    c2.plotly_chart(barras(top, "materia", "Materias con más reprobación", True), width="stretch")

    c3, c4 = st.columns(2)
    t = tasa_por(c, "nivel"); t["nivel"] = t["nivel"].astype(str)
    fig = barras(t, "nivel", "Reprobación por ciclo de la carrera")
    fig.update_layout(xaxis_title="Ciclo (1 = primer ciclo)")
    c3.plotly_chart(fig, width="stretch")
    perdidas = c.groupby("id_estudiante")["reprobo"].sum().value_counts().sort_index()
    fig = px.bar(x=[f"{int(i)} de 4" for i in perdidas.index], y=perdidas.values, text=perdidas.values,
                 title="Número de estudiantes según cuántas de sus 4 materias perdieron")
    fig.update_traces(marker_color="#6C757D")
    fig.update_layout(xaxis_title="Materias perdidas por el estudiante", yaxis_title="Número de estudiantes")
    c4.plotly_chart(fig, width="stretch")

# --------------------------------------------------------------------------- #
# 5. Inicio del ciclo: primer acceso y evolución semanal
# --------------------------------------------------------------------------- #
with tab2:
    c1, c2 = st.columns(2)
    c1.plotly_chart(barras(tasa_por(c, "rango_acceso"), "rango_acceso",
                           "Reprobación según los días hasta el primer acceso"), width="stretch")
    fig = px.box(c, x="estado", y="dias_primer_acceso", color="estado", color_discrete_map=COLOR,
                 points=False, title="Días hasta el primer acceso: aprobados vs reprobados")
    fig.update_layout(showlegend=False, xaxis_title="", yaxis_title="Días desde el 15/03")
    c2.plotly_chart(fig, width="stretch")

    semanal = (a.groupby(["semana", "estado"])["entregada"].mean() * 100).reset_index()
    fig = px.line(semanal, x="semana", y="entregada", color="estado", markers=True,
                  color_discrete_map=COLOR, title="% de actividades entregadas por semana del ciclo")
    fig.add_vline(x=6, line_dash="dash", line_color="gray", annotation_text="Semana 6")
    fig.update_layout(yaxis_title="% entregadas", xaxis_title="Semana del ciclo")
    st.plotly_chart(fig, width="stretch")

    piv = pd.pivot_table(c, values="reprobo", index="carrera", columns="rango_acceso",
                         aggfunc="mean", observed=True) * 100
    fig = px.imshow(piv.round(0), text_auto=True, color_continuous_scale="Reds", aspect="auto",
                    title="% de reprobación por carrera y días hasta el primer acceso")
    fig.update_layout(xaxis_title="", yaxis_title="", coloraxis_showscale=False)
    st.plotly_chart(fig, width="stretch")

# --------------------------------------------------------------------------- #
# 6. Alerta temprana: semáforo en la semana 6
# --------------------------------------------------------------------------- #
SEMAFORO = {"🔴 Riesgo alto": "#E4572E", "🟡 Atención": "#F2C14E", "🟢 Sin riesgo": "#4CAF50"}

with tab3:
    st.markdown("### 🚦 Semáforo de riesgo en la **semana 6** del ciclo")
    st.markdown(
        "Imagina que hoy es la **semana 6** (fines de abril). Todavía no hay notas finales, pero ya sabemos "
        "3 cosas de cada estudiante en cada materia. Cada una que se cumple es una **señal de riesgo** 🚩:\n"
        "1. 🚩 **Entró tarde** al aula virtual (más de 7 días después de iniciar el ciclo).\n"
        "2. 🚩 **No presentó** 1 o más actividades hasta la semana 6.\n"
        "3. 🚩 Su **promedio** en las actividades hasta la semana 6 es **menor a 70 %**.\n\n"
        "**🟢 0 señales = sin riesgo · 🟡 1 señal = atención · 🔴 2 o 3 señales = riesgo alto**")

    with st.expander("⚙️ Ajustar la regla (opcional)"):
        x1, x2, x3 = st.columns(3)
        semana_corte = x1.slider("Semana de corte", 3, 12, 6)
        u_acceso = x2.slider("Entró tarde: más de (días)", 1, 30, 7)
        u_prom = x3.slider("Promedio bajo: menor a (%)", 0, 100, 70, 5)

    # actividades que vencían hasta la semana de corte
    hasta = a[a["semana"] <= semana_corte]
    r = c.merge(indicadores_inicio(act, semana_corte), on=["id_estudiante", "course_id"], how="left")
    no_pres = (hasta[~hasta["entregada"]].groupby(["id_estudiante", "course_id"])["actividad"]
               .agg(lambda x: ", ".join(x)).rename("actividades_no_presentadas"))
    n_no = hasta[~hasta["entregada"]].groupby(["id_estudiante", "course_id"]).size().rename("no_presentadas")
    r = r.merge(no_pres, on=["id_estudiante", "course_id"], how="left").merge(n_no, on=["id_estudiante", "course_id"], how="left")
    r["no_presentadas"] = r["no_presentadas"].fillna(0).astype(int)
    r["actividades_no_presentadas"] = r["actividades_no_presentadas"].fillna("—")
    r["senales"] = ((r["dias_primer_acceso"] > u_acceso).astype(int)
                    + (r["no_presentadas"] >= 1).astype(int)
                    + (r["promedio_corte"] < u_prom).astype(int))
    r["semaforo"] = pd.cut(r["senales"], [-1, 0, 1, 3], labels=["🟢 Sin riesgo", "🟡 Atención", "🔴 Riesgo alto"])

    # --- 6.1 cuántos en cada color ---
    m = st.columns(3)
    for col, color in zip(m, ["🔴 Riesgo alto", "🟡 Atención", "🟢 Sin riesgo"]):
        n = int((r["semaforo"] == color).sum())
        col.metric(color, f"{n:,} matrículas")
        col.caption(f"{n / len(r) * 100:.0f} % del total")

    # --- 6.2 por carrera ---
    por_car = r.groupby(["carrera", "semaforo"], observed=True).size().reset_index(name="matriculas")
    fig = px.bar(por_car, y="carrera", x="matriculas", color="semaforo", orientation="h",
                 color_discrete_map=SEMAFORO, category_orders={"semaforo": list(SEMAFORO)},
                 title=f"Posibles estudiantes en riesgo por carrera (semana {semana_corte})")
    fig.update_layout(xaxis_title="Número de matrículas (estudiante-materia)", yaxis_title="", legend_title="")
    st.plotly_chart(fig, width="stretch")

    # --- 6.3 actividades que más dejan de presentar ---
    faltas = (hasta[~hasta["entregada"]]["actividad"].value_counts().head(8)
              .rename_axis("actividad").reset_index(name="estudiantes"))
    fig = px.bar(faltas.sort_values("estudiantes"), x="estudiantes", y="actividad", orientation="h",
                 text="estudiantes", title=f"Actividades que más estudiantes NO presentaron (hasta la semana {semana_corte})")
    fig.update_traces(marker_color="#6C757D")
    fig.update_layout(xaxis_title="Estudiantes que no la presentaron", yaxis_title="")
    st.plotly_chart(fig, width="stretch")

    # --- 6.4 lista de estudiantes en riesgo alto ---
    st.markdown(f"#### 🔴 Lista de estudiantes en **riesgo alto** en la semana {semana_corte}")
    st.caption("Cada fila es un estudiante en una materia. Se muestran solo con su código anónimo: en la vida real, "
               "el tutor usaría esta lista para contactarlos.")
    car_sel = st.selectbox("Ver carrera", ["Todas"] + sorted(r["carrera"].unique()))
    lista = r[r["semaforo"] == "🔴 Riesgo alto"]
    if car_sel != "Todas":
        lista = lista[lista["carrera"] == car_sel]
    lista = (lista[["id_estudiante", "carrera", "materia", "nivel", "paralelo", "dias_primer_acceso",
                    "no_presentadas", "actividades_no_presentadas", "promedio_corte", "senales"]]
             .sort_values(["senales", "no_presentadas"], ascending=False)
             .rename(columns={"id_estudiante": "Código", "carrera": "Carrera", "materia": "Materia",
                              "nivel": "Ciclo", "paralelo": "Paralelo", "dias_primer_acceso": "Días hasta 1.er acceso",
                              "no_presentadas": "N.º no presentadas",
                              "actividades_no_presentadas": "Actividades no presentadas",
                              "promedio_corte": "Promedio (%)", "senales": "Señales 🚩"}).round(1))
    st.write(f"**{len(lista):,}** matrículas en riesgo alto.")
    st.dataframe(lista, width="stretch", height=380, hide_index=True)

    # --- 6.5 comprobación con el ciclo anterior ---
    with st.expander("✅ ¿La alerta habría funcionado? (comprobación con el resultado real del ciclo anterior)"):
        res = (r.groupby("semaforo", observed=True)["reprobo"].agg(["mean", "size"]).reindex(list(SEMAFORO)))
        st.markdown(
            f"Como los datos son del ciclo anterior, sabemos quién reprobó al final:\n"
            f"- De los **🔴 riesgo alto**, reprobó el **{res.loc['🔴 Riesgo alto', 'mean'] * 100:.0f} %**.\n"
            f"- De los **🟡 atención**, reprobó el **{res.loc['🟡 Atención', 'mean'] * 100:.0f} %**.\n"
            f"- De los **🟢 sin riesgo**, reprobó solo el **{res.loc['🟢 Sin riesgo', 'mean'] * 100:.0f} %**.\n\n"
            f"Es decir, el semáforo de la semana {semana_corte} **sí separa** a quienes iban a reprobar.")
        fig = px.bar(x=res.index, y=(res["mean"] * 100).round(1), color=res.index, color_discrete_map=SEMAFORO,
                     text=(res["mean"] * 100).round(0), title="% que terminó reprobando, según el color del semáforo")
        fig.update_traces(texttemplate="%{text:.0f}%", textposition="outside", cliponaxis=False)
        fig.update_layout(showlegend=False, xaxis_title="", yaxis_title="% reprobó al final", yaxis_range=[0, 110])
        st.plotly_chart(fig, width="stretch")

# --------------------------------------------------------------------------- #
# 7. Hallazgos (se escriben solos con los datos filtrados)
# --------------------------------------------------------------------------- #
with tab4:
    ta = tasa_por(c, "rango_acceso").set_index("rango_acceso")["reprobacion"]
    c["rango_inicio"] = pd.cut(c["promedio_inicio"], [-1, 50, 70, 85, 100], labels=["<50", "50-70", "70-85", "85-100"])
    ti = tasa_por(c, "rango_inicio").set_index("rango_inicio")["reprobacion"]
    tc = tasa_por(c, "carrera").sort_values("reprobacion")
    tm = tasa_por(c, "materia").sort_values("reprobacion")

    st.subheader("Hallazgos principales")
    if {"0-3 días", "Más de 14 días"} <= set(ta.index):
        st.markdown(f"1. **Entrar tarde al aula virtual es una señal de alerta.** Quien entra en los primeros "
                    f"3 días reprueba el **{ta['0-3 días']:.0f} %**; quien tarda más de 2 semanas, el "
                    f"**{ta['Más de 14 días']:.0f} %**.")
    if {"<50", "85-100"} <= set(ti.index):
        st.markdown(f"2. **Las primeras 6 semanas anticipan el resultado.** Con un promedio menor a 50 % en las "
                    f"primeras actividades reprueba el **{ti['<50']:.0f} %**; con más de 85 %, solo el "
                    f"**{ti['85-100']:.0f} %**.")
    if len(tc) > 1:
        st.markdown(f"3. **La pérdida se concentra en ciertos grupos.** La carrera con más reprobación es "
                    f"**{tc.iloc[-1]['carrera']}** ({tc.iloc[-1]['reprobacion']:.0f} %) y la materia más difícil, "
                    f"**{tm.iloc[-1]['materia']}** ({tm.iloc[-1]['reprobacion']:.0f} %).")
    st.markdown("**Recomendación:** usar el primer acceso y las entregas de las primeras 6 semanas como "
                "**alerta temprana**, para que tutores y docentes contacten a tiempo a los estudiantes en riesgo.")
    st.caption("⚠️ Limitación: los datos son sintéticos y sus relaciones fueron definidas al simularlos. "
               "El dashboard demuestra el método; la magnitud real de cada efecto se conocerá con datos reales de EVA Moodle.")

# --------------------------------------------------------------------------- #
# 8. Datos y privacidad
# --------------------------------------------------------------------------- #
with tab5:
    st.markdown("""
**Fuente:** simulación de la exportación de calificaciones de EVA Moodle: una fila por estudiante,
curso y actividad, con los componentes PRF, PAE y AA.

**Protección de datos (LOPDP):**
- Se eliminaron nombre, apellido y correo; el id del estudiante se reemplazó por un **hash SHA-256 con sal secreta**.
- Se verificó **k-anonimato ≥ 5** con carrera, ciclo y paralelo (se suprimieron los estudiantes de grupos pequeños).
- El dashboard no muestra grupos con menos de 5 registros.

**Limpieza:** se eliminaron filas duplicadas. Las actividades sin nota se tratan como **no entregadas**.
Los atípicos (notas muy bajas, accesos muy tardíos) se conservaron porque representan al grupo en riesgo.
""")
    st.markdown("**Diccionario de variables** (una fila = un estudiante en una materia)")
    diccionario = pd.DataFrame([
        ["Días hasta el 1.er acceso", "Días entre el inicio del ciclo (15/03) y la primera vez que el estudiante entró al curso", "first_course_access"],
        ["% entregadas (todo el ciclo)", "De las 13 actividades del curso, qué % presentó el estudiante", "nota_obtenida (vacía = no entregó)"],
        ["% entregadas (inicio)", "De las 4 actividades que vencían hasta la semana 6, qué % presentó", "nota_obtenida + fecha de entrega"],
        ["Promedio al inicio (%)", "Promedio de esas 4 actividades de las primeras 6 semanas (no entregada = 0)", "porcentaje de cada actividad"],
        ["Entregas atrasadas", "Cuántas actividades entregó fuera de plazo (marcadas '(atrasado)')", "nombre de la actividad"],
        ["Nota final (%)", "Porcentaje de la NOTA FINAL DEL CURSO. Aprueba con 70 %", "porcentaje (tipo 'course')"],
    ], columns=["Variable", "Qué mide", "De dónde sale en EVA Moodle"])
    st.dataframe(diccionario, width="stretch", hide_index=True)

    st.markdown("**Resumen estadístico de esas variables**")
    nombres = {"dias_primer_acceso": "Días hasta el 1.er acceso", "entregadas_pct": "% entregadas (todo el ciclo)",
               "entregadas_inicio_pct": "% entregadas (inicio)", "promedio_inicio": "Promedio al inicio (%)",
               "atrasadas": "Entregas atrasadas", "nota_final": "Nota final (%)"}
    resumen = (c[list(nombres)].rename(columns=nombres).describe().T
               [["mean", "50%", "min", "max"]].rename(columns={"mean": "Media", "50%": "Mediana",
                                                              "min": "Mínimo", "max": "Máximo"}).round(1))
    st.dataframe(resumen, width="stretch")
