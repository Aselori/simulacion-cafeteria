"""Simulación M/M/1 con Vacaciones Múltiples — Interfaz gráfica.

Punto de entrada. La lógica vive en `simulacion_cafeteria.py` (intacta) y la
interfaz en el paquete `gui/`, organizada como un asistente paso a paso:

    1. Parámetros   →  2. Analítico  →  3. Generadores
                        →  4. Simulación  →  5. Resultados
"""

from gui.app import App


if __name__ == "__main__":
    App().mainloop()
