"""Inspecciona la recuperación antes de pedir una respuesta al LLM."""

import argparse
from importlib import import_module

common = import_module("1-common")
TOP_K = 3  # Cambia solo este valor para la práctica manual.


def leer_argumentos() -> argparse.Namespace:
    """Lee la pregunta y los filtros opcionales usados por búsqueda y RAG.

    TOP_K se modifica en el código durante la práctica, no como argumento de CLI.
    """
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "pregunta",
        nargs="?",
        default="¿Qué datos necesito para solicitar una inscripción?",
    )
    parser.add_argument(
        "--documento", help="Filtra por documento, por ejemplo inscripciones."
    )
    parser.add_argument(
        "--tipo",
        choices=["politica", "procedimiento", "faq", "documento"],
        help="Filtra por tipo de documento.",
    )
    return parser.parse_args()


def main() -> None:
    """Guarda y muestra los fragmentos, su similitud y su procedencia documental."""
    argumentos = leer_argumentos()
    resultado = common.buscar(
        pregunta=argumentos.pregunta,
        documento=argumentos.documento,
        tipo=argumentos.tipo,
        top_k=TOP_K,
    )
    common.guardar_json(common.DIRECTORIO_RESULTADOS / "busqueda.json", resultado)
    print("Consulta:", resultado["consulta"])
    print("Filtro:", resultado["filtro"])
    for fragmento in resultado["fragmentos"]:
        print(f"\n{fragmento['id']} · similitud {fragmento['score']:.4f}")
        print(
            f"{fragmento['titulo']} · versión {fragmento['version']} · tipo {fragmento['tipo']} · "
            f"página {fragmento['pagina']} · {fragmento['seccion']} · parte {fragmento['parte']}"
        )
        print(fragmento["texto"])
        print("PDF original:", fragmento["url"])
    if not resultado["fragmentos"]:
        print("Sin resultados dentro del ámbito pedido.")
    print("La similitud no mide la probabilidad de que una respuesta sea cierta.")


if __name__ == "__main__":
    common.ejecutar(main)
