"""Despertador Pato (versión terminal): a la hora indicada abre un video al azar de YouTube.

Uso:
    py despertador.py 07:30          # suena a las 07:30 (si ya pasó, mañana)
    py despertador.py --en 10        # suena dentro de 10 minutos
    py despertador.py 07:30 --archivo mis_videos.txt --posponer 10

Para la interfaz gráfica, abrí "Despertador.pyw" o ejecutá: py despertador_gui.py
"""

import argparse
import sys
import time
import webbrowser
from datetime import datetime, timedelta

from nucleo import (ARCHIVO_URLS, cargar_config, cargar_urls, elegir_video,
                    guardar_config, hay_internet, sonido_de_respaldo)


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

    config = cargar_config()
    url = elegir_video(urls, config.historial)
    print(f"▶ Reproduciendo: {url}")
    if webbrowser.open(url):
        config.registrar_video(url)
        guardar_config(config)
    else:
        print("No se pudo abrir el navegador: usando sonido de respaldo.")
        sonido_de_respaldo()


def preguntar_posponer(minutos, entrada=input):
    """Devuelve True si el usuario quiere posponer la alarma."""
    try:
        respuesta = entrada(f"Enter = apagar · p + Enter = posponer {minutos} min: ")
    except EOFError:
        return False
    return respuesta.strip().lower() in ("p", "posponer")


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


def main(argv=None, entrada=input):
    parser = argparse.ArgumentParser(
        description="Despertador que abre un video al azar de YouTube.")
    parser.add_argument("hora", nargs="?", type=hora_valida,
                        help="hora de la alarma en formato HH:MM (24 h)")
    parser.add_argument("--en", type=minutos_validos, metavar="MINUTOS",
                        help="hacer sonar la alarma dentro de N minutos (acepta decimales)")
    parser.add_argument("--archivo", default=ARCHIVO_URLS,
                        help="archivo con las URLs de YouTube (por defecto: urls.txt)")
    parser.add_argument("--posponer", type=minutos_validos, default=5, metavar="MINUTOS",
                        help="minutos que se pospone la alarma (por defecto: 5)")
    args = parser.parse_args(argv)

    if (args.hora is None) == (args.en is None):
        parser.error("indicá una hora (ej. 07:30) o --en MINUTOS, pero no ambas")

    urls = cargar_urls(args.archivo)
    if urls:
        print(f"📼 {len(urls)} video(s) cargado(s) de {args.archivo}")
    else:
        print("⚠ No hay videos cargados: cuando suene se usará el sonido de respaldo.")

    objetivo = calcular_hora_alarma(args.hora, args.en)
    while True:
        print(f"Alarma programada para el {objetivo:%d/%m a las %H:%M:%S}")
        try:
            esperar_hasta(objetivo)
        except KeyboardInterrupt:
            print("\nAlarma cancelada.")
            return 1

        # Se relee el archivo por si lo editaste mientras esperaba.
        sonar(cargar_urls(args.archivo) or urls)
        if not preguntar_posponer(f"{args.posponer:g}", entrada):
            print("Alarma apagada. ¡Buen día!")
            return 0
        objetivo = datetime.now() + timedelta(minutes=args.posponer)


if __name__ == "__main__":
    for flujo in (sys.stdout, sys.stderr):
        if hasattr(flujo, "reconfigure"):
            flujo.reconfigure(encoding="utf-8")
    sys.exit(main())
