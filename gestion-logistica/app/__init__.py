"""Paquete de la app.

`app` se crea recién cuando alguien lo pide, para que el comando de inicio
funcione escrito de las dos formas: `gunicorn wsgi:app` (el recomendado) o
`gunicorn app:app` (el que Azure pone por defecto en algunos casos).
"""


def __getattr__(nombre):
    if nombre == "app":
        from .server import create_app
        globals()["app"] = create_app()
        return globals()["app"]
    raise AttributeError(nombre)
