"""Muestra la petición real y sus fuentes. No llama a servicios externos."""

import json
from importlib import import_module

common = import_module("1-common")


def main() -> None:
    """Lee la última traza para revisar mensajes, filtro, salida y procedencia."""
    traza = common.leer_json(common.DIRECTORIO_RESULTADOS / "ultima-respuesta.json")
    print("Estado:", traza["estado"])
    print("Namespace:", traza["recuperacion"]["namespace"])
    print("Filtro:", traza["recuperacion"]["filtro"])
    for fragmento in traza["recuperacion"]["fragmentos"]:
        print("PDF original:", fragmento["url"])
    print("Mensajes enviados al modelo:")
    print(json.dumps(traza["messages"], ensure_ascii=False, indent=2))
    # Sin fragmentos no se llama al modelo: solo se guarda la salida de abstención.
    salida_mostrada = traza.get("salida_original", traza.get("salida"))
    print("Salida:", salida_mostrada)
    print("Revisa el origen de cada afirmación en el PDF y la página indicados.")


if __name__ == "__main__":
    common.ejecutar(main)
