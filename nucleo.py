"""Lógica compartida del Despertador Pato (terminal e interfaz gráfica)."""

import json
import os
import random
import socket
import time
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta
from datetime import time as hora_del_dia
from pathlib import Path
from urllib.parse import urlparse

CARPETA = Path(__file__).resolve().parent
ARCHIVO_URLS = CARPETA / "urls.txt"
ARCHIVO_CONFIG = CARPETA / "alarmas.json"

DOMINIOS_YOUTUBE = {"youtube.com", "www.youtube.com", "m.youtube.com",
                    "music.youtube.com", "youtu.be"}

# Índices iguales a datetime.weekday(): 0 = lunes ... 6 = domingo
DIAS_CORTOS = ["L", "M", "X", "J", "V", "S", "D"]
DIAS_ABREV = ["Lun", "Mar", "Mié", "Jue", "Vie", "Sáb", "Dom"]
DIAS_LARGOS = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio",
         "agosto", "septiembre", "octubre", "noviembre", "diciembre"]

ENCABEZADO_URLS = "# Una URL de YouTube por línea. Las líneas que empiezan con # se ignoran.\n"


# ---------------------------------------------------------------- videos

def es_url_youtube(url):
    partes = urlparse(url)
    return partes.scheme in ("http", "https") and partes.netloc.lower() in DOMINIOS_YOUTUBE


def cargar_urls(ruta=ARCHIVO_URLS, avisar=print):
    """Lee una URL por línea, ignorando líneas vacías y comentarios (#)."""
    try:
        lineas = Path(ruta).read_text(encoding="utf-8").splitlines()
    except FileNotFoundError:
        avisar(f"⚠ No se encontró el archivo de URLs: {ruta}")
        return []

    urls = []
    for numero, linea in enumerate(lineas, start=1):
        linea = linea.strip()
        if not linea or linea.startswith("#"):
            continue
        if es_url_youtube(linea):
            urls.append(linea)
        else:
            avisar(f"⚠ Línea {numero} ignorada (no es una URL de YouTube): {linea}")
    return urls


def guardar_urls(urls, ruta=ARCHIVO_URLS):
    Path(ruta).write_text(ENCABEZADO_URLS + "".join(u + "\n" for u in urls), encoding="utf-8")


def elegir_video(urls, historial=(), evitar=3):
    """Elige un video al azar evitando los últimos `evitar` que ya sonaron
    (siempre que queden otros para elegir)."""
    if not urls:
        return None
    evitar = min(evitar, len(set(urls)) - 1)
    recientes = set(historial[-evitar:]) if evitar > 0 else set()
    candidatos = [u for u in urls if u not in recientes] or urls
    return random.choice(candidatos)


def hay_internet(host="www.youtube.com", puerto=443, timeout=3):
    try:
        socket.create_connection((host, puerto), timeout=timeout).close()
        return True
    except OSError:
        return False


def sonido_de_respaldo(detener=None, repeticiones=10):
    """Beep insistente para cuando no se puede abrir YouTube.
    Si se pasa un threading.Event en `detener`, suena hasta que se active."""
    vueltas = 0
    while (detener is None and vueltas < repeticiones) or (detener is not None and not detener.is_set()):
        try:
            import winsound
            winsound.Beep(1000, 400)
        except ImportError:
            print("\a", end="", flush=True)
        vueltas += 1
        time.sleep(0.25)


# --------------------------------------------------------------- alarmas

@dataclass
class Alarma:
    hora: int
    minuto: int
    etiqueta: str = ""
    dias: list = field(default_factory=list)   # vacío = suena una sola vez
    activa: bool = True
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:8])

    @property
    def texto_hora(self):
        return f"{self.hora:02d}:{self.minuto:02d}"

    def texto_dias(self):
        dias = sorted(set(self.dias))
        if not dias:
            return "Una vez"
        if dias == list(range(7)):
            return "Todos los días"
        if dias == list(range(5)):
            return "Lunes a viernes"
        if dias == [5, 6]:
            return "Fin de semana"
        return " · ".join(DIAS_ABREV[d] for d in dias)

    def proxima(self, desde):
        """Próxima vez que debe sonar, estrictamente después de `desde`."""
        for i in range(8):
            dia = desde.date() + timedelta(days=i)
            candidato = datetime.combine(dia, hora_del_dia(self.hora, self.minuto))
            if candidato <= desde:
                continue
            if not self.dias or candidato.weekday() in self.dias:
                return candidato
        return None

    @classmethod
    def desde_dict(cls, datos):
        return cls(
            hora=int(datos["hora"]),
            minuto=int(datos["minuto"]),
            etiqueta=str(datos.get("etiqueta", "")),
            dias=sorted({int(d) for d in datos.get("dias", []) if 0 <= int(d) <= 6}),
            activa=bool(datos.get("activa", True)),
            id=str(datos.get("id") or uuid.uuid4().hex[:8]),
        )


@dataclass
class Config:
    alarmas: list = field(default_factory=list)
    posponer_minutos: int = 5
    historial: list = field(default_factory=list)   # últimos videos que sonaron

    def registrar_video(self, url, maximo=20):
        self.historial = (self.historial + [url])[-maximo:]


def cargar_config(ruta=ARCHIVO_CONFIG):
    try:
        datos = json.loads(Path(ruta).read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return Config()

    alarmas = []
    for item in datos.get("alarmas", []):
        try:
            alarmas.append(Alarma.desde_dict(item))
        except (KeyError, ValueError, TypeError):
            continue
    return Config(
        alarmas=alarmas,
        posponer_minutos=max(1, int(datos.get("posponer_minutos", 5))),
        historial=[u for u in datos.get("historial", []) if isinstance(u, str)],
    )


def guardar_config(config, ruta=ARCHIVO_CONFIG):
    """Guarda de forma atómica: si se corta la luz no queda el archivo a medias."""
    ruta = Path(ruta)
    datos = {
        "alarmas": [asdict(a) for a in config.alarmas],
        "posponer_minutos": config.posponer_minutos,
        "historial": config.historial,
    }
    temporal = ruta.with_suffix(".tmp")
    temporal.write_text(json.dumps(datos, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(temporal, ruta)


# ---------------------------------------------------------------- textos

def texto_fecha(momento):
    return f"{DIAS_LARGOS[momento.weekday()]} {momento.day} de {MESES[momento.month - 1]}"


def texto_cuando(objetivo, ahora):
    """'hoy 07:30', 'mañana 07:30' o 'vie 07:30'."""
    dias = (objetivo.date() - ahora.date()).days
    hora = f"{objetivo:%H:%M}"
    if dias == 0:
        return f"hoy {hora}"
    if dias == 1:
        return f"mañana {hora}"
    return f"{DIAS_ABREV[objetivo.weekday()].lower()} {hora}"


def texto_falta(objetivo, ahora):
    segundos = max(0, int((objetivo - ahora).total_seconds()))
    horas, resto = divmod(segundos, 3600)
    minutos = resto // 60
    if horas >= 24:
        return f"{horas // 24} d {horas % 24} h"
    if horas:
        return f"{horas} h {minutos} min"
    if minutos:
        return f"{minutos} min"
    return "menos de 1 min"
