"""
Anonimización (LOPDP), limpieza y variables del proyecto
======================================================================
La exportación de Moodle viene una fila por actividad calificada
Orden de uso:
  crudo → anonimizar() → extraer_curso() → extraer_actividad() → limpiar()
        → resumir_por_curso()   (una fila por estudiante y curso, lista para el EDA)
"""
import hashlib
import numpy as np
import pandas as pd
from scipy import stats

from src.generar_datos import NOTA_MINIMA, INICIO, FIN, CARRERAS

# catálogo de carreras -> base real sale de mdl_course_categories
CATALOGO = {cod: nombre for nombre, (cod, *_ ) in CARRERAS.items()}

PERSONALES = ["student_id", "username", "firstname", "lastname", "email"]
SEMANA_CORTE = 6          # "inicio de ciclo": primeras 6 semanas


# --------------------------------------------------------------------------- #
# 1. Anonimización 
# --------------------------------------------------------------------------- #
def seudonimo(valor, sal: str) -> str:
    """Hash SHA-256 con sal secreta; se conservan 12 caracteres."""
    return hashlib.sha256((sal + str(valor)).encode()).hexdigest()[:12]


def anonimizar(df: pd.DataFrame, sal: str) -> pd.DataFrame:
    """Reemplaza el id de Moodle por un seudónimo y borra nombre, apellido y correos."""
    df = df.copy()
    df["id_estudiante"] = df["student_id"].apply(seudonimo, sal=sal)
    return df.drop(columns=PERSONALES)


def k_anonimato(df: pd.DataFrame, cuasi: list) -> tuple:
    """Tamaño del grupo más pequeño y número de grupos con menos de 5 estudiantes."""
    tamanos = df.drop_duplicates("id_estudiante").groupby(cuasi, observed=True).size()
    return int(tamanos.min()), int((tamanos < 5).sum())


def suprimir_grupos_pequenos(df: pd.DataFrame, cuasi: list, k: int = 5):
    """Elimina a los estudiantes que están en grupos con menos de k personas."""
    personas = df.drop_duplicates("id_estudiante")
    tam = personas.groupby(cuasi, observed=True)["id_estudiante"].transform("size")
    riesgo = set(personas.loc[tam < k, "id_estudiante"])
    return df[~df["id_estudiante"].isin(riesgo)].copy(), len(riesgo)


# --------------------------------------------------------------------------- #
# 2. Extraer información de los textos
# --------------------------------------------------------------------------- #
def extraer_curso(df: pd.DataFrame) -> pd.DataFrame:
    """course_code: 01/2026C1/P/04/120-03/5/000002-5A → periodo, nivel, paralelo; course_name → materia."""
    df = df.copy()
    partes = df["course_code"].str.split("/")
    df["periodo"] = partes.str[1]
    df["carrera_cod"] = partes.str[3] + "/" + partes.str[4]
    df["carrera"] = df["carrera_cod"].map(CATALOGO)
    df["nivel"] = partes.str[5].astype(int)
    df["paralelo"] = partes.str[6].str.split("-").str[1].str[-1]
    df["materia"] = df["course_name"].str.rsplit(" - ", n=1).str[0]
    return df


def extraer_actividad(df: pd.DataFrame) -> pd.DataFrame:
    """Del nombre de la actividad saca el componente (PRF/PAE/AA), la fecha de entrega y si fue atrasada."""
    df = df.copy()
    df["componente"] = df["evaluacion"].str.extract(r":\s*(PRF|PAE|AA)\b")[0]
    df["fecha_entrega"] = pd.to_datetime(
        df["evaluacion"].str.extract(r"FECHA DE ENTREGA \((\d{2}/\d{2}/\d{4})")[0], dayfirst=True)
    df["semana"] = ((df["fecha_entrega"] - INICIO).dt.days // 7 + 1)
    df["atrasado"] = df["evaluacion"].str.contains("(atrasado)", regex=False)
    for col in ["first_course_access", "last_course_access", "fecha_calificacion"]:
        df[col] = pd.to_datetime(df[col], dayfirst=True)
    return df


# --------------------------------------------------------------------------- #
# 3. Limpieza 
# --------------------------------------------------------------------------- #
def limpiar(df: pd.DataFrame) -> pd.DataFrame:
    """Quita filas duplicadas (mismo estudiante, curso y actividad)."""
    return df.drop_duplicates(subset=["id_estudiante", "course_id", "evaluacion"]).reset_index(drop=True)


# --------------------------------------------------------------------------- #
# 4. Tabla resumen: una fila por estudiante y curso
# --------------------------------------------------------------------------- #
def resumir_por_curso(df: pd.DataFrame, semana_corte: int = SEMANA_CORTE) -> pd.DataFrame:
    """Calcula variables de INICIO de ciclo (primeras semanas) y el resultado final."""
    clave = ["id_estudiante", "course_id"]
    info = df.drop_duplicates(clave)[clave + ["course_code", "periodo", "carrera_cod", "carrera", "nivel", "paralelo",
                                              "materia", "first_course_access", "last_course_access"]]
    final = (df[df["tipo_evaluacion"] == "course"]
             .set_index(clave)["porcentaje"].rename("nota_final"))

    act = df[df["componente"].notna()].copy()
    act["entregada"] = act["nota_obtenida"].notna()
    act["pct0"] = act["porcentaje"].fillna(0)                     # no entregada = 0
    temprano = act[act["semana"] <= semana_corte]
    g_t = temprano.groupby(clave)
    g = act.groupby(clave)
    res = pd.DataFrame({
        "actividades_total": g.size(),
        "entregadas_pct": g["entregada"].mean() * 100,
        "atrasadas": g["atrasado"].sum(),
        "actividades_inicio": g_t.size(),
        "entregadas_inicio_pct": g_t["entregada"].mean() * 100,
        "promedio_inicio": g_t["pct0"].mean(),
    })
    out = info.set_index(clave).join(res).join(final).reset_index()
    out["dias_primer_acceso"] = (out["first_course_access"] - INICIO).dt.days
    out["dias_sin_entrar_al_final"] = (FIN - out["last_course_access"]).dt.days.clip(lower=0)
    out["hora_primer_acceso"] = out["first_course_access"].dt.hour
    out["estado"] = np.where(out["nota_final"] >= NOTA_MINIMA, "Aprobado", "Reprobado")
    out["reprobo"] = (out["estado"] == "Reprobado").astype(int)
    num = out.select_dtypes("number").columns
    out[num] = out[num].round(2)
    return out


# --------------------------------------------------------------------------- #
# 5. Diagnóstico 
# --------------------------------------------------------------------------- #
def diagnostico_eda(df: pd.DataFrame) -> pd.DataFrame:
    """Para cada columna numérica: asimetría, atípicos IQR, razón std/uniforme y p-valor KS."""
    filas = {}
    for col in df.select_dtypes("number").columns:
        s = df[col].dropna()
        q1, q3 = s.quantile([.25, .75]); iqr = q3 - q1
        rango = s.max() - s.min()
        filas[col] = {
            "asimetria": s.skew(),
            "atipicos_iqr": int(((s < q1 - 1.5 * iqr) | (s > q3 + 1.5 * iqr)).sum()),
            "razon_std_uniforme": s.std() / (rango / np.sqrt(12)) if rango else np.nan,
            "p_ks_uniforme": stats.kstest(s, "uniform", args=(s.min(), rango)).pvalue if rango else np.nan,
        }
    return pd.DataFrame(filas).T
