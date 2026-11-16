import assert from 'node:assert/strict';
import { test } from 'node:test';

import {
  VENTANA_MS, actualizarVencimientos, elegirVideo, esUrlYoutube, estadoInicial, idNotificacion,
  idVideo, normalizarEstado, nuevaAlarma, ocurrencias, planificar, proxima, sonandoAhora,
  textoCuando, textoDias, textoFalta,
} from '../www/alarmas.js';

// Lunes 19/10/2026 a las 08:00 (hora local), igual que en los tests de la versión de PC.
const LUNES_8AM = new Date(2026, 9, 19, 8, 0);
const fecha = (d, h, m = 0) => new Date(2026, 9, d, h, m);

test('proxima: una vez, hoy o mañana', () => {
  assert.deepEqual(proxima(nuevaAlarma({ hora: 9, minuto: 15, dias: [] }), LUNES_8AM), fecha(19, 9, 15));
  assert.deepEqual(proxima(nuevaAlarma({ hora: 7, minuto: 30, dias: [] }), LUNES_8AM), fecha(20, 7, 30));
  assert.deepEqual(proxima(nuevaAlarma({ hora: 8, minuto: 0, dias: [] }), LUNES_8AM), fecha(20, 8, 0));
});

test('proxima: días de la semana', () => {
  assert.deepEqual(proxima(nuevaAlarma({ hora: 10, minuto: 0, dias: [5, 6] }), LUNES_8AM), fecha(24, 10));
  assert.deepEqual(proxima(nuevaAlarma({ hora: 7, minuto: 0, dias: [0, 1, 2, 3, 4] }), fecha(23, 22)), fecha(26, 7));
  assert.deepEqual(proxima(nuevaAlarma({ hora: 7, minuto: 0, dias: [0] }), LUNES_8AM), fecha(26, 7));
});

test('ocurrencias en un rango', () => {
  const lunAVie = nuevaAlarma({ hora: 7, minuto: 0, dias: [0, 1, 2, 3, 4] });
  assert.equal(ocurrencias(lunAVie, LUNES_8AM, fecha(26, 23)).length, 5);   // mar a vie + lun 26
  const unaVez = nuevaAlarma({ hora: 9, minuto: 0, dias: [] });
  unaVez.vence = fecha(19, 9).toISOString();
  assert.deepEqual(ocurrencias(unaVez, LUNES_8AM, fecha(30, 0)), [fecha(19, 9)]);
  assert.deepEqual(ocurrencias(unaVez, fecha(19, 10), fecha(30, 0)), []);   // ya pasó: no se corre a mañana
});

test('textoDias', () => {
  assert.equal(textoDias([]), 'Una vez');
  assert.equal(textoDias([0, 1, 2, 3, 4, 5, 6]), 'Todos los días');
  assert.equal(textoDias([4, 3, 2, 1, 0]), 'Lunes a viernes');
  assert.equal(textoDias([6, 5]), 'Fin de semana');
  assert.equal(textoDias([0, 2]), 'Lun · Mié');
});

test('URLs de YouTube', () => {
  assert.ok(esUrlYoutube('https://www.youtube.com/watch?v=abc'));
  assert.ok(esUrlYoutube(' https://youtu.be/abc '));
  assert.ok(!esUrlYoutube('https://evil.com/youtube.com'));
  assert.ok(!esUrlYoutube('hola'));
  assert.equal(idVideo('https://www.youtube.com/watch?v=dQw4w9WgXcQ&t=10'), 'dQw4w9WgXcQ');
  assert.equal(idVideo('https://youtu.be/HgzGwKwLmgM'), 'HgzGwKwLmgM');
  assert.equal(idVideo('https://www.youtube.com/shorts/xyz123'), 'xyz123');
});

test('elegirVideo no repite los recientes', () => {
  for (let i = 0; i < 100; i++) {
    assert.equal(elegirVideo(['a', 'b', 'c', 'd'], ['a', 'b', 'c']), 'd');
  }
  assert.equal(elegirVideo([]), null);
  assert.equal(elegirVideo(['a'], ['a']), 'a');
  assert.equal(elegirVideo(['a', 'b'], ['a']), 'b');
});

test('normalizarEstado descarta datos rotos', () => {
  assert.deepEqual(normalizarEstado(null), estadoInicial());
  const e = normalizarEstado({
    alarmas: [{ hora: 7, minuto: 0, dias: [0, 9] }, { hora: 25, minuto: 0 }, 'basura'],
    videos: ['https://youtu.be/a', 'https://evil.com'],
    posponerMin: 500,
  });
  assert.equal(e.alarmas.length, 1);
  assert.deepEqual(e.alarmas[0].dias, [0]);
  assert.deepEqual(e.videos, ['https://youtu.be/a']);
  assert.equal(e.posponerMin, 5);
});

test('las alarmas de una vez se apagan solas después de sonar', () => {
  const estado = estadoInicial();
  const a = nuevaAlarma({ hora: 9, minuto: 0, dias: [] });
  estado.alarmas.push(a);
  assert.ok(actualizarVencimientos(estado, LUNES_8AM));
  assert.equal(a.vence, fecha(19, 9).toISOString());
  assert.ok(!actualizarVencimientos(estado, fecha(19, 9, 2)));          // dentro de la ventana: sigue
  assert.ok(actualizarVencimientos(estado, fecha(19, 9, 5)));           // pasó la ventana: se apaga
  assert.equal(a.activa, false);
});

test('planificar: tres avisos por vez, ids estables, máximo respetado', () => {
  const estado = estadoInicial();
  const a = nuevaAlarma({ hora: 7, minuto: 0, dias: [0, 1, 2, 3, 4, 5, 6] });
  estado.alarmas.push(a);
  const avisos = planificar(estado, LUNES_8AM, { dias: 2 });
  assert.equal(avisos.length, 6);                                       // mar 20 y mié 21, 3 avisos c/u
  assert.deepEqual(avisos.slice(0, 3).map((v) => v.en), [fecha(20, 7, 0), fecha(20, 7, 1), fecha(20, 7, 2)]);
  const clave = `${a.id}@${fecha(20, 7).toISOString()}`;
  assert.equal(avisos[1].id, idNotificacion(clave, 1));
  assert.equal(new Set(avisos.map((v) => v.id)).size, avisos.length);
  assert.equal(planificar(estado, LUNES_8AM, { dias: 30, maximo: 10 }).length, 10);
});

test('planificar: lo que está sonando conserva los avisos que faltan', () => {
  const estado = estadoInicial();
  const a = nuevaAlarma({ hora: 8, minuto: 0, dias: [0] });
  estado.alarmas.push(a);
  const avisos = planificar(estado, new Date(2026, 9, 19, 8, 0, 30), { dias: 1 });
  assert.deepEqual(avisos.map((v) => v.intento), [1, 2]);               // el primero ya sonó
  estado.atendidas.push(avisos[0].clave);                               // apagada: no queda nada
  assert.equal(planificar(estado, new Date(2026, 9, 19, 8, 0, 30), { dias: 1 }).length, 0);
});

test('planificar incluye las pospuestas', () => {
  const estado = estadoInicial();
  estado.pospuestas.push({ clave: 'p-1', cuando: fecha(19, 8, 10).toISOString(), alarmaId: 'x', etiqueta: 'Escuela' });
  const avisos = planificar(estado, LUNES_8AM);
  assert.equal(avisos.length, 3);
  assert.ok(avisos.every((v) => v.pospuesta && v.etiqueta === 'Escuela'));
});

test('sonandoAhora detecta la alarma recién vencida', () => {
  const estado = estadoInicial();
  estado.alarmas.push(nuevaAlarma({ hora: 8, minuto: 0, dias: [0] }));
  assert.equal(sonandoAhora(estado, new Date(2026, 9, 19, 7, 59)).length, 0);
  assert.equal(sonandoAhora(estado, new Date(2026, 9, 19, 8, 1)).length, 1);
  assert.equal(sonandoAhora(estado, new Date(LUNES_8AM.getTime() + VENTANA_MS + 1000)).length, 0);
});

test('textos de fechas', () => {
  assert.equal(textoCuando(fecha(19, 9), LUNES_8AM), 'hoy 09:00');
  assert.equal(textoCuando(fecha(20, 7), LUNES_8AM), 'mañana 07:00');
  assert.equal(textoCuando(fecha(23, 7), LUNES_8AM), 'vie 07:00');
  assert.equal(textoFalta(fecha(19, 9, 30), LUNES_8AM), '1 h 30 min');
  assert.equal(textoFalta(new Date(2026, 9, 19, 8, 0, 30), LUNES_8AM), 'menos de 1 min');
});
