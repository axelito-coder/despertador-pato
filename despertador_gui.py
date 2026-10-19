"""Despertador Pato — interfaz gráfica (Tkinter, sin dependencias externas).

Abrilo con doble clic en "Despertador.pyw" o con:  py despertador_gui.py
"""

import os
import threading
import tkinter as tk
import webbrowser
from datetime import datetime, timedelta
from tkinter import messagebox, ttk

from nucleo import (ARCHIVO_URLS, DIAS_CORTOS, Alarma, cargar_config, cargar_urls,
                    elegir_video, es_url_youtube, guardar_config, guardar_urls,
                    hay_internet, sonido_de_respaldo, texto_cuando, texto_falta,
                    texto_fecha)

C = {
    "fondo": "#16171F",
    "panel": "#1E202B",
    "tarjeta": "#262937",
    "tarjeta_hover": "#30344A",
    "borde": "#3A3D52",
    "texto": "#F1F1F5",
    "suave": "#A0A3B8",
    "tenue": "#5E6178",
    "acento": "#FFC93C",        # amarillo pato
    "acento_hover": "#FFD86B",
    "acento_texto": "#1A1A1A",
    "naranja": "#FF9F43",
    "peligro": "#FF6B6B",
    "oscuro": "#1A1A1A",
}
FUENTE = "Segoe UI"
TOLERANCIA = timedelta(hours=1)   # si la PC estuvo suspendida, suena igual si pasó menos de esto
ESCALA = 1.0


def px(n):
    """Convierte píxeles de diseño a píxeles reales según el DPI de la pantalla."""
    return int(round(n * ESCALA))


def sin_aviso(_mensaje):
    pass


# ------------------------------------------------------------ componentes

ESTILOS_BOTON = {
    "acento": ("acento", "acento_hover", "acento_texto"),
    "secundario": ("tarjeta", "tarjeta_hover", "texto"),
    "peligro": ("tarjeta", "tarjeta_hover", "peligro"),
}


class Boton(tk.Label):
    """Botón plano con efecto al pasar el mouse."""

    def __init__(self, padre, texto, comando, estilo="acento", tam=11,
                 padx=18, pady=9, fondo=None, hover=None, color=None):
        base, sobre, frente = ESTILOS_BOTON.get(estilo, ESTILOS_BOTON["secundario"])
        self._base = fondo or C[base]
        self._sobre = hover or C[sobre]
        super().__init__(padre, text=texto, bg=self._base, fg=color or C[frente],
                         font=(FUENTE, tam, "bold"), padx=px(padx), pady=px(pady),
                         cursor="hand2")
        self._comando = comando
        self.bind("<Enter>", lambda e: self.configure(bg=self._sobre))
        self.bind("<Leave>", lambda e: self.configure(bg=self._base))
        self.bind("<ButtonRelease-1>", self._click)

    def _click(self, evento):
        # Solo cuenta si se suelta el botón del mouse encima.
        if 0 <= evento.x < self.winfo_width() and 0 <= evento.y < self.winfo_height():
            self._comando()


def boton_fantasma(padre, texto, comando, fondo, color=None, tam=9):
    return Boton(padre, texto, comando, fondo=fondo, hover=C["tarjeta_hover"],
                 color=color or C["suave"], tam=tam, padx=8, pady=3)


class Interruptor(tk.Canvas):
    """Interruptor encendido/apagado estilo celular."""

    def __init__(self, padre, valor, al_cambiar, fondo):
        self.ancho, self.alto = px(46), px(26)
        super().__init__(padre, width=self.ancho, height=self.alto, bg=fondo,
                         highlightthickness=0, bd=0, cursor="hand2")
        self.valor = valor
        self.al_cambiar = al_cambiar
        self.bind("<Button-1>", self._alternar)
        self._dibujar()

    def _alternar(self, _evento):
        self.valor = not self.valor
        self._dibujar()
        self.al_cambiar(self.valor)

    def _dibujar(self):
        self.delete("all")
        a, h = self.ancho, self.alto
        pista = C["acento"] if self.valor else C["borde"]
        self.create_oval(0, 0, h, h, fill=pista, outline="")
        self.create_oval(a - h, 0, a, h, fill=pista, outline="")
        self.create_rectangle(h // 2, 0, a - h // 2, h, fill=pista, outline="")
        m = px(4)
        x = a - h if self.valor else 0
        perilla = C["oscuro"] if self.valor else "#C9CBD8"
        self.create_oval(x + m, m, x + h - m, h - m, fill=perilla, outline="")


class ListaDesplazable(tk.Frame):
    """Contenedor con scroll vertical (rueda del mouse y barra que aparece si hace falta)."""

    def __init__(self, padre, fondo):
        super().__init__(padre, bg=fondo)
        self.lienzo = tk.Canvas(self, bg=fondo, highlightthickness=0, bd=0)
        self.barra = ttk.Scrollbar(self, orient="vertical", command=self.lienzo.yview,
                                   style="Pato.Vertical.TScrollbar")
        self.interior = tk.Frame(self.lienzo, bg=fondo)
        self._ventana = self.lienzo.create_window((0, 0), window=self.interior, anchor="nw")
        self.lienzo.configure(yscrollcommand=self.barra.set)
        self.lienzo.pack(side="left", fill="both", expand=True)

        self.interior.bind("<Configure>", self._ajustar)
        self.lienzo.bind("<Configure>", self._ajustar_ancho)
        self.bind("<Enter>", lambda e: self.bind_all("<MouseWheel>", self._rueda))
        self.bind("<Leave>", lambda e: self.unbind_all("<MouseWheel>"))

    def _sobra_contenido(self):
        return self.interior.winfo_reqheight() > self.lienzo.winfo_height()

    def _ajustar(self, _evento=None):
        self.lienzo.configure(scrollregion=self.lienzo.bbox("all"))
        if self._sobra_contenido():
            self.barra.pack(side="right", fill="y", padx=(px(6), 0))
        else:
            self.barra.pack_forget()
            self.lienzo.yview_moveto(0)

    def _ajustar_ancho(self, evento):
        self.lienzo.itemconfigure(self._ventana, width=evento.width)
        self._ajustar()

    def _rueda(self, evento):
        if self._sobra_contenido():
            self.lienzo.yview_scroll(int(-evento.delta / 120), "units")


def centrar(ventana, sobre=None):
    ventana.update_idletasks()
    ancho, alto = ventana.winfo_reqwidth(), ventana.winfo_reqheight()
    if sobre is not None and sobre.winfo_viewable():
        x = sobre.winfo_rootx() + (sobre.winfo_width() - ancho) // 2
        y = sobre.winfo_rooty() + (sobre.winfo_height() - alto) // 3
    else:
        x = (ventana.winfo_screenwidth() - ancho) // 2
        y = (ventana.winfo_screenheight() - alto) // 3
    ventana.geometry(f"+{max(0, x)}+{max(0, y)}")


# ------------------------------------------------------- diálogo de alarma

class DialogoAlarma(tk.Toplevel):
    """Ventana para crear o editar una alarma. Deja el resultado en self.resultado."""

    def __init__(self, raiz, alarma=None):
        super().__init__(raiz)
        self.alarma = alarma
        self.resultado = None
        base = alarma or Alarma(hora=7, minuto=0, dias=list(range(5)))
        self.dias = set(base.dias)

        titulo = "Editar alarma" if alarma else "Nueva alarma"
        self.title(titulo)
        self.configure(bg=C["panel"], padx=px(26), pady=px(22))
        self.resizable(False, False)
        self.transient(raiz)

        tk.Label(self, text=titulo, font=(FUENTE, 15, "bold"), fg=C["texto"],
                 bg=C["panel"]).pack(anchor="w")

        fila_hora = tk.Frame(self, bg=C["panel"])
        fila_hora.pack(pady=px(18))
        self.var_hora = tk.StringVar()
        self.var_minuto = tk.StringVar()
        self.spin_hora = self._selector(fila_hora, self.var_hora, 23, base.hora)
        self.spin_hora.pack(side="left")
        tk.Label(fila_hora, text=":", font=(FUENTE, 36, "bold"), fg=C["suave"],
                 bg=C["panel"]).pack(side="left", padx=px(6))
        self._selector(fila_hora, self.var_minuto, 59, base.minuto).pack(side="left")

        self._titulo_campo("Nombre (opcional)")
        caja = tk.Frame(self, bg=C["tarjeta"], padx=px(10))
        caja.pack(fill="x", pady=(px(4), px(16)))
        self.var_nombre = tk.StringVar(value=base.etiqueta)
        tk.Entry(caja, textvariable=self.var_nombre, bg=C["tarjeta"], fg=C["texto"],
                 insertbackground=C["texto"], relief="flat", bd=0,
                 font=(FUENTE, 11)).pack(fill="x", ipady=px(7))

        self._titulo_campo("Repetir")
        fila_dias = tk.Frame(self, bg=C["panel"])
        fila_dias.pack(anchor="w", pady=(px(6), px(8)))
        self.chips = []
        for i, letra in enumerate(DIAS_CORTOS):
            chip = tk.Label(fila_dias, text=letra, width=3, font=(FUENTE, 11, "bold"),
                            pady=px(7), cursor="hand2")
            chip.pack(side="left", padx=(0, px(6)))
            chip.bind("<Button-1>", lambda e, i=i: self._alternar_dia(i))
            self.chips.append(chip)

        atajos = tk.Frame(self, bg=C["panel"])
        atajos.pack(anchor="w")
        for texto, dias in (("Una vez", set()), ("Lun a Vie", set(range(5))),
                            ("Fin de semana", {5, 6}), ("Todos", set(range(7)))):
            boton_fantasma(atajos, texto, lambda d=dias: self._fijar_dias(d),
                           fondo=C["panel"]).pack(side="left", padx=(0, px(4)))

        self.lbl_resumen = tk.Label(self, font=(FUENTE, 9, "bold"), fg=C["acento"], bg=C["panel"])
        self.lbl_resumen.pack(anchor="w", pady=(px(10), 0))
        self.lbl_error = tk.Label(self, font=(FUENTE, 9), fg=C["peligro"], bg=C["panel"])
        self.lbl_error.pack(anchor="w")

        botones = tk.Frame(self, bg=C["panel"])
        botones.pack(fill="x", pady=(px(14), 0))
        Boton(botones, "Guardar", self.guardar).pack(side="right")
        Boton(botones, "Cancelar", self.destroy, estilo="secundario").pack(side="right", padx=(0, px(8)))

        self._pintar_dias()
        self.bind("<Return>", lambda e: self.guardar())
        self.bind("<Escape>", lambda e: self.destroy())
        centrar(self, raiz)
        self.grab_set()
        self.spin_hora.focus_set()

    def _titulo_campo(self, texto):
        tk.Label(self, text=texto.upper(), font=(FUENTE, 8, "bold"), fg=C["suave"],
                 bg=C["panel"]).pack(anchor="w")

    def _selector(self, padre, variable, maximo, valor):
        spin = tk.Spinbox(padre, from_=0, to=maximo, wrap=True, width=2, format="%02.0f",
                          textvariable=variable, font=(FUENTE, 36, "bold"), justify="center",
                          bg=C["tarjeta"], fg=C["texto"], buttonbackground=C["tarjeta"],
                          relief="flat", bd=0, highlightthickness=0, insertbackground=C["texto"])
        variable.set(f"{valor:02d}")
        spin.bind("<MouseWheel>",
                  lambda e: spin.invoke("buttonup" if e.delta > 0 else "buttondown"))
        return spin

    def _alternar_dia(self, dia):
        self.dias ^= {dia}
        self._pintar_dias()

    def _fijar_dias(self, dias):
        self.dias = set(dias)
        self._pintar_dias()

    def _pintar_dias(self):
        for i, chip in enumerate(self.chips):
            activo = i in self.dias
            chip.configure(bg=C["acento"] if activo else C["tarjeta"],
                           fg=C["acento_texto"] if activo else C["suave"])
        resumen = Alarma(0, 0, dias=sorted(self.dias)).texto_dias()
        self.lbl_resumen.configure(text=f"Suena: {resumen.lower() if self.dias else 'una sola vez'}")

    def guardar(self):
        try:
            hora, minuto = int(self.var_hora.get()), int(self.var_minuto.get())
        except ValueError:
            hora = minuto = -1
        if not (0 <= hora <= 23 and 0 <= minuto <= 59):
            self.lbl_error.configure(text="La hora no es válida (00:00 a 23:59).")
            return

        nombre = self.var_nombre.get().strip()[:40]
        dias = sorted(self.dias)
        if self.alarma:
            self.alarma.hora, self.alarma.minuto = hora, minuto
            self.alarma.etiqueta, self.alarma.dias = nombre, dias
            self.alarma.activa = True
            self.resultado = self.alarma
        else:
            self.resultado = Alarma(hora=hora, minuto=minuto, etiqueta=nombre, dias=dias)
        self.destroy()


# ------------------------------------------------------ ventana que suena

class VentanaAlarma(tk.Toplevel):
    """Pantalla que aparece al sonar: abre el video y ofrece posponer o apagar."""

    def __init__(self, app, alarma):
        super().__init__(app.raiz)
        self.app = app
        self.alarma = alarma
        self.detener = threading.Event()
        self.resultado = None          # lo completa el hilo de fondo
        self._mostrado = False
        self._fase = 0
        self._id_latir = self._id_revisar = None

        self.title("¡Arriba! — Despertador Pato")
        self.configure(bg=C["acento"])
        self.resizable(False, False)
        self.attributes("-topmost", True)
        self.protocol("WM_DELETE_WINDOW", self.apagar)

        cuerpo = tk.Frame(self, bg=C["acento"], padx=px(40), pady=px(34))
        cuerpo.pack(fill="both", expand=True)
        self._pintables = [cuerpo]

        def etiqueta(texto, tam, peso="bold", color=C["oscuro"], **kw):
            lbl = tk.Label(cuerpo, text=texto, font=(FUENTE, tam, peso), fg=color,
                           bg=C["acento"], **kw)
            lbl.pack()
            self._pintables.append(lbl)
            return lbl

        etiqueta("¡ARRIBA!", 40)
        self.lbl_hora = etiqueta(f"{datetime.now():%H:%M}", 24)
        etiqueta(alarma.etiqueta or "Hora de despertarse", 13, "normal")
        self.lbl_estado = etiqueta("Buscando un video…", 10, "normal", color="#4A3B00",
                                   wraplength=px(340), justify="center")
        self.lbl_estado.pack_configure(pady=(px(12), px(22)))

        botones = tk.Frame(cuerpo, bg=C["acento"])
        botones.pack(fill="x")
        self._pintables.append(botones)
        minutos = app.cfg.posponer_minutos
        Boton(botones, f"Posponer {minutos} min", self.posponer, fondo=C["oscuro"],
              hover="#33343F", color=C["acento"], tam=12, pady=12
              ).pack(side="left", fill="x", expand=True, padx=(0, px(6)))
        Boton(botones, "Apagar", self.apagar, fondo="#FFFFFF", hover="#F0F0F0",
              color=C["oscuro"], tam=12, pady=12
              ).pack(side="left", fill="x", expand=True, padx=(px(6), 0))

        centrar(self)
        self.lift()
        self.focus_force()
        self.bell()
        threading.Thread(target=self._sonar, daemon=True).start()
        self._latir()
        self._revisar()

    def _sonar(self):
        """Corre en segundo plano para no congelar la ventana mientras se
        comprueba internet y se abre el navegador."""
        urls = cargar_urls(avisar=sin_aviso)
        url = elegir_video(urls, list(self.app.cfg.historial))
        if url is None:
            self.resultado = ("respaldo", "No hay videos en la lista: suena la alarma de respaldo.")
        elif not hay_internet():
            self.resultado = ("respaldo", "Sin conexión a internet: suena la alarma de respaldo.")
        elif webbrowser.open(url):
            self.resultado = ("video", url)
            return
        else:
            self.resultado = ("respaldo", "No se pudo abrir el navegador: suena la alarma de respaldo.")
        sonido_de_respaldo(self.detener)

    def _revisar(self):
        if self.resultado and not self._mostrado:
            self._mostrado = True
            tipo, dato = self.resultado
            if tipo == "video":
                self.lbl_estado.configure(text=f"▶ Sonando en tu navegador\n{dato}")
                self.app.registrar_video(dato)
            else:
                self.lbl_estado.configure(text=dato)
        if not self._mostrado:
            self._id_revisar = self.after(200, self._revisar)

    def _latir(self):
        """Hace titilar el fondo entre amarillo y naranja."""
        self._fase ^= 1
        color = C["acento"] if self._fase else C["naranja"]
        for widget in self._pintables:
            widget.configure(bg=color)
        self.configure(bg=color)
        self.lbl_hora.configure(text=f"{datetime.now():%H:%M}")
        self._id_latir = self.after(700, self._latir)

    def posponer(self):
        self.app.posponer(self.alarma)
        self._cerrar()

    def apagar(self):
        self._cerrar()

    def _cerrar(self):
        self.detener.set()
        for pendiente in (self._id_latir, self._id_revisar):
            if pendiente:
                self.after_cancel(pendiente)
        self.destroy()
        self.app.alarma_cerrada()


# ------------------------------------------------------------ aplicación

class App:
    def __init__(self, raiz):
        self.raiz = raiz
        self.cfg = cargar_config()
        self.urls = cargar_urls(avisar=sin_aviso)
        self.proximas = {}        # id de alarma -> datetime en que suena
        self.pospuestas = []      # [(datetime, Alarma)]
        self.cola = []            # alarmas esperando para sonar
        self.ventana_sonando = None
        self._minuto = None

        self._estilos()
        self._armar_ventana()
        self.recalcular_proximas()
        self.dibujar_alarmas()
        self.dibujar_videos()
        self.mostrar_seccion("alarmas")
        self.tic()

    # ---------- armado

    def _estilos(self):
        estilo = ttk.Style(self.raiz)
        estilo.theme_use("clam")
        estilo.configure("Pato.Vertical.TScrollbar", background=C["borde"],
                         troughcolor=C["fondo"], bordercolor=C["fondo"],
                         lightcolor=C["borde"], darkcolor=C["borde"],
                         arrowcolor=C["suave"], gripcount=0, arrowsize=px(11))
        estilo.map("Pato.Vertical.TScrollbar", background=[("active", C["tenue"])])

    def _armar_ventana(self):
        r = self.raiz
        r.title("Despertador Pato")
        r.configure(bg=C["fondo"])
        r.geometry(f"{px(500)}x{px(740)}")
        r.minsize(px(420), px(600))
        r.protocol("WM_DELETE_WINDOW", self.al_cerrar)
        r.iconphoto(True, icono_pato())

        cab = tk.Frame(r, bg=C["fondo"])
        cab.pack(fill="x", padx=px(28), pady=(px(22), px(6)))
        tk.Label(cab, text="DESPERTADOR PATO", font=(FUENTE, 9, "bold"), fg=C["acento"],
                 bg=C["fondo"]).pack(anchor="w")
        fila = tk.Frame(cab, bg=C["fondo"])
        fila.pack(anchor="w")
        self.lbl_reloj = tk.Label(fila, font=(FUENTE, 58, "bold"), fg=C["texto"], bg=C["fondo"])
        self.lbl_reloj.pack(side="left")
        self.lbl_segundos = tk.Label(fila, font=(FUENTE, 20, "bold"), fg=C["tenue"], bg=C["fondo"])
        self.lbl_segundos.pack(side="left", anchor="s", pady=(0, px(18)), padx=(px(4), 0))
        self.lbl_fecha = tk.Label(cab, font=(FUENTE, 12), fg=C["suave"], bg=C["fondo"])
        self.lbl_fecha.pack(anchor="w")
        pastilla = tk.Frame(cab, bg=C["panel"], padx=px(14), pady=px(8))
        pastilla.pack(anchor="w", pady=(px(14), 0))
        self.lbl_proxima = tk.Label(pastilla, font=(FUENTE, 10, "bold"), bg=C["panel"])
        self.lbl_proxima.pack()

        fila_pestanas = tk.Frame(r, bg=C["fondo"])
        fila_pestanas.pack(fill="x", padx=px(28), pady=(px(16), 0))
        self.pestanas = {}
        for clave, texto in (("alarmas", "Alarmas"), ("videos", "Videos")):
            caja = tk.Frame(fila_pestanas, bg=C["fondo"])
            caja.pack(side="left", padx=(0, px(24)))
            lbl = tk.Label(caja, text=texto, font=(FUENTE, 12, "bold"), bg=C["fondo"], cursor="hand2")
            lbl.pack()
            linea = tk.Frame(caja, height=px(3), bg=C["fondo"])
            linea.pack(fill="x", pady=(px(4), 0))
            lbl.bind("<Button-1>", lambda e, c=clave: self.mostrar_seccion(c))
            self.pestanas[clave] = (lbl, linea)
        tk.Frame(r, bg=C["borde"], height=1).pack(fill="x", padx=px(28))

        contenido = tk.Frame(r, bg=C["fondo"])
        contenido.pack(fill="both", expand=True, padx=px(28), pady=(px(16), px(22)))
        self.secciones = {
            "alarmas": self._seccion_alarmas(contenido),
            "videos": self._seccion_videos(contenido),
        }

    def _seccion_alarmas(self, padre):
        sec = tk.Frame(padre, bg=C["fondo"])

        pie = tk.Frame(sec, bg=C["fondo"])
        pie.pack(side="bottom", fill="x", pady=(px(12), 0))
        Boton(pie, "+   Nueva alarma", self.nueva_alarma, tam=12, pady=12).pack(fill="x")
        ajustes = tk.Frame(pie, bg=C["fondo"])
        ajustes.pack(fill="x", pady=(px(12), 0))
        tk.Label(ajustes, text="Posponer", font=(FUENTE, 10), fg=C["suave"],
                 bg=C["fondo"]).pack(side="left")
        self.var_posponer = tk.StringVar(value=str(self.cfg.posponer_minutos))
        tk.Spinbox(ajustes, from_=1, to=60, width=3, textvariable=self.var_posponer,
                   font=(FUENTE, 10, "bold"), bg=C["tarjeta"], fg=C["texto"],
                   buttonbackground=C["tarjeta"], relief="flat", bd=0, justify="center",
                   insertbackground=C["texto"], highlightthickness=0
                   ).pack(side="left", padx=px(8), ipady=px(3))
        self.var_posponer.set(str(self.cfg.posponer_minutos))
        self.var_posponer.trace_add("write", self._cambio_posponer)
        tk.Label(ajustes, text="min", font=(FUENTE, 10), fg=C["suave"],
                 bg=C["fondo"]).pack(side="left")
        boton_fantasma(ajustes, "▶  Probar alarma", self.probar_alarma,
                       fondo=C["fondo"], tam=10).pack(side="right")

        self.lista_alarmas = ListaDesplazable(sec, C["fondo"])
        self.lista_alarmas.pack(fill="both", expand=True)
        return sec

    def _seccion_videos(self, padre):
        sec = tk.Frame(padre, bg=C["fondo"])

        self.lbl_cant_videos = tk.Label(sec, font=(FUENTE, 13, "bold"), fg=C["texto"], bg=C["fondo"])
        self.lbl_cant_videos.pack(anchor="w")
        tk.Label(sec, text="Cuando suena una alarma se abre uno al azar. "
                           "Los últimos que sonaron no se repiten enseguida.",
                 font=(FUENTE, 9), fg=C["suave"], bg=C["fondo"], justify="left",
                 wraplength=px(420)).pack(anchor="w", pady=(px(2), px(12)))

        fila = tk.Frame(sec, bg=C["fondo"])
        fila.pack(fill="x")
        caja = tk.Frame(fila, bg=C["tarjeta"], padx=px(10))
        caja.pack(side="left", fill="both", expand=True, padx=(0, px(8)))
        self.entrada_url = tk.Entry(caja, bg=C["tarjeta"], fg=C["texto"], relief="flat", bd=0,
                                    insertbackground=C["texto"], font=(FUENTE, 10))
        self.entrada_url.pack(fill="both", expand=True, ipady=px(8))
        self.entrada_url.bind("<Return>", lambda e: self.agregar_video())
        self.entrada_url.bind("<FocusIn>", lambda e: self._quitar_sugerencia())
        self.entrada_url.bind("<FocusOut>", lambda e: self._poner_sugerencia())
        self._con_sugerencia = False
        self._poner_sugerencia()
        Boton(fila, "Agregar", self.agregar_video, tam=10, padx=14, pady=8).pack(side="right")

        self.lbl_error_video = tk.Label(sec, font=(FUENTE, 9), fg=C["peligro"], bg=C["fondo"])
        self.lbl_error_video.pack(anchor="w", pady=px(4))

        acciones = tk.Frame(sec, bg=C["fondo"])
        acciones.pack(side="bottom", fill="x", pady=(px(10), 0))
        Boton(acciones, "▶  Abrir", self.abrir_video, estilo="secundario",
              tam=10, padx=12, pady=6).pack(side="left")
        Boton(acciones, "Quitar", self.quitar_video, estilo="peligro",
              tam=10, padx=12, pady=6).pack(side="left", padx=px(8))
        if hasattr(os, "startfile"):
            boton_fantasma(acciones, "Abrir urls.txt", lambda: os.startfile(ARCHIVO_URLS),
                           fondo=C["fondo"]).pack(side="right")

        marco = tk.Frame(sec, bg=C["tarjeta"], padx=px(6), pady=px(6))
        marco.pack(fill="both", expand=True)
        barra = ttk.Scrollbar(marco, orient="vertical", style="Pato.Vertical.TScrollbar")
        self.lista_videos = tk.Listbox(marco, bg=C["tarjeta"], fg=C["texto"],
                                       selectbackground=C["acento"],
                                       selectforeground=C["acento_texto"],
                                       font=(FUENTE, 10), relief="flat", bd=0,
                                       highlightthickness=0, activestyle="none",
                                       yscrollcommand=barra.set)
        barra.configure(command=self.lista_videos.yview)
        barra.pack(side="right", fill="y")
        self.lista_videos.pack(side="left", fill="both", expand=True)
        self.lista_videos.bind("<Double-Button-1>", lambda e: self.abrir_video())
        self.lista_videos.bind("<Delete>", lambda e: self.quitar_video())
        return sec

    def mostrar_seccion(self, clave):
        for nombre, seccion in self.secciones.items():
            lbl, linea = self.pestanas[nombre]
            activa = nombre == clave
            lbl.configure(fg=C["texto"] if activa else C["tenue"])
            linea.configure(bg=C["acento"] if activa else C["fondo"])
            if activa:
                seccion.pack(fill="both", expand=True)
            else:
                seccion.pack_forget()
        if clave == "videos":
            # Por si editaste urls.txt a mano mientras el programa estaba abierto.
            self.urls = cargar_urls(avisar=sin_aviso)
            self.dibujar_videos()

    # ---------- alarmas

    def recalcular_proximas(self):
        ahora = datetime.now()
        self.proximas = {a.id: a.proxima(ahora) for a in self.cfg.alarmas if a.activa}

    def dibujar_alarmas(self):
        interior = self.lista_alarmas.interior
        for widget in interior.winfo_children():
            widget.destroy()

        alarmas = sorted(self.cfg.alarmas, key=lambda a: (a.hora, a.minuto))
        if not alarmas:
            vacio = tk.Frame(interior, bg=C["fondo"])
            vacio.pack(fill="x", pady=px(40))
            tk.Label(vacio, text="☀", font=(FUENTE, 40), fg=C["tenue"], bg=C["fondo"]).pack()
            tk.Label(vacio, text="No hay alarmas todavía", font=(FUENTE, 13, "bold"),
                     fg=C["suave"], bg=C["fondo"]).pack(pady=(px(6), 0))
            tk.Label(vacio, text="Creá la primera con «Nueva alarma».", font=(FUENTE, 10),
                     fg=C["tenue"], bg=C["fondo"]).pack()
            return

        ahora = datetime.now()
        for alarma in alarmas:
            self._tarjeta(interior, alarma, ahora)

    def _tarjeta(self, padre, alarma, ahora):
        fondo = C["tarjeta"]
        tarjeta = tk.Frame(padre, bg=fondo, padx=px(18), pady=px(14))
        tarjeta.pack(fill="x", pady=(0, px(10)))

        derecha = tk.Frame(tarjeta, bg=fondo)
        derecha.pack(side="right", anchor="n")
        Interruptor(derecha, alarma.activa, lambda v, a=alarma: self.activar(a, v),
                    fondo).pack(anchor="e", pady=(px(4), 0))
        acciones = tk.Frame(derecha, bg=fondo)
        acciones.pack(anchor="e", pady=(px(14), 0))
        boton_fantasma(acciones, "Editar", lambda a=alarma: self.editar_alarma(a),
                       fondo=fondo).pack(side="left")
        boton_fantasma(acciones, "Borrar", lambda a=alarma: self.borrar_alarma(a),
                       fondo=fondo, color=C["peligro"]).pack(side="left")

        izquierda = tk.Frame(tarjeta, bg=fondo)
        izquierda.pack(side="left", fill="x", expand=True)
        tk.Label(izquierda, text=alarma.texto_hora, font=(FUENTE, 30, "bold"), bg=fondo,
                 fg=C["texto"] if alarma.activa else C["tenue"]).pack(anchor="w")
        nombre = alarma.etiqueta or "Alarma"
        if len(nombre) > 24:
            nombre = nombre[:23] + "…"
        tk.Label(izquierda, text=f"{nombre}  ·  {alarma.texto_dias()}", font=(FUENTE, 10),
                 fg=C["suave"], bg=fondo).pack(anchor="w")
        proxima = self.proximas.get(alarma.id) if alarma.activa else None
        if proxima:
            texto = f"Suena {texto_cuando(proxima, ahora)} · en {texto_falta(proxima, ahora)}"
            tk.Label(izquierda, text=texto, font=(FUENTE, 9, "bold"), fg=C["acento"],
                     bg=fondo).pack(anchor="w", pady=(px(4), 0))
        elif not alarma.activa:
            tk.Label(izquierda, text="Desactivada", font=(FUENTE, 9), fg=C["tenue"],
                     bg=fondo).pack(anchor="w", pady=(px(4), 0))

        for widget in (tarjeta, izquierda, *izquierda.winfo_children()):
            widget.bind("<Double-Button-1>", lambda e, a=alarma: self.editar_alarma(a))

    def _guardar_y_refrescar(self):
        guardar_config(self.cfg)
        self.recalcular_proximas()
        self.dibujar_alarmas()
        self.actualizar_proxima()

    def nueva_alarma(self):
        dialogo = DialogoAlarma(self.raiz)
        self.raiz.wait_window(dialogo)
        if dialogo.resultado:
            self.cfg.alarmas.append(dialogo.resultado)
            self._guardar_y_refrescar()

    def editar_alarma(self, alarma):
        dialogo = DialogoAlarma(self.raiz, alarma)
        self.raiz.wait_window(dialogo)
        if dialogo.resultado:
            self._guardar_y_refrescar()

    def borrar_alarma(self, alarma):
        if messagebox.askyesno("Borrar alarma",
                               f"¿Borrar la alarma de las {alarma.texto_hora}?", parent=self.raiz):
            self.cfg.alarmas = [a for a in self.cfg.alarmas if a.id != alarma.id]
            self._guardar_y_refrescar()

    def activar(self, alarma, valor):
        alarma.activa = valor
        # Se redibuja después del clic, no durante (el interruptor se destruye al redibujar).
        self.raiz.after_idle(self._guardar_y_refrescar)

    def _cambio_posponer(self, *_):
        try:
            minutos = int(self.var_posponer.get())
        except ValueError:
            return
        if 1 <= minutos <= 120 and minutos != self.cfg.posponer_minutos:
            self.cfg.posponer_minutos = minutos
            guardar_config(self.cfg)

    # ---------- reloj y disparo

    def tic(self):
        ahora = datetime.now()
        self.lbl_reloj.configure(text=f"{ahora:%H:%M}")
        self.lbl_segundos.configure(text=f"{ahora:%S}")
        self.lbl_fecha.configure(text=texto_fecha(ahora).capitalize())
        self.revisar_alarmas(ahora)
        if ahora.minute != self._minuto:
            # Una vez por minuto se actualiza el "en X min" de las tarjetas.
            self._minuto = ahora.minute
            self.dibujar_alarmas()
        self.actualizar_proxima(ahora)
        self.raiz.after(max(50, 1000 - ahora.microsecond // 1000), self.tic)

    def revisar_alarmas(self, ahora):
        cambios = False
        for alarma in self.cfg.alarmas:
            cuando = self.proximas.get(alarma.id)
            if not alarma.activa or cuando is None or ahora < cuando:
                continue
            if ahora - cuando <= TOLERANCIA:
                self.cola.append(alarma)
            if alarma.dias:
                self.proximas[alarma.id] = alarma.proxima(ahora)
            else:
                alarma.activa = False      # las de "una vez" se apagan solas
                del self.proximas[alarma.id]
            cambios = True

        vencidas = [p for p in self.pospuestas if p[0] <= ahora]
        if vencidas:
            self.pospuestas = [p for p in self.pospuestas if p[0] > ahora]
            self.cola.extend(alarma for _, alarma in vencidas)

        if cambios:
            guardar_config(self.cfg)
            self.dibujar_alarmas()
        self.procesar_cola()

    def procesar_cola(self):
        if self.ventana_sonando is None and self.cola:
            alarma = self.cola.pop(0)
            # Si hay un diálogo modal abierto, se libera para poder tocar "Apagar".
            modal = self.raiz.grab_current()
            if modal is not None:
                modal.grab_release()
            if self.raiz.state() == "iconic":
                self.raiz.deiconify()
            self.ventana_sonando = VentanaAlarma(self, alarma)

    def alarma_cerrada(self):
        self.ventana_sonando = None
        self.actualizar_proxima()
        self.raiz.after(500, self.procesar_cola)

    def posponer(self, alarma):
        cuando = datetime.now() + timedelta(minutes=self.cfg.posponer_minutos)
        self.pospuestas.append((cuando, alarma))

    def probar_alarma(self):
        self.cola.append(Alarma(hora=0, minuto=0, etiqueta="Alarma de prueba"))
        self.procesar_cola()

    def registrar_video(self, url):
        self.cfg.registrar_video(url)
        guardar_config(self.cfg)

    def actualizar_proxima(self, ahora=None):
        ahora = ahora or datetime.now()
        candidatas = [(p, False) for p in self.proximas.values() if p]
        candidatas += [(p, True) for p, _ in self.pospuestas]
        if not candidatas:
            self.lbl_proxima.configure(text="Sin alarmas activas", fg=C["suave"])
            return
        cuando, pospuesta = min(candidatas, key=lambda c: c[0])
        prefijo = "Pospuesta hasta" if pospuesta else "Próxima:"
        self.lbl_proxima.configure(
            fg=C["texto"],
            text=f"⏰  {prefijo} {texto_cuando(cuando, ahora)}   ·   en {texto_falta(cuando, ahora)}")

    # ---------- videos

    def _poner_sugerencia(self):
        if not self.entrada_url.get():
            self._con_sugerencia = True
            self.entrada_url.configure(fg=C["tenue"])
            self.entrada_url.insert(0, "Pegá un link de YouTube…")

    def _quitar_sugerencia(self):
        if self._con_sugerencia:
            self._con_sugerencia = False
            self.entrada_url.delete(0, "end")
            self.entrada_url.configure(fg=C["texto"])

    def dibujar_videos(self):
        self.lista_videos.delete(0, "end")
        for url in self.urls:
            self.lista_videos.insert("end", f"  {url}")
        cantidad = len(self.urls)
        self.lbl_cant_videos.configure(
            text=f"{cantidad} video{'s' if cantidad != 1 else ''} en la lista" if cantidad
            else "La lista está vacía")

    def agregar_video(self):
        url = "" if self._con_sugerencia else self.entrada_url.get().strip()
        if not es_url_youtube(url):
            self.lbl_error_video.configure(text="Eso no parece un link de YouTube (youtube.com o youtu.be).")
            return
        urls = cargar_urls(avisar=sin_aviso)
        if url in urls:
            self.lbl_error_video.configure(text="Ese video ya está en la lista.")
            return
        urls.append(url)
        guardar_urls(urls)
        self.urls = urls
        self.lbl_error_video.configure(text="")
        self.entrada_url.delete(0, "end")
        self.dibujar_videos()
        self.lista_videos.see("end")

    def _video_elegido(self):
        seleccion = self.lista_videos.curselection()
        if not seleccion:
            self.lbl_error_video.configure(text="Primero elegí un video de la lista.")
            return None
        self.lbl_error_video.configure(text="")
        return self.urls[seleccion[0]]

    def abrir_video(self):
        url = self._video_elegido()
        if url:
            webbrowser.open(url)

    def quitar_video(self):
        url = self._video_elegido()
        if not url:
            return
        urls = [u for u in cargar_urls(avisar=sin_aviso) if u != url]
        guardar_urls(urls)
        self.urls = urls
        self.dibujar_videos()

    # ---------- cierre

    def al_cerrar(self):
        hay_pendientes = any(a.activa for a in self.cfg.alarmas) or self.pospuestas
        if hay_pendientes:
            respuesta = messagebox.askyesnocancel(
                "Despertador Pato",
                "Si cerrás el programa, las alarmas no van a sonar.\n\n"
                "¿Querés minimizarlo en lugar de cerrarlo?",
                parent=self.raiz)
            if respuesta is None:
                return
            if respuesta:
                self.raiz.iconify()
                return
        self.raiz.destroy()


def icono_pato(tam=32):
    """Dibuja un patito simple para el ícono de la ventana."""
    img = tk.PhotoImage(width=tam, height=tam)
    centro, radio = tam / 2 - 1, tam / 2 - 2
    for y in range(tam):
        for x in range(tam):
            dx, dy = x - centro, y - centro
            if dx * dx + dy * dy <= radio * radio:
                img.put(C["acento"], (x, y))
    for y in range(tam // 2 - 2, tam // 2 + 3):          # pico
        for x in range(tam - 6, tam):
            if abs(y - tam // 2) <= (tam - x) // 2:
                img.put(C["naranja"], (x, y))
    for y in range(tam // 3 - 2, tam // 3 + 2):          # ojo
        for x in range(tam // 2 + 3, tam // 2 + 7):
            img.put(C["oscuro"], (x, y))
    return img


def activar_dpi():
    """Texto nítido en pantallas con escala (125 %, 150 %...) en Windows."""
    try:
        import ctypes
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except (AttributeError, OSError):
        pass


def main():
    global ESCALA
    activar_dpi()
    raiz = tk.Tk()
    ESCALA = raiz.winfo_fpixels("1i") / 96
    App(raiz)
    raiz.mainloop()


if __name__ == "__main__":
    main()
