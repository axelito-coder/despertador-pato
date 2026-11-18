// Despertador Pato para celulares.
// El mismo código corre en dos modos:
//  - App Android (Capacitor): las alarmas son notificaciones programadas en el
//    sistema, así suenan aunque el celular esté bloqueado y la app cerrada.
//  - Navegador / iPhone (PWA): la app tiene que quedar abierta (modo mesita de
//    luz); suena con Web Audio y mantiene la pantalla prendida con Wake Lock.

import {
  DIAS_CORTOS, actualizarVencimientos, elegirVideo, esUrlYoutube, estadoInicial, idNotificacion,
  idVideo, normalizarEstado, nuevaAlarma, planificar, proxima, sonandoAhora, textoCuando,
  textoDias, textoFalta, textoFecha, textoHora,
} from './alarmas.js';

const CLAVE_ALMACEN = 'despertador-pato';
const REPETICIONES = 3;               // avisos por alarma en Android: a la hora, +1 y +2 min

const Cap = window.Capacitor;
const NATIVO = Boolean(Cap?.isNativePlatform?.());
const Notis = NATIVO ? Cap.Plugins.LocalNotifications : null;
const Lanzador = NATIVO ? Cap.Plugins.AppLauncher : null;
const AppNativa = NATIVO ? Cap.Plugins.App : null;

const $ = (selector) => document.querySelector(selector);
const dos = (n) => String(n).padStart(2, '0');
const horaDe = (fecha) => `${dos(fecha.getHours())}:${dos(fecha.getMinutes())}`;

function el(etiqueta, clase = '', texto = '') {
  const nodo = document.createElement(etiqueta);
  if (clase) nodo.className = clase;
  if (texto) nodo.textContent = texto;   // textContent: lo que escribe el usuario nunca se interpreta como HTML
  return nodo;
}

let estado = cargar();
let sonandoActual = null;   // {clave, alarmaId, etiqueta}
let alarmaEditada = null;   // null = alarma nueva
let diasEditor = new Set();
let ultimoMinuto = -1;

// ------------------------------------------------------------ almacenamiento

function cargar() {
  try {
    return normalizarEstado(JSON.parse(localStorage.getItem(CLAVE_ALMACEN)));
  } catch {
    return estadoInicial();
  }
}

function guardar() {
  try {
    localStorage.setItem(CLAVE_ALMACEN, JSON.stringify(estado));
    quitarAviso('guardar');
  } catch {
    mostrarAviso('guardar', 'No se pudieron guardar los cambios en este dispositivo.');
  }
}

/** Después de cualquier cambio: guardar, redibujar y volver a programar. */
function cambiar() {
  actualizarVencimientos(estado, new Date());
  guardar();
  dibujarAlarmas();
  actualizarProxima();
  avisoModoWeb();
  reprogramar();
}

// ------------------------------------------------------------ agenda (Android)

let colaProgramacion = Promise.resolve();

/** Cancela todo lo pendiente y vuelve a programar la agenda completa.
 *  Las llamadas se encadenan para que dos reprogramaciones no se pisen. */
function reprogramar() {
  if (!NATIVO) return Promise.resolve();
  colaProgramacion = colaProgramacion.then(programarNotificaciones).catch((error) => {
    console.error(error);
    mostrarAviso('programar', `No se pudieron programar las alarmas: ${error?.message || error}`);
  });
  return colaProgramacion;
}

async function programarNotificaciones() {
  const { notifications: pendientes } = await Notis.getPending();
  if (pendientes.length) await Notis.cancel({ notifications: pendientes.map((n) => ({ id: n.id })) });
  const avisos = planificar(estado, new Date(), { repeticiones: REPETICIONES });
  if (avisos.length) await Notis.schedule({ notifications: avisos.map(aNotificacion) });
  quitarAviso('programar');
}

function aNotificacion(v) {
  return {
    id: v.id,
    title: v.intento ? '¡Arriba! Sigue sonando' : '¡Arriba!',
    body: `${v.etiqueta || 'Alarma'} · ${horaDe(v.cuando)}. Tocá para despertarte con tu video.`,
    // Sin channelId: se usa el canal "default" del plugin, que toma el sonido de
    // capacitor.config.json y lo reproduce con el volumen de ALARMA (suena aunque
    // el celular esté en silencio). Un canal propio usaría el de notificaciones.
    actionTypeId: 'ALARMA',
    schedule: { at: v.en, allowWhileIdle: true },
    sound: 'alarma.wav',
    smallIcon: 'ic_stat_pato',
    iconColor: '#FFC93C',
    extra: { clave: v.clave, alarmaId: v.alarmaId, etiqueta: v.etiqueta },
  };
}

/** Marca una vez que sonó como atendida y saca sus avisos pendientes y visibles. */
async function atender(clave) {
  if (!estado.atendidas.includes(clave)) estado.atendidas = [...estado.atendidas, clave].slice(-100);
  estado.pospuestas = estado.pospuestas.filter((p) => p.clave !== clave);
  // Las alarmas de "una vez" se apagan solas en cuanto se atienden.
  const alarma = estado.alarmas.find((a) => clave.startsWith(`${a.id}@`));
  if (alarma && !alarma.dias.length) {
    alarma.activa = false;
    alarma.vence = null;
  }
  guardar();
  await silenciarAvisos(clave);
}

/** Saca los avisos pendientes y visibles de una vez que sonó (solo Android). */
async function silenciarAvisos(clave) {
  if (!NATIVO) return;
  const ids = Array.from({ length: REPETICIONES }, (_, i) => ({ id: idNotificacion(clave, i) }));
  await Notis.cancel({ notifications: ids }).catch(() => {});
  await Notis.removeDeliveredNotifications({ notifications: ids }).catch(() => {});
}

// ------------------------------------------------------------ sonido (navegador)

const sonido = (() => {
  let ctx = null;
  let intervalo = null;

  function desbloquear() {
    // Los navegadores solo dejan sonar audio después de que el usuario tocó la página.
    try {
      ctx ??= new (window.AudioContext || window.webkitAudioContext)();
      if (ctx.state === 'suspended') ctx.resume();
    } catch { /* sin Web Audio: queda la vibración y la pantalla */ }
  }

  function pitido(inicio, frecuencia) {
    const osc = ctx.createOscillator();
    const volumen = ctx.createGain();
    osc.type = 'square';
    osc.frequency.value = frecuencia;
    volumen.gain.setValueAtTime(0.0001, inicio);
    volumen.gain.exponentialRampToValueAtTime(0.25, inicio + 0.01);
    volumen.gain.exponentialRampToValueAtTime(0.0001, inicio + 0.18);
    osc.connect(volumen).connect(ctx.destination);
    osc.start(inicio);
    osc.stop(inicio + 0.2);
  }

  function rafaga() {
    if (!ctx) return;
    const t = ctx.currentTime + 0.05;
    [0, 0.25, 0.5, 0.75].forEach((d, i) => pitido(t + d, i % 2 ? 1320 : 990));
  }

  return {
    desbloquear,
    iniciar() { desbloquear(); clearInterval(intervalo); rafaga(); intervalo = setInterval(rafaga, 1600); },
    detener() { clearInterval(intervalo); intervalo = null; },
    probar() { desbloquear(); rafaga(); },
  };
})();

let bloqueoPantalla = null;
let mesitaPedida = false;

async function activarMesita() {
  sonido.probar();
  mesitaPedida = true;
  try {
    bloqueoPantalla = await navigator.wakeLock.request('screen');
    bloqueoPantalla.addEventListener('release', () => { bloqueoPantalla = null; actualizarAjustes(); avisoModoWeb(); });
    toast('Modo mesita activado: dejá esta pantalla abierta');
  } catch {
    toast('Este navegador no deja mantener la pantalla prendida: desactivá el bloqueo automático');
  }
  actualizarAjustes();
  avisoModoWeb();
}

document.addEventListener('visibilitychange', () => {
  // En Android se usa el evento 'resume' de Capacitor (ver iniciarNativo).
  if (NATIVO || document.visibilityState !== 'visible') return;
  if (mesitaPedida && !bloqueoPantalla) activarMesita();
  alVolver();
});

// ------------------------------------------------------------ cuando suena

// El despertador es el video: a la hora se reproduce en pantalla completa un
// video al azar de la lista. Si el navegador no deja que arranque con sonido
// (iPhone, o una página que nadie tocó), arranca sin sonido, suena el pitido de
// respaldo y un toque en "Tocá para escuchar" activa el sonido del video.

let reproductor = null;    // YT.Player
let videoActual = null;
let vigilancia = null;
let promesaYouTube = null;

/** Carga la API de YouTube (una sola vez, recién cuando hace falta). */
function cargarYouTube() {
  if (window.YT?.Player) return Promise.resolve(window.YT);
  promesaYouTube ??= new Promise((resolver, rechazar) => {
    const anterior = window.onYouTubeIframeAPIReady;
    window.onYouTubeIframeAPIReady = () => { anterior?.(); resolver(window.YT); };
    const script = document.createElement('script');
    script.src = 'https://www.youtube.com/iframe_api';
    script.onerror = () => rechazar(new Error('sin conexión'));
    document.head.append(script);
    setTimeout(() => rechazar(new Error('YouTube no respondió')), 12000);
  }).catch((error) => {
    promesaYouTube = null;
    throw error;
  });
  return promesaYouTube;
}

function mostrarSonando(vez) {
  if (sonandoActual) return;
  sonandoActual = { clave: vez.clave, alarmaId: vez.alarmaId, etiqueta: vez.etiqueta, fallidos: 0 };
  $('#sonando-info').textContent = `${horaDe(new Date())} · ${vez.etiqueta || 'Hora de despertarse'}`;
  $('#btn-posponer').textContent = `Posponer ${estado.posponerMin} min`;
  $('#sonando-respaldo').hidden = true;
  $('#btn-activar-sonido').hidden = true;
  $('#sonando').hidden = false;
  navigator.vibrate?.([700, 300, 700, 300, 700]);
  if (NATIVO) silenciarAvisos(vez.clave);   // ya suena en pantalla: no hacen falta más notificaciones
  reproducirVideo();
}

async function reproducirVideo(anterior = null) {
  const actual = sonandoActual;
  if (!actual) return;
  const conId = estado.videos.filter((u) => idVideo(u));
  const otros = conId.filter((u) => u !== anterior);
  const url = elegirVideo(otros.length ? otros : conId, estado.historial);
  if (!url) {
    sonarRespaldo('Tu lista de videos está vacía: agregá alguno en la pestaña Videos.');
    return;
  }
  try {
    await cargarYouTube();
  } catch {
    sonarRespaldo('Sin conexión: no se pudo cargar YouTube.');
    return;
  }
  if (sonandoActual !== actual) return;   // la apagaron mientras cargaba

  videoActual = url;
  estado.historial = [...estado.historial, url].slice(-20);
  guardar();
  if (reproductor) {
    reproductor.loadVideoById(idVideo(url));
    vigilarArranque();
    return;
  }
  const lugar = el('div');
  $('#marco-video').replaceChildren(lugar);
  reproductor = new window.YT.Player(lugar, {
    videoId: idVideo(url),
    width: '100%',
    height: '100%',
    playerVars: { autoplay: 1, playsinline: 1, rel: 0 },
    events: {
      onReady: (e) => {
        e.target.unMute();
        e.target.setVolume(100);
        e.target.playVideo();
        vigilarArranque();
      },
      onStateChange: alCambiarEstado,
      onError: videoFallido,
      onAutoplayBlocked: sinSonido,
    },
  });
}

function alCambiarEstado(evento) {
  const { PLAYING, ENDED } = window.YT.PlayerState;
  if (evento.data === PLAYING) {
    clearTimeout(vigilancia);
    if (evento.target.isMuted()) sinSonido();
    else conSonido();
  } else if (evento.data === ENDED) {
    reproducirVideo(videoActual);   // terminó y nadie la apagó: sigue con otro
  }
}

/** Si a los pocos segundos el video no arrancó, el navegador bloqueó el sonido. */
function vigilarArranque() {
  clearTimeout(vigilancia);
  vigilancia = setTimeout(() => {
    if (!sonandoActual || !reproductor?.getPlayerState) return;
    const estadoVideo = reproductor.getPlayerState();
    if (estadoVideo === window.YT.PlayerState.BUFFERING) vigilarArranque();   // internet lento: esperar más
    else if (estadoVideo !== window.YT.PlayerState.PLAYING) sinSonido();
  }, 4000);
}

function sinSonido() {
  if (!sonandoActual || !reproductor) return;
  reproductor.mute();
  reproductor.playVideo();
  sonido.iniciar();   // el pitido despierta hasta que actives el sonido del video
  $('#btn-activar-sonido').hidden = false;
}

function conSonido() {
  sonido.detener();
  $('#btn-activar-sonido').hidden = true;
}

function activarSonidoVideo() {
  if (!reproductor) return;
  reproductor.unMute();
  reproductor.setVolume(100);
  reproductor.playVideo();
  conSonido();
}

function videoFallido() {
  // Algunos videos no permiten verse fuera de YouTube: se prueba con otro.
  if (!sonandoActual) return;
  sonandoActual.fallidos += 1;
  if (sonandoActual.fallidos >= 4) sonarRespaldo('YouTube no dejó reproducir los videos de tu lista.');
  else reproducirVideo(videoActual);
}

function sonarRespaldo(motivo) {
  if (!sonandoActual) return;
  clearTimeout(vigilancia);
  $('#sonando-motivo').textContent = motivo;
  $('#sonando-respaldo').hidden = false;
  $('#btn-activar-sonido').hidden = true;
  sonido.iniciar();
}

function ocultarSonando() {
  $('#sonando').hidden = true;
  sonandoActual = null;
  videoActual = null;
  clearTimeout(vigilancia);
  sonido.detener();
  navigator.vibrate?.(0);
  if (reproductor) {
    try { reproductor.destroy(); } catch { /* ya no existe */ }
    reproductor = null;
  }
  $('#marco-video').replaceChildren();
}

async function apagar() {
  const actual = sonandoActual;
  ocultarSonando();
  if (actual) await atender(actual.clave);
  cambiar();
}

async function posponer() {
  const actual = sonandoActual;
  ocultarSonando();
  if (actual) await atender(actual.clave);
  const cuando = new Date(Date.now() + estado.posponerMin * 60000);
  estado.pospuestas.push({
    clave: `p-${cuando.getTime()}`,
    cuando: cuando.toISOString(),
    alarmaId: actual?.alarmaId ?? '',
    etiqueta: actual?.etiqueta ?? '',
  });
  cambiar();
  toast(`Pospuesta: vuelve a sonar a las ${horaDe(cuando)}`);
}

function probarAlarma() {
  const segundos = NATIVO ? 10 : 2;
  const cuando = new Date(Date.now() + segundos * 1000);
  estado.pospuestas.push({ clave: `p-${cuando.getTime()}`, cuando: cuando.toISOString(), alarmaId: '', etiqueta: 'Alarma de prueba' });
  cambiar();
  if (NATIVO) toast('Suena en 10 segundos: bloqueá el celular para ver cómo llega');
  else sonido.desbloquear();
}

// ------------------------------------------------------------ alarmas

function siguiente(alarma, ahora) {
  if (!alarma.activa) return null;
  if (alarma.dias.length) return proxima(alarma, ahora);
  const vence = alarma.vence ? new Date(alarma.vence) : null;
  return vence && vence > ahora ? vence : null;
}

function dibujarAlarmas() {
  const lista = $('#lista-alarmas');
  lista.replaceChildren();
  const ahora = new Date();
  const alarmas = [...estado.alarmas].sort((a, b) => a.hora - b.hora || a.minuto - b.minuto);

  if (!alarmas.length) {
    const vacio = el('div', 'vacio');
    vacio.append(el('div', 'sol', '☀'), el('strong', '', 'No hay alarmas todavía'),
      el('span', '', 'Creá la primera con «Nueva alarma».'));
    lista.append(vacio);
    return;
  }

  for (const a of alarmas) {
    const tarjeta = el('div', a.activa ? 'alarma' : 'alarma apagada');
    const info = el('button', 'alarma-info');
    info.type = 'button';
    info.setAttribute('aria-label', `Editar la alarma de las ${textoHora(a)}`);
    const p = siguiente(a, ahora);
    info.append(
      el('div', 'alarma-hora', textoHora(a)),
      el('div', 'alarma-detalle', `${a.etiqueta || 'Alarma'}  ·  ${textoDias(a.dias)}`),
      el('div', 'alarma-cuando', p ? `Suena ${textoCuando(p, ahora)} · en ${textoFalta(p, ahora)}` : 'Desactivada'),
    );
    info.addEventListener('click', () => abrirEditor(a));

    const interruptor = el('label', 'interruptor');
    const casilla = el('input');
    casilla.type = 'checkbox';
    casilla.checked = a.activa;
    casilla.setAttribute('aria-label', `Activar la alarma de las ${textoHora(a)}`);
    casilla.addEventListener('change', () => activar(a, casilla.checked));
    interruptor.append(casilla, el('span'));

    tarjeta.append(info, interruptor);
    lista.append(tarjeta);
  }
}

function fijarVencimiento(alarma) {
  alarma.vence = alarma.dias.length || !alarma.activa ? null : proxima(alarma, new Date()).toISOString();
}

function activar(alarma, valor) {
  alarma.activa = valor;
  fijarVencimiento(alarma);
  cambiar();
  if (valor) avisarCuando(alarma);
}

function avisarCuando(alarma) {
  const ahora = new Date();
  const p = siguiente(alarma, ahora);
  if (p) toast(`Suena ${textoCuando(p, ahora)}, en ${textoFalta(p, ahora)}`);
}

function actualizarProxima(ahora = new Date()) {
  const candidatas = estado.alarmas.map((a) => [siguiente(a, ahora), false])
    .concat(estado.pospuestas.map((p) => [new Date(p.cuando), true]))
    .filter(([cuando]) => cuando && cuando > ahora)
    .sort((x, y) => x[0] - y[0]);
  const pastilla = $('#proxima');
  if (!candidatas.length) {
    pastilla.textContent = 'Sin alarmas activas';
    pastilla.classList.add('vacia');
    return;
  }
  const [cuando, pospuesta] = candidatas[0];
  pastilla.classList.remove('vacia');
  pastilla.textContent = `⏰  ${pospuesta ? 'Pospuesta hasta' : 'Próxima:'} ${textoCuando(cuando, ahora)}  ·  en ${textoFalta(cuando, ahora)}`;
}

// ------------------------------------------------------------ editor

function abrirEditor(alarma = null) {
  alarmaEditada = alarma;
  const base = alarma ?? { hora: 7, minuto: 0, etiqueta: '', dias: [0, 1, 2, 3, 4] };
  $('#titulo-editor').textContent = alarma ? 'Editar alarma' : 'Nueva alarma';
  $('#campo-hora').value = `${dos(base.hora)}:${dos(base.minuto)}`;
  $('#campo-nombre').value = base.etiqueta;
  $('#btn-borrar').hidden = !alarma;
  diasEditor = new Set(base.dias);
  pintarDias();
  $('#editor').showModal();
}

function pintarDias() {
  $('#chips-dias').querySelectorAll('button').forEach((chip, i) => {
    chip.setAttribute('aria-pressed', String(diasEditor.has(i)));
  });
  const resumen = textoDias([...diasEditor]);
  $('#resumen-dias').textContent = `Suena: ${diasEditor.size ? resumen.toLowerCase() : 'una sola vez'}`;
}

function guardarEditor(evento) {
  evento.preventDefault();
  const [hora, minuto] = ($('#campo-hora').value || '').split(':').map(Number);
  if (!Number.isInteger(hora) || !Number.isInteger(minuto)) {
    toast('Elegí una hora válida');
    return;
  }
  const datos = {
    hora, minuto,
    etiqueta: $('#campo-nombre').value.trim().slice(0, 40),
    dias: [...diasEditor].sort((a, b) => a - b),
  };
  let alarma = alarmaEditada;
  if (alarma) {
    Object.assign(alarma, datos, { activa: true });
  } else {
    alarma = nuevaAlarma(datos);
    estado.alarmas.push(alarma);
  }
  fijarVencimiento(alarma);
  $('#editor').close();
  cambiar();
  avisarCuando(alarma);
}

function borrarEditada() {
  if (!alarmaEditada || !confirm(`¿Borrar la alarma de las ${textoHora(alarmaEditada)}?`)) return;
  estado.alarmas = estado.alarmas.filter((a) => a.id !== alarmaEditada.id);
  $('#editor').close();
  cambiar();
  toast('Alarma borrada');
}

// ------------------------------------------------------------ videos

function dibujarVideos() {
  const cantidad = estado.videos.length;
  $('#cant-videos').textContent = cantidad ? `${cantidad} video${cantidad === 1 ? '' : 's'} en la lista` : 'La lista está vacía';
  const lista = $('#lista-videos');
  lista.replaceChildren();
  estado.videos.forEach((url, i) => {
    const item = el('li', 'video');
    const id = idVideo(url);
    if (id) {
      const img = el('img');
      img.src = `https://i.ytimg.com/vi/${encodeURIComponent(id)}/mqdefault.jpg`;
      img.alt = '';
      img.loading = 'lazy';
      item.append(img);
    } else {
      item.append(el('div', 'sin-miniatura'));
    }
    const texto = el('div', 'video-texto');
    texto.append(el('strong', '', `Video ${i + 1}`), document.createTextNode(url));
    const abrir = el('button', 'icono-boton', '▶');
    abrir.type = 'button';
    abrir.setAttribute('aria-label', `Abrir el video ${i + 1}`);
    abrir.addEventListener('click', () => (NATIVO ? Lanzador.openUrl({ url }) : window.open(url, '_blank', 'noopener')));
    const quitar = el('button', 'icono-boton quitar', '✕');
    quitar.type = 'button';
    quitar.setAttribute('aria-label', `Quitar el video ${i + 1}`);
    quitar.addEventListener('click', () => {
      estado.videos = estado.videos.filter((u) => u !== url);
      guardar();
      dibujarVideos();
      toast('Video quitado');
    });
    item.append(texto, abrir, quitar);
    lista.append(item);
  });
}

function agregarVideo(evento) {
  evento.preventDefault();
  const entrada = $('#entrada-video');
  const url = entrada.value.trim();
  const error = $('#error-video');
  if (!esUrlYoutube(url)) {
    error.textContent = 'Eso no parece un link de YouTube (youtube.com o youtu.be).';
    return;
  }
  const id = idVideo(url);
  if (estado.videos.some((u) => u === url || (id && idVideo(u) === id))) {
    error.textContent = 'Ese video ya está en la lista.';
    return;
  }
  error.textContent = '';
  estado.videos.push(url);
  entrada.value = '';
  guardar();
  dibujarVideos();
  toast('Video agregado');
}

// ------------------------------------------------------------ ajustes y avisos

function mostrarAviso(clave, texto, boton, accion) {
  let aviso = document.querySelector(`[data-aviso="${clave}"]`);
  if (!aviso) {
    aviso = el('div', 'aviso');
    aviso.dataset.aviso = clave;
    $('#avisos').append(aviso);
  }
  aviso.replaceChildren(el('span', '', texto));
  if (boton) {
    const b = el('button', '', boton);
    b.type = 'button';
    b.addEventListener('click', accion);
    aviso.append(b);
  }
}

function quitarAviso(clave) {
  document.querySelector(`[data-aviso="${clave}"]`)?.remove();
}

function avisoModoWeb() {
  if (NATIVO) return;
  const hayActivas = estado.alarmas.some((a) => a.activa) || estado.pospuestas.length;
  if (hayActivas && !bloqueoPantalla) {
    mostrarAviso('web', 'En el navegador la alarma solo suena con esta pantalla abierta.', 'Modo mesita', activarMesita);
  } else {
    quitarAviso('web');
  }
}

function actualizarAjustes() {
  $('#posponer').value = String(estado.posponerMin);
  if (!NATIVO) {
    $('#btn-mesita').textContent = bloqueoPantalla ? 'Modo mesita activado ✓' : 'Activar modo mesita';
    $('#btn-mesita').disabled = Boolean(bloqueoPantalla);
  }
}

async function actualizarPermisos() {
  if (!NATIVO) return;
  const { display } = await Notis.checkPermissions();
  let exactas = 'granted';
  try {
    exactas = (await Notis.checkExactNotificationSetting()).exact_alarm;
  } catch { /* Android viejo: no hace falta */ }

  const notifOk = display === 'granted';
  $('#estado-notif').textContent = notifOk ? 'Permitidas ✓' : 'Bloqueadas: las alarmas no van a sonar';
  $('#btn-permiso-notif').hidden = notifOk;
  $('#estado-exactas').textContent = exactas === 'granted' ? 'Permitidas ✓' : 'Sin permiso: pueden sonar tarde';
  $('#btn-permiso-exactas').hidden = exactas === 'granted';

  if (!notifOk) {
    mostrarAviso('notif', 'Las notificaciones están bloqueadas: las alarmas no van a sonar.', 'Permitir', pedirNotificaciones);
  } else {
    quitarAviso('notif');
  }
  if (exactas !== 'granted') {
    mostrarAviso('exactas', 'Falta el permiso de alarmas exactas: pueden sonar tarde.', 'Revisar', pedirExactas);
  } else {
    quitarAviso('exactas');
  }
}

async function pedirNotificaciones() {
  const { display } = await Notis.requestPermissions();
  if (display !== 'granted') {
    toast('Activalas en Ajustes de Android → Apps → Despertador Pato → Notificaciones');
  }
  await actualizarPermisos();
  reprogramar();
}

async function pedirExactas() {
  try {
    await Notis.changeExactNotificationSetting();
  } catch { /* no disponible en esta versión de Android */ }
  await actualizarPermisos();
  reprogramar();
}

let temporizadorToast = null;
function toast(texto) {
  const caja = $('#toast');
  caja.textContent = texto;
  caja.hidden = false;
  clearTimeout(temporizadorToast);
  temporizadorToast = setTimeout(() => { caja.hidden = true; }, 3200);
}

// ------------------------------------------------------------ pestañas y reloj

function mostrarSeccion(nombre) {
  document.querySelectorAll('.pestanas button').forEach((b) => {
    b.setAttribute('aria-selected', String(b.dataset.seccion === nombre));
  });
  for (const s of ['alarmas', 'videos', 'ajustes']) $(`#sec-${s}`).hidden = s !== nombre;
  $('#btn-nueva').hidden = nombre !== 'alarmas';
  if (nombre === 'videos') dibujarVideos();
  if (nombre === 'ajustes') { actualizarAjustes(); actualizarPermisos(); }
}

function tic() {
  const ahora = new Date();
  $('#hora').textContent = horaDe(ahora);
  $('#segundos').textContent = dos(ahora.getSeconds());
  $('#fecha').textContent = textoFecha(ahora);
  if (ahora.getMinutes() !== ultimoMinuto) {
    ultimoMinuto = ahora.getMinutes();
    if (actualizarVencimientos(estado, ahora)) {
      guardar();
      reprogramar();
    }
    dibujarAlarmas();
  }
  actualizarProxima(ahora);
  if (!sonandoActual) {
    const [vez] = sonandoAhora(estado, ahora);
    if (vez) mostrarSonando(vez);
  }
  setTimeout(tic, 1005 - ahora.getMilliseconds());
}

/** Al volver a la app: releer (otra pestaña o una notificación pudo cambiar algo). */
function alVolver() {
  estado = cargar();
  if (actualizarVencimientos(estado, new Date())) guardar();
  dibujarAlarmas();
  actualizarProxima();
  if (NATIVO) { actualizarPermisos(); reprogramar(); }
}

// ------------------------------------------------------------ arranque

async function iniciarNativo() {
  await Notis.registerActionTypes({
    types: [{ id: 'ALARMA', actions: [{ id: 'posponer', title: 'Posponer' }, { id: 'apagar', title: 'Apagar' }] }],
  });
  await Notis.addListener('localNotificationActionPerformed', ({ actionId, notification }) => {
    const extra = notification?.extra || {};
    if (!extra.clave) return;
    if (estado.atendidas.includes(extra.clave)) {
      atender(extra.clave);   // aviso viejo: solo se limpia
      return;
    }
    const vez = { clave: extra.clave, alarmaId: extra.alarmaId, etiqueta: extra.etiqueta };
    ocultarSonando();
    if (actionId === 'posponer' || actionId === 'apagar') {
      sonandoActual = { ...vez, fallidos: 0 };
      if (actionId === 'posponer') posponer(); else apagar();
    } else {
      mostrarSonando(vez);   // tocar la notificación: abre la app y arranca el video
    }
  });
  await AppNativa.addListener('resume', alVolver);
  await AppNativa.addListener('backButton', () => {
    if ($('#editor').open) $('#editor').close();
    else if (!sonandoActual) AppNativa.minimizeApp();
  });

  const { display } = await Notis.checkPermissions();
  if (display !== 'granted') await Notis.requestPermissions().catch(() => {});
  await actualizarPermisos();
  await reprogramar();
}

function iniciar() {
  const chips = $('#chips-dias');
  DIAS_CORTOS.forEach((letra, i) => {
    const chip = el('button', '', letra);
    chip.type = 'button';
    chip.setAttribute('aria-label', ['lunes', 'martes', 'miércoles', 'jueves', 'viernes', 'sábado', 'domingo'][i]);
    chip.addEventListener('click', () => {
      if (diasEditor.has(i)) diasEditor.delete(i); else diasEditor.add(i);
      pintarDias();
    });
    chips.append(chip);
  });
  document.querySelectorAll('.atajos button').forEach((b) => {
    b.addEventListener('click', () => {
      diasEditor = new Set(b.dataset.dias ? b.dataset.dias.split(',').map(Number) : []);
      pintarDias();
    });
  });

  document.querySelectorAll('.pestanas button').forEach((b) => b.addEventListener('click', () => mostrarSeccion(b.dataset.seccion)));
  $('#btn-nueva').addEventListener('click', () => abrirEditor());
  $('#form-alarma').addEventListener('submit', guardarEditor);
  $('#btn-cancelar').addEventListener('click', () => $('#editor').close());
  $('#btn-borrar').addEventListener('click', borrarEditada);
  $('#form-video').addEventListener('submit', agregarVideo);
  $('#btn-apagar').addEventListener('click', apagar);
  $('#btn-posponer').addEventListener('click', posponer);
  $('#btn-activar-sonido').addEventListener('click', activarSonidoVideo);
  $('#btn-probar').addEventListener('click', probarAlarma);
  $('#btn-mesita').addEventListener('click', activarMesita);
  $('#btn-permiso-notif').addEventListener('click', pedirNotificaciones);
  $('#btn-permiso-exactas').addEventListener('click', pedirExactas);
  $('#posponer').addEventListener('change', (e) => {
    estado.posponerMin = Number(e.target.value);
    guardar();
  });
  document.addEventListener('pointerdown', sonido.desbloquear, { passive: true });

  $('#ajustes-nativo').hidden = !NATIVO;
  $('#ajustes-web').hidden = NATIVO;
  $('#ayuda-probar').textContent = NATIVO
    ? 'Suena en 10 segundos: bloqueá el celular para probar'
    : 'Suena enseguida para ver cómo es';

  if (actualizarVencimientos(estado, new Date())) guardar();
  dibujarAlarmas();
  actualizarProxima();
  avisoModoWeb();
  tic();

  if (NATIVO) {
    iniciarNativo().catch((error) => mostrarAviso('nativo', `Error al iniciar: ${error?.message || error}`));
  } else if ('serviceWorker' in navigator && location.protocol.startsWith('http')) {
    navigator.serviceWorker.register('sw.js').catch(() => {});
  }
}

iniciar();
