"""Prueba la interfaz simulando clics reales (necesita una pantalla)."""
import sys
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import tkinter as tk  # noqa: E402

import despertador_gui as g  # noqa: E402
import nucleo  # noqa: E402


def clic(widget):
    widget.update_idletasks()
    widget.event_generate("<ButtonPress-1>", x=5, y=5)
    widget.event_generate("<ButtonRelease-1>", x=5, y=5)


def buscar(padre, clase, texto=None):
    for hijo in padre.winfo_children():
        if isinstance(hijo, clase) and (texto is None or hijo.cget("text") == texto):
            return hijo
        encontrado = buscar(hijo, clase, texto)
        if encontrado:
            return encontrado
    return None


class TestNuevaAlarma(unittest.TestCase):
    def setUp(self):
        try:
            self.raiz = tk.Tk()
        except tk.TclError:
            self.skipTest("no hay pantalla disponible")
        carpeta = Path(tempfile.mkdtemp())
        self.parches = [
            mock.patch.object(g, "cargar_config", lambda: nucleo.Config()),
            mock.patch.object(g, "cargar_urls", lambda avisar=None: ["https://youtu.be/a"]),
            mock.patch.object(g, "hay_internet", lambda: True),
            mock.patch.object(g.webbrowser, "open", lambda url: True),
            mock.patch.object(g, "CARPETA_DATOS", carpeta),
        ]
        for parche in self.parches:
            parche.start()

    def tearDown(self):
        for parche in self.parches:
            parche.stop()
        self.raiz.destroy()

    def crear_alarma_con_clics(self, app, cuando):
        self.raiz.update()   # los botones necesitan tener tamaño real para recibir el clic
        def completar():
            dialogo = next(w for w in self.raiz.winfo_children() if isinstance(w, g.DialogoAlarma))
            dialogo.var_hora.set(f"{cuando.hour:02d}")
            dialogo.var_minuto.set(f"{cuando.minute:02d}")
            dialogo._fijar_dias(set())
            clic(buscar(dialogo, g.Boton, "Guardar"))
        self.raiz.after(300, completar)
        clic(buscar(self.raiz, g.Boton, "+   Nueva alarma"))

    def comprobar_programada_y_suena(self, app, cuando):
        self.assertEqual(len(app.cfg.alarmas), 1)
        alarma = app.cfg.alarmas[0]
        # Aparece en la lista y queda programada en el momento, sin esperar.
        self.assertEqual(len(app.lista_alarmas.interior.winfo_children()), 1)
        self.assertEqual(app.proximas[alarma.id], cuando.replace(second=0, microsecond=0))
        # Y suena al llegar la hora.
        app.revisar_alarmas(app.proximas[alarma.id] + timedelta(seconds=1))
        self.assertIsNotNone(app.ventana_sonando)
        app.ventana_sonando.apagar()

    def test_nueva_alarma_se_programa_al_guardar(self):
        guardados = []
        with mock.patch.object(g, "guardar_config", lambda cfg: guardados.append(cfg)):
            app = g.App(self.raiz)
            cuando = datetime.now() + timedelta(minutes=3)
            self.crear_alarma_con_clics(app, cuando)
            self.comprobar_programada_y_suena(app, cuando)
        self.assertTrue(guardados)
        self.assertFalse(app.lbl_aviso.winfo_ismapped())

    def test_carpeta_sin_permiso_no_impide_que_suene(self):
        def sin_permiso(cfg):
            raise PermissionError(13, "Acceso denegado")
        with mock.patch.object(g, "guardar_config", sin_permiso):
            app = g.App(self.raiz)
            cuando = datetime.now() + timedelta(minutes=3)
            self.crear_alarma_con_clics(app, cuando)
            self.comprobar_programada_y_suena(app, cuando)
            self.raiz.update()
            self.assertTrue(app.lbl_aviso.winfo_ismapped())
            self.assertIn("No se pudieron guardar", app.lbl_aviso.cget("text"))


if __name__ == "__main__":
    unittest.main()
