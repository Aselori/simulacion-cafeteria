"""Módulo 3 — Motor de eventos discretos: descripción del algoritmo + traza."""

import customtkinter as ctk

from .. import theme as t
from ..components import Card, ExplainBox, TechBlock, Bullets
from .base import Module


EVENT_DESCRIPTIONS = {
    "LLEGADA": ("Un cliente llega al sistema. Si el servidor está libre lo atiende "
                "de inmediato; si está ocupado o de vacaciones, entra a la cola. "
                "Siempre se programa la siguiente llegada con Exp(λ)."),
    "FIN_SERV": ("Termina el servicio del cliente en curso. Si hay cola, atiende al "
                 "siguiente; si no, el servidor inicia una vacación de duración Exp(θ)."),
    "FIN_VAC":  ("Termina una vacación del servidor. Si hay clientes en cola, los "
                 "atiende; si la cola sigue vacía, inicia OTRA vacación (vacaciones "
                 "múltiples — ésta es la clave del modelo)."),
}

EVENT_COLOR = {
    "LLEGADA": t.ACCENT,
    "FIN_SERV": t.SUCCESS,
    "FIN_VAC": t.WARN,
}


class ModEventos(Module):
    number = 5
    title = "Motor de simulación de eventos discretos"
    subtitle = ("El reloj avanza de evento en evento (no en pasos fijos). Una cola de "
                "prioridad guarda los próximos eventos en orden cronológico.")
    needs_simulation = True

    def render(self, state):
        sim = state.sim
        # Counters
        stats = Card(self.body, fg_color=t.BG_SOFT)
        stats.pack(fill="x", pady=(0, t.PAD_MD))
        ctk.CTkLabel(
            stats,
            text=(f"Eventos procesados: {sim['total_eventos']:,}     "
                  f"Llegadas: {sim['clientes_llegados']:,}     "
                  f"Atendidos: {sim['clientes_servidos']:,}     "
                  f"Vacaciones: {sim['total_vacaciones']:,}     "
                  f"Tiempo simulado: {sim['t_efectivo']:.1f} min"),
            font=t.mono(t.SIZE_MONO_SMALL), text_color=t.TEXT, anchor="w",
        ).pack(fill="x", padx=t.PAD_MD, pady=t.PAD_SM)

        # Event-type legend with explanations
        legend = Card(self.body, fg_color=t.BG_SOFT)
        legend.pack(fill="x", pady=(0, t.PAD_MD))
        ctk.CTkLabel(
            legend, text="Tipos de evento",
            font=t.font(t.SIZE_SMALL, "bold"), text_color=t.TEXT, anchor="w",
        ).pack(fill="x", padx=t.PAD_MD, pady=(t.PAD_SM, 4))

        for ev, desc in EVENT_DESCRIPTIONS.items():
            row = ctk.CTkFrame(legend, fg_color="transparent")
            row.pack(fill="x", padx=t.PAD_MD, pady=(0, 4))
            ctk.CTkLabel(
                row, text=ev, font=t.mono(t.SIZE_MONO_SMALL, "bold"),
                text_color=EVENT_COLOR[ev], width=90, anchor="w",
            ).pack(side="left")
            ctk.CTkLabel(
                row, text=desc, font=t.font(t.SIZE_TINY),
                text_color=t.TEXT_MUTED, anchor="w", justify="left", wraplength=720,
            ).pack(side="left", fill="x", expand=True)
        ctk.CTkFrame(legend, fg_color="transparent", height=t.PAD_SM).pack()

        # Trace
        traza = sim.get("traza", [])
        ctk.CTkLabel(
            self.body, text=f"Traza de los primeros {len(traza)} eventos",
            font=t.font(t.SIZE_SMALL, "bold"), text_color=t.TEXT, anchor="w",
        ).pack(fill="x", pady=(0, t.PAD_XS))

        self._trace_table(traza)

        # ---- DES pseudocode ----
        tb1 = TechBlock(self.body, "Ficha técnica — Pseudocódigo del bucle principal")
        tb1.pack(fill="x", pady=(t.PAD_MD, t.PAD_SM))
        tb1.add_mono(
            "reloj ← 0\n"
            "estado ← LIBRE,  cola ← []\n"
            "FEL ← {(gen_llegada(), LLEGADA)}        # cola de prioridad por tiempo\n\n"
            "mientras FEL no esté vacía:\n"
            "    (t, tipo) ← extraer_mínimo(FEL)\n"
            "    si t > T_sim: detener\n"
            "    acumular_áreas(reloj → t)            # L(t), Lq(t), ocupado, vacación\n"
            "    reloj ← t\n"
            "    si tipo == LLEGADA:\n"
            "        si estado == LIBRE: estado ← OCUPADO; FEL += (t+gen_serv(), FIN_SERV)\n"
            "        si no: cola.append(t)\n"
            "        FEL += (t + gen_llegada(), LLEGADA)   # próxima llegada\n"
            "    si tipo == FIN_SERV:\n"
            "        si cola: t_llegada = cola.pop(); FEL += (t+gen_serv(), FIN_SERV)\n"
            "        si no:   estado ← VACACION; FEL += (t+gen_vac(), FIN_VAC)\n"
            "    si tipo == FIN_VAC:\n"
            "        si cola: estado ← OCUPADO; FEL += (t+gen_serv(), FIN_SERV)\n"
            "        si no:   FEL += (t+gen_vac(), FIN_VAC)     # vacación múltiple"
        )

        # ---- Variables and data structures ----
        tb2 = TechBlock(self.body, "Ficha técnica — Variables de estado")
        tb2.pack(fill="x", pady=(0, t.PAD_SM))
        tb2.add_bullets([
            ("reloj:", "tiempo simulado actual (avanza sólo en eventos)."),
            ("estado_servidor:", "LIBRE / OCUPADO / VACACION."),
            ("cola:", "deque de tiempos de llegada de los clientes en espera (FIFO)."),
            ("num_en_cola, num_en_sistema:", "contadores derivados, evitan recorrer "
             "la deque para promediar."),
            ("FEL:", "future event list — heap binario sobre (tiempo, tipo)."),
            ("area_cola, area_sistema:", "∫ Lq(t) dt y ∫ L(t) dt acumuladas."),
            ("area_ocupado, area_vacacion:", "fracciones del tiempo en cada estado."),
            ("total_espera, total_tiempo_sistema:", "sumas sobre clientes servidos, "
             "para promediar Wq y W."),
        ], mono_label=True)

        # ---- Why event-driven ----
        tb3 = TechBlock(self.body, "Ficha técnica — Por qué simulación de eventos discretos")
        tb3.pack(fill="x", pady=(0, t.PAD_SM))
        tb3.add_bullets([
            "Eficiente: el reloj salta directamente al siguiente evento; no se "
            "iteran instantes 'muertos' donde nada cambia.",
            "Exacta: como los eventos ocurren en tiempos continuos, no hay error "
            "de discretización (a diferencia de la simulación por pasos fijos).",
            "Las áreas bajo L(t) y Lq(t) se calculan exactamente como suma de "
            "rectángulos (Lq(t) es constante a trozos entre eventos).",
            "La cola de prioridad (heap binario) procesa cada evento en O(log n).",
        ])

        # ---- Estimators used ----
        tb4 = TechBlock(self.body, "Ficha técnica — Estimadores calculados")
        tb4.pack(fill="x", pady=(0, 0))
        tb4.add_bullets([
            ("L̂  =", "area_sistema / t_efectivo     (promedio temporal)"),
            ("L̂q =", "area_cola / t_efectivo        (promedio temporal)"),
            ("ρ̂  =", "area_ocupado / t_efectivo     (fracción del tiempo ocupado)"),
            ("Ŵ  =", "total_tiempo_sistema / clientes_servidos   (media por cliente)"),
            ("Ŵq =", "total_espera / clientes_servidos           (media por cliente)"),
        ], mono_label=True)
        tb4.add_text("Los promedios temporales son consistentes con el comportamiento "
                     "en estado estacionario; los promedios por cliente sólo cuentan "
                     "a los que terminaron el servicio (los aún en cola al cortar la "
                     "simulación no aportan).", muted=True)

        ExplainBox(
            self.body,
            body=("Cada evento mantiene actualizadas las áreas bajo las curvas L(t) "
                  "y Lq(t), de las que se obtienen los promedios ponderados por tiempo. "
                  "La cola de prioridad garantiza que los eventos se procesen en orden, "
                  "y los tres generadores aseguran que llegadas, servicios y vacaciones "
                  "sean estadísticamente independientes."),
            title="Por qué este módulo",
        ).pack(fill="x", pady=(t.PAD_MD, 0))

    def _trace_table(self, traza):
        table = Card(self.body, fg_color=t.BG_SOFT)
        table.pack(fill="x")

        if not traza:
            ctk.CTkLabel(
                table, text="(traza vacía)", font=t.font(t.SIZE_SMALL),
                text_color=t.TEXT_SUBTLE,
            ).pack(padx=t.PAD_MD, pady=t.PAD_MD)
            return

        headers = ("#", "Tiempo (min)", "Evento", "Cola antes", "Acción / siguiente")
        widths = (40, 110, 110, 90, 280)

        hdr = ctk.CTkFrame(table, fg_color="transparent")
        hdr.pack(fill="x", padx=t.PAD_MD, pady=(t.PAD_SM, 2))
        for h, w in zip(headers, widths):
            ctk.CTkLabel(
                hdr, text=h, font=t.font(t.SIZE_TINY, "bold"),
                text_color=t.TEXT_MUTED, width=w, anchor="w",
            ).pack(side="left", padx=2)
        ctk.CTkFrame(table, fg_color=t.BORDER, height=1).pack(fill="x", padx=t.PAD_MD)

        for i, ev in enumerate(traza, 1):
            row = ctk.CTkFrame(table, fg_color="transparent")
            row.pack(fill="x", padx=t.PAD_MD)
            color = EVENT_COLOR.get(ev["tipo"], t.TEXT)
            cells = [
                (str(i), t.TEXT_SUBTLE, "normal"),
                (f"{ev['t']:.3f}", t.TEXT, "normal"),
                (ev["tipo"], color, "bold"),
                (str(ev["cola_antes"]), t.TEXT, "normal"),
                (ev["servidor"], t.TEXT_MUTED, "normal"),
            ]
            for (txt, col, weight), w in zip(cells, widths):
                ctk.CTkLabel(
                    row, text=txt, font=t.mono(t.SIZE_MONO_SMALL, weight),
                    text_color=col, width=w, anchor="w",
                ).pack(side="left", padx=2)
        ctk.CTkFrame(table, fg_color="transparent", height=t.PAD_SM).pack()
