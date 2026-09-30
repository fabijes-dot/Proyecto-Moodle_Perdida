# Alerta temprana de pérdida de materias (EVA Moodle)

Trabajo final · Maestría en Inteligencia Artificial y Ciencia de Datos

**Asignatura:** Programación y Análisis de Datos

**Autores:** 
Fabiola Jescenia Chacha · Paul Vicente Huancayo · Henry Chicaiza · Gabriela Moscoso

## Pregunta de análisis
¿Qué factores se relacionan con que un estudiante **repruebe una materia**, y es posible **identificar a mitad del ciclo (semana 6)** a quienes están en riesgo?

**Alcance:** ciclos 1 a 5 de la carrera (primeros ciclos, donde se concentra la pérdida y el abandono).

## Fuente de datos
Los datos son sintéticos ya que simulan la exportación de calificaciones de un aula virtual EVA Moodle
(una fila por estudiante × curso × actividad), con la misma estructura que el reporte real.
No se usaron datos reales porque son datos personales y su uso requiere autorización según la **LOPDP**.
La simulación incluye datos personales **ficticios** (nombre, correo, id) para aplicar el proceso de anonimización.

Ciclo simulado: 15/03/2026 – 07/08/2026. Se aprueba con 70 %.

## Cómo ejecutarlo

```bash
pip install -r requirements.txt
python -m src.preparar_datos      # genera data/crudos y data/procesados
python -m streamlit run app.py    # abre el dashboard en http://localhost:8501
```

El notebook del análisis exploratorio está en `01_EDA.ipynb`
(necesita que antes se haya corrido `python -m src.preparar_datos`).

La **sal** del hash se lee de un archivo `.env` (no se sube a GitHub). Copia `.env.example` a `.env` y cambia la frase.

## Estructura

```
proyecto_perdida/
├── app.py                  # dashboard (Streamlit + Plotly)
├── 01_EDA.ipynb            # análisis exploratorio paso a paso
├── src/
│   ├── generar_datos.py    # simulación de la exportación de EVA Moodle
│   ├── limpieza.py         # anonimización, k-anonimato, limpieza, variables
│   └── preparar_datos.py   # pipeline completo
├── data/
│   ├── crudos/             # exportación con datos personales ficticios (NO se versiona)
│   └── procesados/         # datos anónimos y limpios (los usa el dashboard)
├── requirements.txt
├── .env.example            # plantilla de la sal secreta
└── .gitignore
```

## Protección de datos (LOPDP)
- Se eliminan nombre, apellido y correos; el id del estudiante se reemplaza por un **hash SHA-256 con sal**.
- **k-anonimato ≥ 5** con carrera, ciclo y paralelo (se suprimen estudiantes de grupos pequeños).
- El dashboard no muestra grupos con menos de 5 registros.
- `data/crudos/` y `.env` están en `.gitignore`.

## Hallazgos principales (sobre datos sintéticos)
1. Entrar tarde al aula virtual es una señal de alerta (≈16 % de reprobación si entra en 3 días vs ≈75 % si tarda más de 2 semanas).
2. El desempeño de las primeras 6 semanas anticipa el resultado final (Spearman 0,83).
3. La pérdida se concentra en el primer ciclo, en carreras de salud y en materias como Bioquímica y Cálculo.

> ⚠️ Limitación: las relaciones entre variables fueron definidas al simular los datos. El proyecto demuestra el **método**; la magnitud real de cada efecto se conocerá al aplicarlo a datos reales autorizados.
