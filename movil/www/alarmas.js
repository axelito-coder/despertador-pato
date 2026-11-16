// Lógica pura del Despertador Pato (sin DOM ni plugins): la usa la app y los
// tests de Node. Es el equivalente de nucleo.py de la versión de PC.

export const DIAS_CORTOS = ['L', 'M', 'X', 'J', 'V', 'S', 'D'];
export const DIAS_ABREV = ['Lun', 'Mar', 'Mié', 'Jue', 'Vie', 'Sáb', 'Dom'];
const DIAS_LARGOS = ['lunes', 'martes', 'miércoles', 'jueves', 'viernes', 'sábado', 'domingo'];
const MESES = ['enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio', 'julio',
  'agosto', 'septiembre', 'octubre', 'noviembre', 'diciembre'];

const DOMINIOS_YOUTUBE = new Set(['youtube.com', 'www.youtube.com', 'm.youtube.com',
  'music.youtube.com', 'youtu.be']);

export const VIDEOS_INICIALES = [
  'https://www.youtube.com/watch?v=IcrbM1l_BoI',
  'https://www.youtube.com/watch?v=HgzGwKwLmgM',
  'https://www.youtube.com/watch?v=dQw4w9WgXcQ',
];

// Cuánto tiempo después de sonar sigue "viva" una alarma: mientras tanto se puede
// apagar o posponer, y en el celular se repite el aviso.
export const VENTANA_MS = 3 * 60 * 1000;

// JavaScript numera los días con 0 = domingo; acá (como en la versión de PC) 0 = lunes.
export const diaSemana = (fecha) => (fecha.getDay() + 6) % 7;

const dos = (n) => String(n).padStart(2, '0');
export const textoHora = (a) => `${dos(a.hora)}:${dos(a.minuto)}`;

export function nuevaAlarma({ hora = 7, minuto = 0, etiqueta = '', dias = [0, 1, 2, 3, 4], activa = true } = {}) {
  return {
    id: Math.random().toString(16).slice(2, 10).padEnd(8, '0'),
    hora, minuto, etiqueta,
    dias: [...new Set(dias)].filter((d) => d >= 0 && d <= 6).sort((a, b) => a - b),
    activa,
    vence: null,   // solo para las de "una vez": cuándo suenan
  };
}

/** Próxima vez que debe sonar, estrictamente después de `desde` (o null). */
export function proxima(alarma, desde) {
  for (let i = 0; i < 8; i++) {
    const candidato = new Date(desde.getFullYear(), desde.getMonth(), desde.getDate() + i,
      alarma.hora, alarma.minuto, 0, 0);
    if (candidato <= desde) continue;
    if (!alarma.dias.length || alarma.dias.includes(diaSemana(candidato))) return candidato;
  }
  return null;
}

/** Todas las veces que suena entre `desde` (excluido) y `hasta` (incluido). */
export function ocurrencias(alarma, desde, hasta) {
  if (!alarma.dias.length) {
    const vence = alarma.vence ? new Date(alarma.vence) : proxima(alarma, desde);
    return vence && vence > desde && vence <= hasta ? [vence] : [];
  }
  const lista = [];
  let actual = desde;
  for (;;) {
    const p = proxima(alarma, actual);
    if (!p || p > hasta) return lista;
    lista.push(p);
    actual = p;
  }
}

export function textoDias(dias) {
  const d = [...new Set(dias)].sort((a, b) => a - b).join(',');
  if (!d) return 'Una vez';
  if (d === '0,1,2,3,4,5,6') return 'Todos los días';
  if (d === '0,1,2,3,4') return 'Lunes a viernes';
  if (d === '5,6') return 'Fin de semana';
  return d.split(',').map((i) => DIAS_ABREV[i]).join(' · ');
}

// ------------------------------------------------------------------ videos

export function esUrlYoutube(texto) {
  try {
    const url = new URL(String(texto).trim());
    return (url.protocol === 'https:' || url.protocol === 'http:') &&
      DOMINIOS_YOUTUBE.has(url.hostname.toLowerCase());
  } catch {
    return false;
  }
}

/** Id del video (para la miniatura), o null. */
export function idVideo(texto) {
  if (!esUrlYoutube(texto)) return null;
  const url = new URL(texto.trim());
  if (url.hostname.toLowerCase() === 'youtu.be') return url.pathname.slice(1).split('/')[0] || null;
  const v = url.searchParams.get('v');
  if (v) return v;
  const partes = url.pathname.split('/').filter(Boolean);
  if (['shorts', 'embed', 'live'].includes(partes[0])) return partes[1] || null;
  return null;
}

/** Elige un video al azar evitando los últimos `evitar` que sonaron. */
export function elegirVideo(urls, historial = [], evitar = 3, azar = Math.random) {
  if (!urls.length) return null;
  const cuantos = Math.min(evitar, new Set(urls).size - 1);
  const recientes = new Set(cuantos > 0 ? historial.slice(-cuantos) : []);
  const candidatos = urls.filter((u) => !recientes.has(u));
  const lista = candidatos.length ? candidatos : urls;
  return lista[Math.floor(azar() * lista.length)];
}

// ------------------------------------------------------------------ estado

export function estadoInicial() {
  return {
    alarmas: [],
    videos: [...VIDEOS_INICIALES],
    historial: [],
    posponerMin: 5,
    pospuestas: [],    // [{clave, cuando (ISO), alarmaId, etiqueta}]
    atendidas: [],     // claves de alarmas ya apagadas o pospuestas
  };
}

/** Valida lo leído del almacenamiento: nunca confía en que esté bien formado. */
export function normalizarEstado(datos) {
  const base = estadoInicial();
  if (!datos || typeof datos !== 'object') return base;
  const entero = (v, min, max, def) => (Number.isInteger(v) && v >= min && v <= max ? v : def);
  const alarmas = (Array.isArray(datos.alarmas) ? datos.alarmas : []).flatMap((a) => {
    if (!a || !Number.isInteger(a.hora) || !Number.isInteger(a.minuto)) return [];
    if (a.hora < 0 || a.hora > 23 || a.minuto < 0 || a.minuto > 59) return [];
    const alarma = nuevaAlarma({
      hora: a.hora, minuto: a.minuto,
      etiqueta: typeof a.etiqueta === 'string' ? a.etiqueta.slice(0, 40) : '',
      dias: Array.isArray(a.dias) ? a.dias.filter(Number.isInteger) : [],
      activa: a.activa !== false,
    });
    if (typeof a.id === 'string' && a.id) alarma.id = a.id;
    if (typeof a.vence === 'string' && !Number.isNaN(Date.parse(a.vence))) alarma.vence = a.vence;
    return [alarma];
  });
  return {
    alarmas,
    videos: Array.isArray(datos.videos) ? datos.videos.filter(esUrlYoutube) : base.videos,
    historial: (Array.isArray(datos.historial) ? datos.historial : []).filter((u) => typeof u === 'string').slice(-20),
    posponerMin: entero(datos.posponerMin, 1, 60, 5),
    pospuestas: (Array.isArray(datos.pospuestas) ? datos.pospuestas : [])
      .filter((p) => p && typeof p.clave === 'string' && !Number.isNaN(Date.parse(p.cuando))),
    atendidas: (Array.isArray(datos.atendidas) ? datos.atendidas : []).filter((c) => typeof c === 'string').slice(-100),
  };
}

/** Deja el estado al día: apaga las alarmas de "una vez" que ya sonaron y
 *  completa `vence` en las que no lo tienen. Devuelve true si cambió algo. */
export function actualizarVencimientos(estado, ahora) {
  let cambios = false;
  for (const a of estado.alarmas) {
    if (a.dias.length) {
      if (a.vence) { a.vence = null; cambios = true; }
      continue;
    }
    if (!a.activa) continue;
    if (!a.vence) {
      a.vence = proxima(a, ahora).toISOString();
      cambios = true;
    } else if (ahora - new Date(a.vence) > VENTANA_MS) {
      a.activa = false;
      a.vence = null;
      cambios = true;
    }
  }
  const vigentes = estado.pospuestas.filter((p) => ahora - new Date(p.cuando) <= VENTANA_MS);
  if (vigentes.length !== estado.pospuestas.length) {
    estado.pospuestas = vigentes;
    cambios = true;
  }
  return cambios;
}

// --------------------------------------------------------------- agenda

/** Número estable para identificar una notificación (Android pide enteros de 32 bits). */
function hashEntero(texto) {
  let h = 2166136261;
  for (const c of texto) {
    h ^= c.codePointAt(0);
    h = Math.imul(h, 16777619);
  }
  return (h >>> 0) % 200000000;
}

export const idNotificacion = (clave, intento) => hashEntero(clave) * 10 + intento;

/**
 * Arma la agenda: cada vez que suena una alarma (o una pospuesta) en los
 * próximos `dias` días, con `repeticiones` avisos separados `separacionMin`
 * minutos. Incluye lo que sonó hace menos de VENTANA_MS y todavía no se atendió,
 * pero solo los avisos que siguen en el futuro. La clave de cada vez que suena
 * es estable, así se puede cancelar aunque la agenda se vuelva a armar.
 */
export function planificar(estado, ahora, { dias = 14, repeticiones = 3, separacionMin = 1, maximo = 450 } = {}) {
  const desde = new Date(ahora.getTime() - VENTANA_MS);
  const hasta = new Date(ahora.getTime() + dias * 86400000);
  const atendidas = new Set(estado.atendidas);
  const veces = [];

  for (const a of estado.alarmas) {
    if (!a.activa) continue;
    for (const cuando of ocurrencias(a, desde, hasta)) {
      veces.push({ clave: `${a.id}@${cuando.toISOString()}`, cuando, alarmaId: a.id, etiqueta: a.etiqueta, pospuesta: false });
    }
  }
  for (const p of estado.pospuestas) {
    const cuando = new Date(p.cuando);
    if (cuando > desde && cuando <= hasta) {
      veces.push({ clave: p.clave, cuando, alarmaId: p.alarmaId, etiqueta: p.etiqueta, pospuesta: true });
    }
  }

  const avisos = [];
  for (const v of veces.sort((x, y) => x.cuando - y.cuando)) {
    if (atendidas.has(v.clave)) continue;
    for (let intento = 0; intento < repeticiones; intento++) {
      const en = new Date(v.cuando.getTime() + intento * separacionMin * 60000);
      if (en > ahora) avisos.push({ ...v, intento, en, id: idNotificacion(v.clave, intento) });
    }
  }
  return avisos.slice(0, maximo);
}

/** Alarmas que ya sonaron (hace menos de VENTANA_MS) y nadie apagó ni pospuso. */
export function sonandoAhora(estado, ahora) {
  return planificar(estado, new Date(ahora.getTime() - VENTANA_MS), { dias: 1, repeticiones: 1 })
    .filter((v) => v.cuando <= ahora);
}

// ------------------------------------------------------------------ textos

export const textoFecha = (m) => `${DIAS_LARGOS[diaSemana(m)]} ${m.getDate()} de ${MESES[m.getMonth()]}`;

export function textoCuando(objetivo, ahora) {
  const inicio = (d) => new Date(d.getFullYear(), d.getMonth(), d.getDate());
  const dias = Math.round((inicio(objetivo) - inicio(ahora)) / 86400000);
  const hora = `${dos(objetivo.getHours())}:${dos(objetivo.getMinutes())}`;
  if (dias === 0) return `hoy ${hora}`;
  if (dias === 1) return `mañana ${hora}`;
  return `${DIAS_ABREV[diaSemana(objetivo)].toLowerCase()} ${hora}`;
}

export function textoFalta(objetivo, ahora) {
  const segundos = Math.max(0, Math.floor((objetivo - ahora) / 1000));
  const horas = Math.floor(segundos / 3600);
  const minutos = Math.floor((segundos % 3600) / 60);
  if (horas >= 24) return `${Math.floor(horas / 24)} d ${horas % 24} h`;
  if (horas) return `${horas} h ${minutos} min`;
  if (minutos) return `${minutos} min`;
  return 'menos de 1 min';
}
