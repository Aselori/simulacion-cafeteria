"""
Simulación M/M/1 con Vacaciones Múltiples — Interfaz Gráfica
Cafetería Universitaria — UANL

Versión con GUI (tkinter) del simulador de colas con vacaciones del servidor.
Importa la lógica central de simulacion_cafeteria.py
"""

import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
import math
import io
import threading

from simulacion_cafeteria import (
    MersenneTwister, LCG, MRG,
    gen_interarrival, gen_service_time, gen_vacation_time,
    calcular_analitico, simular, ejecutar_replicas,
    chi_cuadrado_exp, reporte_completo,
)


# ============================================================================
# Generación del reporte detallado como string
# ============================================================================

def generar_reporte_texto(sim, analitico, lam, mu, theta, t_sim, t_warmup, seeds,
                          replicas_result=None):
    buf = io.StringIO()
    reporte_completo(sim, analitico, lam, mu, theta, t_sim, t_warmup, seeds,
                     replicas_result=replicas_result,
                     print_fn=lambda *a, **kw: print(*a, file=buf, **kw))
    return buf.getvalue()


# ============================================================================
# Aplicación GUI
# ============================================================================

class SimulacionApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Simulación M/M/1 con Vacaciones Múltiples — Cafetería UANL")
        self.root.geometry("1050x800")
        self.root.minsize(900, 600)

        self._build_ui()

    def _build_ui(self):
        frame_top = ttk.LabelFrame(self.root, text="  Parámetros del Sistema  ", padding=10)
        frame_top.pack(fill="x", padx=10, pady=(10, 5))

        row1 = ttk.Frame(frame_top)
        row1.pack(fill="x", pady=2)

        ttk.Label(row1, text="λ (clientes/min):").pack(side="left", padx=(0, 5))
        self.var_lam = tk.StringVar(value="0.5")
        ttk.Entry(row1, textvariable=self.var_lam, width=8).pack(side="left", padx=(0, 15))

        ttk.Label(row1, text="μ (clientes/min):").pack(side="left", padx=(0, 5))
        self.var_mu = tk.StringVar(value="0.67")
        ttk.Entry(row1, textvariable=self.var_mu, width=8).pack(side="left", padx=(0, 15))

        ttk.Label(row1, text="θ (retornos/min):").pack(side="left", padx=(0, 5))
        self.var_theta = tk.StringVar(value="0.2")
        ttk.Entry(row1, textvariable=self.var_theta, width=8).pack(side="left", padx=(0, 15))

        ttk.Label(row1, text="T sim (min):").pack(side="left", padx=(0, 5))
        self.var_tsim = tk.StringVar(value="10000")
        ttk.Entry(row1, textvariable=self.var_tsim, width=8).pack(side="left", padx=(0, 15))

        ttk.Label(row1, text="T warmup (min):").pack(side="left", padx=(0, 5))
        self.var_twarm = tk.StringVar(value="500")
        ttk.Entry(row1, textvariable=self.var_twarm, width=8).pack(side="left")

        row2 = ttk.Frame(frame_top)
        row2.pack(fill="x", pady=2)

        ttk.Label(row2, text="Semillas →").pack(side="left", padx=(0, 5))
        ttk.Label(row2, text="MT19937:").pack(side="left", padx=(0, 3))
        self.var_s_mt = tk.StringVar(value="19937")
        ttk.Entry(row2, textvariable=self.var_s_mt, width=8).pack(side="left", padx=(0, 15))

        ttk.Label(row2, text="LCG:").pack(side="left", padx=(0, 3))
        self.var_s_lcg = tk.StringVar(value="48271")
        ttk.Entry(row2, textvariable=self.var_s_lcg, width=8).pack(side="left", padx=(0, 15))

        ttk.Label(row2, text="MRG₁:").pack(side="left", padx=(0, 3))
        self.var_s_mrg1 = tk.StringVar(value="31415")
        ttk.Entry(row2, textvariable=self.var_s_mrg1, width=8).pack(side="left", padx=(0, 15))

        ttk.Label(row2, text="MRG₂:").pack(side="left", padx=(0, 3))
        self.var_s_mrg2 = tk.StringVar(value="92653")
        ttk.Entry(row2, textvariable=self.var_s_mrg2, width=8).pack(side="left", padx=(0, 15))

        self.var_replicas = tk.BooleanVar(value=True)
        ttk.Checkbutton(row2, text="10 Réplicas + IC 95%",
                        variable=self.var_replicas).pack(side="left", padx=10)

        self.btn_run = ttk.Button(row2, text="  Ejecutar Simulación  ", command=self._run)
        self.btn_run.pack(side="right", padx=5)

        # Barra de estado
        self.var_status = tk.StringVar(value="Listo")
        status_bar = ttk.Label(self.root, textvariable=self.var_status,
                               relief="sunken", anchor="w", padding=(5, 2))
        status_bar.pack(fill="x", side="bottom", padx=10, pady=(0, 5))

        # Notebook con pestañas
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill="both", expand=True, padx=10, pady=5)

        # Pestaña 1: Resumen
        self.tab_resumen = ttk.Frame(self.notebook)
        self.notebook.add(self.tab_resumen, text="  Resumen  ")
        self._build_resumen_tab()

        # Pestaña 2: Detalles
        self.tab_detalles = ttk.Frame(self.notebook)
        self.notebook.add(self.tab_detalles, text="  Detalles  ")
        self.txt_detalles = scrolledtext.ScrolledText(
            self.tab_detalles, wrap="none", font=("Courier", 10))
        self.txt_detalles.pack(fill="both", expand=True, padx=5, pady=5)

        h_scroll = ttk.Scrollbar(self.tab_detalles, orient="horizontal",
                                 command=self.txt_detalles.xview)
        self.txt_detalles.configure(xscrollcommand=h_scroll.set)
        h_scroll.pack(fill="x")

    def _build_resumen_tab(self):
        self.resumen_frame = ttk.Frame(self.tab_resumen)
        self.resumen_frame.pack(fill="both", expand=True, padx=5, pady=5)

        self.lbl_placeholder = ttk.Label(
            self.resumen_frame,
            text="Presione 'Ejecutar Simulación' para ver los resultados.",
            font=("Helvetica", 12), anchor="center")
        self.lbl_placeholder.pack(expand=True)

    def _populate_resumen(self, sim, analitico, lam, mu, theta, replicas_result=None):
        for w in self.resumen_frame.winfo_children():
            w.destroy()

        canvas = tk.Canvas(self.resumen_frame)
        v_scroll = ttk.Scrollbar(self.resumen_frame, orient="vertical", command=canvas.yview)
        scrollable = ttk.Frame(canvas)

        scrollable.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=scrollable, anchor="nw")
        canvas.configure(yscrollcommand=v_scroll.set)

        canvas.pack(side="left", fill="both", expand=True)
        v_scroll.pack(side="right", fill="y")

        # Header
        header = ttk.Label(scrollable,
                           text="SIMULACIÓN M/M/1 CON VACACIONES MÚLTIPLES — CAFETERÍA UANL",
                           font=("Helvetica", 14, "bold"))
        header.pack(pady=(10, 5))

        # Parámetros
        f_params = ttk.LabelFrame(scrollable, text="  Parámetros  ", padding=8)
        f_params.pack(fill="x", padx=10, pady=5)

        params_text = (
            f"λ = {lam:.4f} clientes/min  |  μ = {mu:.4f} clientes/min  |  "
            f"θ = {theta:.4f} retornos/min  |  ρ = {analitico['rho']:.4f}"
        )
        ttk.Label(f_params, text=params_text, font=("Courier", 10)).pack()

        params_text2 = (
            f"1/λ = {1/lam:.2f} min (entre llegadas)  |  "
            f"1/μ = {1/mu:.2f} min (servicio)  |  "
            f"1/θ = {1/theta:.2f} min (vacación)"
        )
        ttk.Label(f_params, text=params_text2, font=("Courier", 10)).pack()

        stability = "ESTABLE ✓" if analitico["rho"] < 1 else "INESTABLE ✗"
        ttk.Label(f_params, text=f"Condición de estabilidad: ρ = {analitico['rho']:.4f} → {stability}",
                  font=("Courier", 10, "bold")).pack(pady=(3, 0))

        # Métricas: Simulación vs Analítico
        f_metrics = ttk.LabelFrame(scrollable, text="  Comparación: Simulación vs Analítico  ", padding=8)
        f_metrics.pack(fill="x", padx=10, pady=5)

        cols = ("Métrica", "Simulación", "Analítico", "Error (%)")
        tree = ttk.Treeview(f_metrics, columns=cols, show="headings", height=5)
        for col in cols:
            tree.heading(col, text=col)
            tree.column(col, width=150, anchor="center")
        tree.column("Métrica", width=200, anchor="w")

        metricas = [
            ("ρ (utilización)", sim["rho"], analitico["rho"]),
            ("L (en sistema)", sim["L"], analitico["L"]),
            ("Lq (en cola)", sim["Lq"], analitico["Lq"]),
            ("W (tiempo en sistema, min)", sim["W"], analitico["W"]),
            ("Wq (tiempo en cola, min)", sim["Wq"], analitico["Wq"]),
        ]
        for nombre, s_val, a_val in metricas:
            if a_val != 0 and math.isfinite(a_val):
                err = f"{abs(s_val - a_val) / a_val * 100:.2f}%"
            else:
                err = "N/A"
            tree.insert("", "end", values=(nombre, f"{s_val:.4f}", f"{a_val:.4f}", err))

        tree.pack(fill="x", pady=3)

        # Estadísticas de vacaciones
        f_vac = ttk.LabelFrame(scrollable, text="  Estadísticas del Servidor  ", padding=8)
        f_vac.pack(fill="x", padx=10, pady=5)

        vac_lines = [
            f"Clientes llegados: {sim['clientes_llegados']:,}  |  "
            f"Clientes servidos: {sim['clientes_servidos']:,}  |  "
            f"Eventos procesados: {sim['total_eventos']:,}",
            f"Vacaciones tomadas: {sim['total_vacaciones']:,}  |  "
            f"Fracción tiempo ocupado: {sim['rho']:.4f}  |  "
            f"Fracción tiempo vacación: {sim['rho_vacacion']:.4f}  |  "
            f"Fracción tiempo libre: {1 - sim['rho'] - sim['rho_vacacion']:.4f}",
        ]
        for line in vac_lines:
            ttk.Label(f_vac, text=line, font=("Courier", 10)).pack(anchor="w")

        # Réplicas e intervalos de confianza
        if replicas_result:
            rr = replicas_result
            stats = rr["stats"]
            a = rr["analitico"]

            f_ci = ttk.LabelFrame(scrollable, text="  Intervalos de Confianza al 95% (10 Réplicas)  ", padding=8)
            f_ci.pack(fill="x", padx=10, pady=5)

            ci_cols = ("Métrica", "Analítico", "IC Inferior", "IC Superior", "Media Sim.", "Contiene")
            ci_tree = ttk.Treeview(f_ci, columns=ci_cols, show="headings", height=5)
            for col in ci_cols:
                ci_tree.heading(col, text=col)
                ci_tree.column(col, width=120, anchor="center")
            ci_tree.column("Métrica", width=180, anchor="w")

            for nombre, clave, a_val in [
                ("ρ (utilización)", "rho", a["rho"]),
                ("L (en sistema)", "L", a["L"]),
                ("Lq (en cola)", "Lq", a["Lq"]),
                ("W (min)", "W", a["W"]),
                ("Wq (min)", "Wq", a["Wq"]),
            ]:
                st = stats[clave]
                contiene = "✓" if st["ci_lower"] <= a_val <= st["ci_upper"] else "✗"
                ci_tree.insert("", "end", values=(
                    nombre, f"{a_val:.4f}",
                    f"{st['ci_lower']:.4f}", f"{st['ci_upper']:.4f}",
                    f"{st['media']:.4f}", contiene
                ))

            ci_tree.pack(fill="x", pady=3)

            # Validación
            f_val = ttk.LabelFrame(scrollable, text="  Validación (§8.4)  ", padding=8)
            f_val.pack(fill="x", padx=10, pady=5)

            val = rr["validacion"]
            val_lines = [
                f"1. Wq analítico dentro del IC 95%:  {'PASA ✓' if val.get('Wq_en_IC') else 'FALLA ✗'}",
                f"2. Ley de Little (L = λ·W):  error {val.get('Little_L_valor', 0)*100:.2f}%  {'PASA ✓' if val.get('Little_L') else 'FALLA ✗'}",
                f"3. Ley de Little (Lq = λ·Wq):  error {val.get('Little_Lq_valor', 0)*100:.2f}%  {'PASA ✓' if val.get('Little_Lq') else 'FALLA ✗'}",
                f"4. |ρ_sim - λ/μ| < 0.02:  {val.get('rho_diff', 0):.4f}  {'PASA ✓' if val.get('rho_precision') else 'FALLA ✗'}",
            ]
            for line in val_lines:
                ttk.Label(f_val, text=line, font=("Courier", 10)).pack(anchor="w")

        # PRNGs
        f_prng = ttk.LabelFrame(scrollable, text="  Generadores Pseudoaleatorios  ", padding=8)
        f_prng.pack(fill="x", padx=10, pady=(5, 10))

        prng_lines = [
            "Tiempo entre llegadas  →  Mersenne Twister (MT19937)  │  Matsumoto y Nishimura (1998)",
            "Tiempo de servicio     →  MRG/FMRG (k=2)             │  Deng y Lin (2000)",
            "Duración de vacación   →  LCG multiplicativo          │  Deng y Lin (2000)",
        ]
        for line in prng_lines:
            ttk.Label(f_prng, text=line, font=("Courier", 10)).pack(anchor="w")

    def _run(self):
        try:
            lam = float(self.var_lam.get())
            mu = float(self.var_mu.get())
            theta = float(self.var_theta.get())
            t_sim = float(self.var_tsim.get())
            t_warmup = float(self.var_twarm.get())
            s_mt = int(self.var_s_mt.get())
            s_lcg = int(self.var_s_lcg.get())
            s_mrg1 = int(self.var_s_mrg1.get())
            s_mrg2 = int(self.var_s_mrg2.get())
        except ValueError:
            messagebox.showerror("Error", "Verifique que todos los parámetros sean numéricos.")
            return

        analitico = calcular_analitico(lam, mu, theta)
        if not analitico["estable"]:
            if not messagebox.askyesno("Advertencia",
                    f"ρ = {analitico['rho']:.4f} ≥ 1 — el sistema es inestable.\n"
                    "¿Desea continuar de todos modos?"):
                return

        run_replicas = self.var_replicas.get()
        self.btn_run.config(state="disabled")
        self.var_status.set("Ejecutando simulación..." +
                           (" (10 réplicas)" if run_replicas else ""))
        self.root.update()

        def worker():
            sim = simular(lam, mu, theta, t_sim, s_mt, s_lcg, s_mrg1, s_mrg2,
                          t_warmup, trace_eventos=20)

            replicas_result = None
            if run_replicas:
                replicas_result = ejecutar_replicas(lam, mu, theta, t_sim, t_warmup,
                                                   n_replicas=10, base_seed=42,
                                                   trace_eventos=20)

            seeds = {"mt": s_mt, "lcg": s_lcg, "mrg1": s_mrg1, "mrg2": s_mrg2}
            reporte = generar_reporte_texto(sim, analitico, lam, mu, theta,
                                           t_sim, t_warmup, seeds, replicas_result)

            self.root.after(0, lambda: self._on_complete(
                sim, analitico, lam, mu, theta, reporte, replicas_result))

        threading.Thread(target=worker, daemon=True).start()

    def _on_complete(self, sim, analitico, lam, mu, theta, reporte, replicas_result):
        self._populate_resumen(sim, analitico, lam, mu, theta, replicas_result)

        self.txt_detalles.config(state="normal")
        self.txt_detalles.delete("1.0", "end")
        self.txt_detalles.insert("1.0", reporte)
        self.txt_detalles.config(state="disabled")

        self.btn_run.config(state="normal")
        self.var_status.set(
            f"Simulación completada — {sim['clientes_servidos']:,} clientes servidos, "
            f"error promedio: {self._avg_error(sim, analitico):.2f}%"
            + (f" | Réplicas: todas las validaciones pasaron" if replicas_result and
               all(replicas_result["validacion"].get(k, False)
                   for k in ["Wq_en_IC", "Little_L", "Little_Lq", "rho_precision"])
               else "")
        )
        self.notebook.select(self.tab_resumen)

    def _avg_error(self, sim, analitico):
        errores = []
        for s_val, a_val in [
            (sim["rho"], analitico["rho"]),
            (sim["L"], analitico["L"]),
            (sim["Lq"], analitico["Lq"]),
            (sim["W"], analitico["W"]),
            (sim["Wq"], analitico["Wq"]),
        ]:
            if a_val != 0 and math.isfinite(a_val):
                errores.append(abs(s_val - a_val) / a_val * 100)
        return sum(errores) / len(errores) if errores else 0


# ============================================================================
# Punto de entrada
# ============================================================================

if __name__ == "__main__":
    root = tk.Tk()
    app = SimulacionApp(root)
    root.mainloop()
