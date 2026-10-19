"""Despertador Pato: a la hora indicada abre un video al azar de YouTube.

Uso:
    py despertador.py 07:30          # suena a las 07:30 (si ya pasó, mañana)
    py despertador.py --en 10        # suena dentro de 10 minutos
    py despertador.py 07:30 --archivo mis_videos.txt
"""

import argparse
import random
import socket
import sys
import time
import webbrowser
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import urlparse

ARCHIVO_POR_DEFECTO = Path(__file__).with_name("urls.txt")
DOMINIOS_YOUTUBE = {"youtube.com", "www.youtube.com", "m.youtube.com",
                    "music.youtube.com", "youtu.be"}


def es_url_youtube(url):
    partes = urlparse(url)
    return partes.scheme in ("http", "https") and partes.netloc.lower() in DOMINIOS_YOUTUBE


def cargar_urls(ruta):
    """Lee una URL por línea, ignorando líneas vacías y comentarios (#)."""
    try:
        lineas = Path(ruta).read_text(encoding="utf-8").splitlines()
    except FileNotFoundError:
        print(f"⚠ No se encontró el archivo de URLs: {ruta}")
        return []

    urls = []
    for numero, linea in enumerate(lineas, start=1):
        linea = linea.strip()
        if not linea or linea.startswith("#"):
            continue
        if es_url_youtube(linea):
            urls.append(linea)
        else:
            print(f"⚠ Línea {numero} ignorada (no es una URL de YouTube): {linea}")
    return urls


def calcular_hora_alarma(hora=None, minutos=None, ahora=None):
    """Devuelve el datetime en que debe sonar la alarma."""
    ahora = ahora or datetime.now()
    if minutos is not None:
        return ahora + timedelta(minutes=minutos)

    hora_alarma = datetime.strptime(hora, "%H:%M").time()
    objetivo = datetime.combine(ahora.date(), hora_alarma)
    if objetivo <= ahora:
        objetivo += timedelta(days=1)
    return objetivo


def hay_internet(host="www.youtube.com", puerto=443, timeout=3):
    try:
        socket.create_connection((host, puerto), timeout=timeout).close()
        return True
    except OSError:
        return False


def sonido_de_respaldo(repeticiones=10):
    """Beep insistente para cuando no se puede abrir YouTube."""
    try:
        import winsound
        for _ in range(repeticiones):
            winsound.Beep(1000, 400)
            time.sleep(0.2)
    except ImportError:
        for _ in range(repeticiones):
            print("\a", end="", flush=True)
            time.sleep(0.6)


def esperar_hasta(objetivo):
    """Cuenta regresiva en la terminal. Recalcula contra el reloj real en cada
    vuelta, así no se desfasa aunque la PC se suspenda un rato."""
    while True:
        restante = objetivo - datetime.now()
        segundos = int(restante.total_seconds())
        if segundos <= 0:
            break
        h, resto = divmod(segundos, 3600)
        m, s = divmod(resto, 60)
        print(f"\r⏰ Suena en {h:02d}:{m:02d}:{s:02d}  (Ctrl+C para cancelar) ", end="", flush=True)
        time.sleep(min(1, restante.total_seconds()))
    print()


def sonar(urls):
    print("🦆 ¡Arriba! ¡Hora de despertarse!")
    if not urls:
        print("No hay URLs válidas: usando sonido de respaldo.")
        sonido_de_respaldo()
        return
    if not hay_internet():
        print("Sin conexión a internet: usando sonido de respaldo.")
        sonido_de_respaldo()
        return

    url = random.choice(urls)
    print(f"▶ Reproduciendo: {url}")
    if not webbrowser.open(url):
        print("No se pudo abrir el navegador: usando sonido de respaldo.")
        sonido_de_respaldo()


def hora_valida(texto):
    try:
        datetime.strptime(texto, "%H:%M")
    except ValueError:
        raise argparse.ArgumentTypeError(f"'{texto}' no es una hora válida (formato HH:MM, ej. 07:30)")
    return texto


def minutos_validos(texto):
    try:
        valor = float(texto)
    except ValueError:
        raise argparse.ArgumentTypeError(f"'{texto}' no es un número de minutos")
    if valor < 0:
        raise argparse.ArgumentTypeError("los minutos no pueden ser negativos")
    return valor


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Despertador que abre un video al azar de YouTube.")
    parser.add_argument("hora", nargs="?", type=hora_valida,
                        help="hora de la alarma en formato HH:MM (24 h)")
    parser.add_argument("--en", type=minutos_validos, metavar="MINUTOS",
                        help="hacer sonar la alarma dentro de N minutos (acepta decimales)")
    parser.add_argument("--archivo", default=ARCHIVO_POR_DEFECTO,
                        help="archivo con las URLs de YouTube (por defecto: urls.txt)")
    args = parser.parse_args(argv)

    if (args.hora is None) == (args.en is None):
        parser.error("indicá una hora (ej. 07:30) o --en MINUTOS, pero no ambas")

    urls = cargar_urls(args.archivo)
    if urls:
        print(f"📼 {len(urls)} video(s) cargado(s) de {args.archivo}")
    else:
        print("⚠ No hay videos cargados: cuando suene se usará el sonido de respaldo.")

    objetivo = calcular_hora_alarma(args.hora, args.en)
    print(f"Alarma programada para el {objetivo:%d/%m a las %H:%M:%S}")

    try:
        esperar_hasta(objetivo)
    except KeyboardInterrupt:
        print("\nAlarma cancelada.")
        return 1

    # Se relee el archivo por si lo editaste mientras esperaba.
    sonar(cargar_urls(args.archivo) or urls)
    return 0


if __name__ == "__main__":
    for flujo in (sys.stdout, sys.stderr):
        if hasattr(flujo, "reconfigure"):
            flujo.reconfigure(encoding="utf-8")
    sys.exit(main())
