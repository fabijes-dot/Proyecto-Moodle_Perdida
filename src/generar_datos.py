"""
Simulación de una exportación de calificaciones de Moodle-EVA
====================================================================================
Datos SINTÉTICOS con la MISMA ESTRUCTURA que el reporte real de Moodle EVA: una fila por estudiante-curso-actividad calificada.

Columnas:
  student_id, username, firstname, lastname, email        → mdl_user 
  course_id, course_code, course_name                     → mdl_course
  first_course_access, last_course_access                 → logs / mdl_user_lastaccess
  evaluacion, tipo_evaluacion                             → mdl_grade_items (itemname, itemtype)
  nota_obtenida, nota_maxima, porcentaje, fecha_calificacion → mdl_grade_grades

Los nombres de las actividades siguen el formato real:
  "ASISTIDO POR EL PROFESOR: PRF ││ 10 PTOS ││ <tema> ││ FECHA DE ENTREGA (18/04/2026)"
  componentes: PRF (asistido por el profesor), PAE (práctico experimental), AA (aprendizaje autónomo)

Ciclo simulado: 15/03/2026- 07/08/2026. Se aprueba con 70 % de la nota final.
Incluye problemas reales: notas sin calificar, entregas "atrasado", filas duplicadas.
"""
import numpy as np
import pandas as pd

NOTA_MINIMA = 70                       # % para aprobar
INICIO = pd.Timestamp("2026-03-15")
FIN = pd.Timestamp("2026-08-07")
PERIODO = "2026C1"

# carrera: (código "unidad/carrera-versión", probabilidad, dificultad)
CARRERAS = {
    "MEDICINA": ("01/101-01", .18, .45), "DERECHO": ("02/145-01", .16, .15),
    "INGENIERÍA DE SOFTWARE": ("03/210-01", .14, .35), "CONTABILIDAD Y AUDITORÍA": ("04/132-02", .14, .20),
    "ENFERMERÍA": ("01/188-01", .14, .10), "PSICOLOGÍA": ("05/167-02", .12, .05),
    "ECONOMÍA": ("04/120-03", .12, .15)}
MATERIAS = {
    "MEDICINA": ["ANATOMÍA HUMANA", "BIOQUÍMICA", "FISIOLOGÍA", "METODOLOGÍA DE LA INVESTIGACIÓN"],
    "DERECHO": ["DERECHO CIVIL", "DERECHO PENAL", "DERECHO CONSTITUCIONAL", "METODOLOGÍA DE LA INVESTIGACIÓN"],
    "INGENIERÍA DE SOFTWARE": ["CÁLCULO DIFERENCIAL", "PROGRAMACIÓN I", "BASE DE DATOS", "METODOLOGÍA DE LA INVESTIGACIÓN"],
    "CONTABILIDAD Y AUDITORÍA": ["CONTABILIDAD GENERAL", "MATEMÁTICA FINANCIERA", "TRIBUTACIÓN", "METODOLOGÍA DE LA INVESTIGACIÓN"],
    "ENFERMERÍA": ["ANATOMÍA HUMANA", "CUIDADO BÁSICO", "FARMACOLOGÍA", "METODOLOGÍA DE LA INVESTIGACIÓN"],
    "PSICOLOGÍA": ["PSICOLOGÍA GENERAL", "ESTADÍSTICA", "NEUROCIENCIAS", "METODOLOGÍA DE LA INVESTIGACIÓN"],
    "ECONOMÍA": ["MACROECONOMÍA", "MICROECONOMÍA", "ESTADÍSTICA", "METODOLOGÍA DE LA INVESTIGACIÓN"]}
DIF_MATERIA = {"CÁLCULO DIFERENCIAL": .60, "BIOQUÍMICA": .50, "ANATOMÍA HUMANA": .40, "ESTADÍSTICA": .35,
               "MATEMÁTICA FINANCIERA": .35, "PROGRAMACIÓN I": .30, "FARMACOLOGÍA": .30, "MACROECONOMÍA": .25}

# Plan de evaluación de cada curso: (componente, etiqueta, tema, semana de entrega, puntaje máximo)
PLAN = [("PRF", "10 PTOS", "Tarea 1", 5), ("PRF", "10 PTOS", "Tarea 2", 5),
        ("PRF", "10 PTOS", "Cuestionario 1", 6), ("PRF", "10 PTOS", "Casos prácticos", 6),
        ("AA", "10 PTOS", "PRUEBA BLOQUE NRO 1", 9), ("PRF", "10 PTOS", "Tarea 3", 11),
        ("PRF", "10 PTOS", "Tarea 4", 11), ("PRF", "10 PTOS", "Cuestionario 2", 12),
        ("AA", "10 PTOS", "PRUEBA BLOQUE NRO 2", 13), ("PRF", "10 PTOS", "Cuestionario 3", 18),
        ("PAE", "10 PTOS", "Práctica de laboratorio", 20), ("PAE", "VALORACIÓN DE LA TAREA", "Informe de la práctica", 20),
        ("AA", "10 PTOS", "PRUEBA BLOQUE NRO 3", 19)]
COMPONENTE = {"PRF": "ASISTIDO POR EL PROFESOR", "PAE": "PRÁCTICO EXPERIMENTAL", "AA": "APRENDIZAJE AUTÓNOMO"}
RESULTADO_APRENDIZAJE = ("Aplicar los contenidos de la asignatura en la resolución de problemas "
                         "del contexto local, nacional e internacional")

NOMBRES = ["ANA", "LUIS", "MARÍA", "JORGE", "CARLA", "DIEGO", "SOFÍA", "PABLO", "VALERIA",
           "ANDRÉS", "CAMILA", "MATEO", "DANIELA", "JUAN", "PAULA", "ESTEBAN"]
APELLIDOS = ["PÉREZ", "GUERRERO", "ANDRADE", "ZAMBRANO", "VERA", "MORA", "SALAZAR", "ORTIZ",
             "CÁRDENAS", "MOLINA", "REYES", "VÁZQUEZ", "CALLE", "OCHOA", "LEÓN", "SERRANO"]


def _sin_tildes(t):
    return t.translate(str.maketrans("ÁÉÍÓÚÑ", "AEIOUN"))


def _fecha_hora(dia, hora):
    return (dia.normalize() + pd.to_timedelta(hora, unit="h")).strftime("%d/%m/%Y %H:%M")


def generar_crudo(n_estudiantes=800, semilla=2026):
    """Exportación cruda simulada con datos personales ficticios."""
    rng = np.random.default_rng(semilla)
    carreras = list(CARRERAS)
    p = np.array([CARRERAS[c][1] for c in carreras]); p = p / p.sum()
    todas = sorted({m for l in MATERIAS.values() for m in l})
    cod_materia = {m: 11 * (i + 1) for i, m in enumerate(todas)}

    filas, course_ids = [], {}
    for i in range(n_estudiantes):
        nombre = f"{rng.choice(NOMBRES)} {rng.choice(NOMBRES)}"
        ap1, ap2 = rng.choice(APELLIDOS, 2)
        correo = f"{_sin_tildes(nombre.split()[0]).lower()}.{_sin_tildes(ap1).lower()}{i:04d}@est.ejemplo.edu.ec"
        carrera = rng.choice(carreras, p=p)
        nivel, paralelo = int(rng.integers(1, 6)), rng.choice(["A", "B"])
        compromiso = rng.normal(0, 1)                       # oculto: constante del estudiante
        abandona = rng.random() < .06 + .06 * (compromiso < -1)  # deja de entrar a mitad de ciclo
        hora_habitual = float(np.clip(rng.normal(20 - 1.5 * compromiso, 2.5), 6, 23.9))  # tarde = menos compromiso

        for m in MATERIAS[carrera]:
            codigo = f"01/{PERIODO}/P/{CARRERAS[carrera][0]}/{nivel}/{cod_materia[m]:06d}-{nivel}{paralelo}"
            course_ids.setdefault(codigo, 3000 + len(course_ids))
            c = compromiso + rng.normal(0, .5)              # compromiso en esa materia
            dif = CARRERAS[carrera][2] + DIF_MATERIA.get(m, 0)

            # ---- accesos ----
            dias_primer = int(np.clip(rng.exponential(4 + 6 * max(0, -c)), 0, 60))
            primer = INICIO + pd.Timedelta(days=dias_primer)
            semana_abandono = rng.integers(6, 14) if abandona else 99
            ultimo = min(FIN, INICIO + pd.Timedelta(weeks=int(semana_abandono)) - pd.Timedelta(days=int(rng.integers(0, 6)))) \
                if abandona else FIN - pd.Timedelta(days=int(rng.integers(0, 10)))
            base = {"student_id": 10000 + i, "username": correo, "firstname": nombre,
                    "lastname": f"{ap1} {ap2}", "email": correo, "course_id": course_ids[codigo],
                    "course_code": codigo, "course_name": f"{m} - {nivel}{paralelo}",
                    "first_course_access": _fecha_hora(primer, hora_habitual + rng.normal(0, 1)),
                    "last_course_access": _fecha_hora(ultimo, hora_habitual + rng.normal(0, 1))}

            # ---- actividades ----
            obtenido = maximo = 0.0
            filas.append({**base, "evaluacion": "Evaluación diagnóstica", "tipo_evaluacion": "mod",
                          "nota_obtenida": np.nan, "nota_maxima": 1.0, "porcentaje": np.nan, "fecha_calificacion": np.nan})
            for comp, etq, tema, semana in PLAN:
                entrega = INICIO + pd.Timedelta(weeks=semana) - pd.Timedelta(days=int(rng.integers(1, 4)))
                nombre_act = (f"{COMPONENTE[comp]}: {comp} ││ {etq} ││ {tema} ││ "
                              f"FECHA DE ENTREGA ({entrega:%d/%m/%Y})")
                # probabilidad de entregar: cae si abandonó, si entró tarde y con poco compromiso
                p_entrega = 1 / (1 + np.exp(-(4.2 + 1.6 * c - .05 * dias_primer)))
                if semana >= semana_abandono:
                    p_entrega *= .08
                maximo += 1.0
                if rng.random() < p_entrega:
                    atrasado = rng.random() < .10 + .10 * (c < 0)
                    nota = float(np.clip(rng.normal(.90 + .09 * c - .12 * dif, .12), .2, 1.0))
                    if atrasado:
                        nota = max(.2, nota - .1)
                        nombre_act += " (atrasado)"
                    califica = entrega + pd.Timedelta(days=int(rng.integers(1, 45)))
                    obtenido += nota
                    filas.append({**base, "evaluacion": nombre_act, "tipo_evaluacion": "mod",
                                  "nota_obtenida": round(nota, 2), "nota_maxima": 1.0,
                                  "porcentaje": round(100 * nota, 2),
                                  "fecha_calificacion": _fecha_hora(min(califica, FIN), rng.uniform(8, 22))})
                else:          # no entregó: el ítem aparece en el calificador, pero sin nota
                    filas.append({**base, "evaluacion": nombre_act, "tipo_evaluacion": "mod",
                                  "nota_obtenida": np.nan, "nota_maxima": 1.0, "porcentaje": np.nan,
                                  "fecha_calificacion": np.nan})
            # resultado de aprendizaje (lo califica el docente al cierre)
            ra = float(np.clip((obtenido / maximo) * 1.5 + rng.normal(0, .12), 0, 1.5)) if obtenido else 0.0
            obtenido += ra; maximo += 1.5
            filas.append({**base, "evaluacion": RESULTADO_APRENDIZAJE, "tipo_evaluacion": "mod",
                          "nota_obtenida": round(ra, 2), "nota_maxima": 1.5, "porcentaje": round(100 * ra / 1.5, 2),
                          "fecha_calificacion": _fecha_hora(FIN - pd.Timedelta(days=1), rng.uniform(8, 22))})
            filas.append({**base, "evaluacion": "NOTA FINAL DEL CURSO", "tipo_evaluacion": "course",
                          "nota_obtenida": round(obtenido, 2), "nota_maxima": maximo,
                          "porcentaje": round(100 * obtenido / maximo, 2),
                          "fecha_calificacion": _fecha_hora(FIN - pd.Timedelta(days=1), rng.uniform(8, 22))})

    df = pd.DataFrame(filas)
    df = pd.concat([df, df.sample(40, random_state=semilla)], ignore_index=True)   # duplicados
    return df
