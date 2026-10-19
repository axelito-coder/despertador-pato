import io
import sys
import tempfile
from contextlib import redirect_stderr
import unittest
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import despertador  # noqa: E402
from nucleo import (Alarma, Config, cargar_config, cargar_urls, elegir_video,  # noqa: E402
                    guardar_config, guardar_urls, texto_cuando, texto_falta)

# 19/10/2026 es lunes
LUNES_8AM = datetime(2026, 10, 19, 8, 0)


class TestAlarma(unittest.TestCase):
    def test_una_vez_hoy_o_manana(self):
        self.assertEqual(Alarma(9, 15).proxima(LUNES_8AM), datetime(2026, 10, 19, 9, 15))
        self.assertEqual(Alarma(7, 30).proxima(LUNES_8AM), datetime(2026, 10, 20, 7, 30))
        # A la hora exacta ya cuenta como pasada.
        self.assertEqual(Alarma(8, 0).proxima(LUNES_8AM), datetime(2026, 10, 20, 8, 0))

    def test_dias_de_la_semana(self):
        fin_de_semana = Alarma(10, 0, dias=[5, 6])
        self.assertEqual(fin_de_semana.proxima(LUNES_8AM), datetime(2026, 10, 24, 10, 0))
        lun_a_vie = Alarma(7, 0, dias=list(range(5)))
        viernes_noche = datetime(2026, 10, 23, 22, 0)
        self.assertEqual(lun_a_vie.proxima(viernes_noche), datetime(2026, 10, 26, 7, 0))
        solo_lunes = Alarma(7, 0, dias=[0])
        self.assertEqual(solo_lunes.proxima(LUNES_8AM), datetime(2026, 10, 26, 7, 0))

    def test_texto_dias(self):
        self.assertEqual(Alarma(7, 0).texto_dias(), "Una vez")
        self.assertEqual(Alarma(7, 0, dias=list(range(7))).texto_dias(), "Todos los días")
        self.assertEqual(Alarma(7, 0, dias=[0, 1, 2, 3, 4]).texto_dias(), "Lunes a viernes")
        self.assertEqual(Alarma(7, 0, dias=[6, 5]).texto_dias(), "Fin de semana")
        self.assertEqual(Alarma(7, 0, dias=[0, 2]).texto_dias(), "Lun · Mié")


class TestConfig(unittest.TestCase):
    def test_guardar_y_cargar(self):
        with tempfile.TemporaryDirectory() as carpeta:
            ruta = Path(carpeta) / "alarmas.json"
            config = Config(alarmas=[Alarma(6, 45, "Facu", [0, 3], activa=False)],
                            posponer_minutos=10)
            config.registrar_video("https://youtu.be/a")
            guardar_config(config, ruta)
            leida = cargar_config(ruta)
            self.assertEqual(leida, config)

    def test_archivo_roto_o_inexistente(self):
        with tempfile.TemporaryDirectory() as carpeta:
            ruta = Path(carpeta) / "alarmas.json"
            self.assertEqual(cargar_config(ruta), Config())
            ruta.write_text("{esto no es json", encoding="utf-8")
            self.assertEqual(cargar_config(ruta), Config())
            ruta.write_text('{"alarmas": [{"hora": 7, "minuto": 0}, {"sin": "hora"}]}', encoding="utf-8")
            self.assertEqual(len(cargar_config(ruta).alarmas), 1)

    def test_historial_limitado(self):
        config = Config()
        for i in range(30):
            config.registrar_video(f"https://youtu.be/{i}")
        self.assertEqual(len(config.historial), 20)
        self.assertEqual(config.historial[-1], "https://youtu.be/29")


class TestVideos(unittest.TestCase):
    def test_cargar_filtra_lineas(self):
        with tempfile.TemporaryDirectory() as carpeta:
            ruta = Path(carpeta) / "urls.txt"
            ruta.write_text("# comentario\n\nhttps://youtu.be/abc\nhola\n"
                            "https://evil.com/youtube.com\nhttps://music.youtube.com/watch?v=x\n",
                            encoding="utf-8")
            avisos = []
            self.assertEqual(cargar_urls(ruta, avisar=avisos.append),
                             ["https://youtu.be/abc", "https://music.youtube.com/watch?v=x"])
            self.assertEqual(len(avisos), 2)
            self.assertEqual(cargar_urls(Path(carpeta) / "no.txt", avisar=avisos.append), [])

    def test_guardar_urls(self):
        with tempfile.TemporaryDirectory() as carpeta:
            ruta = Path(carpeta) / "urls.txt"
            guardar_urls(["https://youtu.be/a", "https://youtu.be/b"], ruta)
            self.assertEqual(cargar_urls(ruta), ["https://youtu.be/a", "https://youtu.be/b"])

    def test_no_repite_recientes(self):
        urls = ["a", "b", "c", "d"]
        for _ in range(200):
            self.assertIn(elegir_video(urls, historial=["a", "b", "c"]), ["d"])

    def test_pocos_videos(self):
        self.assertIsNone(elegir_video([]))
        self.assertEqual(elegir_video(["a"], historial=["a"]), "a")
        for _ in range(50):
            self.assertEqual(elegir_video(["a", "b"], historial=["a"]), "b")


class TestTextos(unittest.TestCase):
    def test_cuando_y_falta(self):
        self.assertEqual(texto_cuando(datetime(2026, 10, 19, 9, 0), LUNES_8AM), "hoy 09:00")
        self.assertEqual(texto_cuando(datetime(2026, 10, 20, 7, 0), LUNES_8AM), "mañana 07:00")
        self.assertEqual(texto_cuando(datetime(2026, 10, 23, 7, 0), LUNES_8AM), "vie 07:00")
        self.assertEqual(texto_falta(datetime(2026, 10, 19, 9, 30), LUNES_8AM), "1 h 30 min")
        self.assertEqual(texto_falta(datetime(2026, 10, 19, 8, 0, 30), LUNES_8AM), "menos de 1 min")


class TestTerminal(unittest.TestCase):
    def test_hora_pasada_es_manana(self):
        self.assertEqual(despertador.calcular_hora_alarma("07:30", ahora=LUNES_8AM),
                         datetime(2026, 10, 20, 7, 30))

    def test_preguntar_posponer(self):
        self.assertTrue(despertador.preguntar_posponer(5, entrada=lambda _: "p"))
        self.assertFalse(despertador.preguntar_posponer(5, entrada=lambda _: ""))

    def test_argumentos_invalidos(self):
        for args in ([], ["25:00"], ["07:30", "--en", "5"], ["--en", "-1"]):
            with self.assertRaises(SystemExit), redirect_stderr(io.StringIO()):
                despertador.main(args)


if __name__ == "__main__":
    unittest.main()
