# 🦆 Despertador Pato

Reloj despertador de línea de comando: a la hora que elijas abre en tu navegador un video **al azar** de YouTube, sacado de una lista en `urls.txt`.

Prototipo para PC. Solo usa la biblioteca estándar de Python (3.8+), así que no hace falta instalar nada.

## Uso

```bash
py despertador.py 07:30        # suena a las 07:30 (si esa hora ya pasó, suena mañana)
py despertador.py --en 10      # suena dentro de 10 minutos
py despertador.py --en 0.1     # suena en ~6 segundos (para probar)
py despertador.py 07:30 --archivo otra_lista.txt
```

> En Windows usá `py`. En Linux/macOS usá `python3`.

Mientras espera, muestra una cuenta regresiva. Para cancelar, apretá `Ctrl+C`.

## La lista de videos (`urls.txt`)

Va una URL por línea. Las líneas vacías y las que empiezan con `#` se ignoran:

```
# Canciones para arrancar el día
https://www.youtube.com/watch?v=IcrbM1l_BoI
https://youtu.be/HgzGwKwLmgM
```

Se aceptan links de `youtube.com`, `youtu.be`, `m.youtube.com` y `music.youtube.com`. Las líneas que no son de YouTube se ignoran y se avisa cuáles fueron.

El archivo se vuelve a leer al momento de sonar, así que podés editarlo mientras la alarma espera.

## Sonido de respaldo

Si no hay videos válidos, si no hay internet o si no se puede abrir el navegador, suena un beep insistente para que igual te despiertes.

## Limitaciones conocidas

- La terminal tiene que quedar abierta y la PC despierta. Si la PC está suspendida a la hora de la alarma, va a sonar cuando se despierte.
- Algunos navegadores bloquean la reproducción automática con sonido. Si el video abre pausado, permití el autoplay para youtube.com en la configuración del navegador.
