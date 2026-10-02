"""
Permite generar → anonimizar → extraer → limpiar → resumir
"""

import os
from src.generar_datos import generar_crudo
from src.limpieza import (anonimizar, k_anonimato, suprimir_grupos_pequenos, extraer_curso,
                          extraer_actividad, limpiar, resumir_por_curso)

#Calcula en donde estan los archvios 
RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CRUDO = os.path.join(RAIZ, "data", "crudos", "evea_export_simulado.csv")
PROC_ACT = os.path.join(RAIZ, "data", "procesados", "calificaciones_anon.csv")
PROC_CUR = os.path.join(RAIZ, "data", "procesados", "cursos_anon.csv")
CUASI = ["carrera_cod", "nivel", "paralelo"]


def leer_sal() -> str:
    """La sal se lee del archivo .env (que NO se sube a GitHub)."""
    ruta = os.path.join(RAIZ, ".env")
    if os.path.exists(ruta):
        for linea in open(ruta, encoding="utf-8"):
            if linea.startswith("SAL="):
                return linea.strip().split("=", 1)[1]
    print("⚠️  No hay .env: se usa una sal de ejemplo. Copia .env.example a .env y cámbiala.")
    return "sal-de-ejemplo-cambiar"


def main():
    for ruta in (CRUDO, PROC_ACT):                      # crea data/crudos y data/procesados si no existen
        os.makedirs(os.path.dirname(ruta), exist_ok=True)
    crudo = generar_crudo()
    crudo.to_csv(CRUDO, index=False)
    print(f"Crudo (datos personales ficticios): {crudo.shape} → {CRUDO}")

    datos = extraer_curso(anonimizar(crudo, leer_sal()))
    k, riesgo = k_anonimato(datos, CUASI)
    print(f"k-anonimato con {CUASI}: k = {k} | grupos con < 5 estudiantes: {riesgo}")
    if riesgo:
        datos, n = suprimir_grupos_pequenos(datos, CUASI)
        print(f"  Se suprimieron {n} estudiantes → k = {k_anonimato(datos, CUASI)[0]}")

    datos = limpiar(extraer_actividad(datos))
    datos.to_csv(PROC_ACT, index=False) #se gnera el archivo calificaciones_anon, una fila por actividad
    cursos = resumir_por_curso(datos)
    cursos.to_csv(PROC_CUR, index=False) # genera archivo cursos_anon una fila por estudiante y materia
    print(f"Calificaciones (anónimas): {datos.shape} → {PROC_ACT}")
    print(f"Resumen por curso:         {cursos.shape} → {PROC_CUR}")


if __name__ == "__main__":
    main()
