"""Genera los íconos y el sonido de alarma de la versión móvil.

Solo usa la biblioteca estándar (sin Pillow): dibuja el patito píxel por píxel
con antialiasing y escribe los PNG a mano. Ejecutar desde la carpeta movil/:

    py herramientas/generar_recursos.py
"""

import math
import struct
import wave
import zlib
from pathlib import Path

MOVIL = Path(__file__).resolve().parent.parent
WEB = MOVIL / "www" / "iconos"
RES = MOVIL / "android" / "app" / "src" / "main" / "res"

FONDO = (0x16, 0x17, 0x1F)
AMARILLO = (0xFF, 0xC9, 0x3C)
NARANJA = (0xFF, 0x9F, 0x43)
OSCURO = (0x1A, 0x1A, 0x1A)
BLANCO = (0xFF, 0xFF, 0xFF)


# ------------------------------------------------------------------- PNG

def escribir_png(ruta, ancho, alto, pixeles):
    """pixeles: bytes RGBA fila por fila."""
    def bloque(tipo, datos):
        return (struct.pack(">I", len(datos)) + tipo + datos
                + struct.pack(">I", zlib.crc32(tipo + datos) & 0xFFFFFFFF))

    filas = b"".join(b"\x00" + pixeles[y * ancho * 4:(y + 1) * ancho * 4] for y in range(alto))
    png = (b"\x89PNG\r\n\x1a\n"
           + bloque(b"IHDR", struct.pack(">IIBBBBB", ancho, alto, 8, 6, 0, 0, 0))
           + bloque(b"IDAT", zlib.compress(filas, 9))
           + bloque(b"IEND", b""))
    ruta.parent.mkdir(parents=True, exist_ok=True)
    ruta.write_bytes(png)


# ---------------------------------------------------------------- dibujo

def capas_pato(x, y):
    """Qué parte del pato hay en (x, y), en coordenadas 0..1 del pato."""
    if (x - 0.56) ** 2 + (y - 0.40) ** 2 <= 0.05 ** 2:
        return "ojo"
    if (x - 0.44) ** 2 + (y - 0.52) ** 2 <= 0.33 ** 2:
        return "cabeza"
    # pico: elipse aplastada a la derecha
    if ((x - 0.80) / 0.17) ** 2 + ((y - 0.56) / 0.085) ** 2 <= 1:
        return "pico"
    return None


def dibujar(tam, escala=1.0, fondo=None, mono=False, muestras=4):
    """fondo: None (transparente), 'cuadrado' o 'circulo'. mono: silueta blanca."""
    pix = bytearray(tam * tam * 4)
    paso = 1 / muestras
    for py in range(tam):
        for px in range(tam):
            r = g = b = a = 0.0
            for sy in range(muestras):
                for sx in range(muestras):
                    u = (px + (sx + 0.5) * paso) / tam
                    v = (py + (sy + 0.5) * paso) / tam
                    color, alfa = None, 0.0
                    if fondo == "cuadrado" or (fondo == "circulo" and (u - 0.5) ** 2 + (v - 0.5) ** 2 <= 0.25):
                        color, alfa = FONDO, 1.0
                    parte = capas_pato((u - 0.5) / escala + 0.5, (v - 0.5) / escala + 0.5)
                    if mono:
                        color, alfa = (BLANCO, 1.0) if parte in ("cabeza", "pico") else (None, 0.0)
                    elif parte:
                        color, alfa = {"cabeza": AMARILLO, "pico": NARANJA, "ojo": OSCURO}[parte], 1.0
                    if alfa:
                        r += color[0]; g += color[1]; b += color[2]; a += 1
            i = (py * tam + px) * 4
            if a:
                pix[i:i + 4] = bytes((round(r / a), round(g / a), round(b / a), round(255 * a / muestras ** 2)))
    return bytes(pix)


def icono(ruta, tam, **opciones):
    escribir_png(ruta, tam, tam, dibujar(tam, **opciones))
    print("  ", ruta.relative_to(MOVIL))


# ----------------------------------------------------------------- sonido

def generar_alarma(ruta, segundos=20, muestreo=22050):
    """Ráfagas de dos tonos que van subiendo de volumen."""
    datos = bytearray()
    for n in range(segundos * muestreo):
        t = n / muestreo
        en_ciclo = t % 1.6                       # 4 pitidos de 0,2 s y una pausa
        valor = 0.0
        if en_ciclo < 1.0 and (en_ciclo % 0.25) < 0.18:
            frec = 1175 if int(en_ciclo / 0.25) % 2 else 880
            local = en_ciclo % 0.25
            envolvente = min(1, local / 0.01, (0.18 - local) / 0.02)
            valor = envolvente * (math.sin(2 * math.pi * frec * t) + 0.3 * math.sin(4 * math.pi * frec * t)) / 1.3
        volumen = 0.35 + 0.55 * min(1, t / 8)    # de suave a fuerte en 8 segundos
        datos += struct.pack("<h", int(valor * volumen * 32000))
    ruta.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(ruta), "wb") as archivo:
        archivo.setnchannels(1)
        archivo.setsampwidth(2)
        archivo.setframerate(muestreo)
        archivo.writeframes(bytes(datos))
    print("  ", ruta.relative_to(MOVIL))


def main():
    print("Íconos de la app web:")
    icono(WEB / "icono-180.png", 180, escala=0.80, fondo="cuadrado")
    icono(WEB / "icono-192.png", 192, escala=0.80, fondo="cuadrado")
    icono(WEB / "icono-512.png", 512, escala=0.80, fondo="cuadrado", muestras=2)
    icono(WEB / "icono-mascara-512.png", 512, escala=0.62, fondo="cuadrado", muestras=2)

    if not RES.exists():
        print("No existe movil/android: corré 'npx cap add android' y volvé a ejecutar este script.")
        return

    print("Íconos de Android:")
    densidades = {"mdpi": 1, "hdpi": 1.5, "xhdpi": 2, "xxhdpi": 3, "xxxhdpi": 4}
    for nombre, factor in densidades.items():
        lanzador = round(48 * factor)
        icono(RES / f"mipmap-{nombre}" / "ic_launcher.png", lanzador, escala=0.78, fondo="circulo")
        icono(RES / f"mipmap-{nombre}" / "ic_launcher_round.png", lanzador, escala=0.78, fondo="circulo")
        icono(RES / f"mipmap-{nombre}" / "ic_launcher_foreground.png", round(108 * factor), escala=0.55)
        icono(RES / f"drawable-{nombre}" / "ic_stat_pato.png", round(24 * factor), escala=0.95, mono=True)

    fondo = RES / "values" / "ic_launcher_background.xml"
    fondo.write_text('<?xml version="1.0" encoding="utf-8"?>\n<resources>\n'
                     '    <color name="ic_launcher_background">#16171F</color>\n</resources>\n',
                     encoding="utf-8")
    print("  ", fondo.relative_to(MOVIL))

    print("Sonido de alarma:")
    generar_alarma(RES / "raw" / "alarma.wav")


if __name__ == "__main__":
    main()
