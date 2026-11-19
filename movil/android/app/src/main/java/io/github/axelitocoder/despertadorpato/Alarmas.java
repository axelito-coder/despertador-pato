package io.github.axelitocoder.despertadorpato;

import android.app.AlarmManager;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.PendingIntent;
import android.content.ContentResolver;
import android.content.Context;
import android.content.Intent;
import android.content.SharedPreferences;
import android.media.AudioAttributes;
import android.net.Uri;
import android.os.Build;
import org.json.JSONArray;
import org.json.JSONException;
import org.json.JSONObject;

/**
 * Alarmas de pantalla completa, como las del reloj de Android: se programan con
 * AlarmManager.setAlarmClock (exactas aunque el celular esté en reposo) y, al
 * sonar, AlarmaReceiver publica una notificación con "full screen intent" que
 * abre la app encima de la pantalla de bloqueo para que arranque el video.
 */
public final class Alarmas {

    static final String EXTRA = "alarma";
    static final String CANAL = "alarma_pantalla";
    private static final String PREFERENCIAS = "alarmas_nativas";
    private static final String CLAVE_LISTA = "lista";

    private Alarmas() {}

    /** Reemplaza todas las alarmas programadas por las de la lista. */
    static void reemplazar(Context ctx, JSONArray nuevas) {
        SharedPreferences prefs = ctx.getSharedPreferences(PREFERENCIAS, Context.MODE_PRIVATE);
        JSONArray viejas = leer(prefs);
        AlarmManager am = (AlarmManager) ctx.getSystemService(Context.ALARM_SERVICE);
        for (int i = 0; i < viejas.length(); i++) {
            JSONObject a = viejas.optJSONObject(i);
            if (a != null) am.cancel(alSonar(ctx, a));
        }
        prefs.edit().putString(CLAVE_LISTA, nuevas.toString()).apply();
        programarTodas(ctx, nuevas);
    }

    /** Vuelve a programar lo guardado (después de reiniciar el celular o actualizar la app). */
    static void restaurar(Context ctx) {
        programarTodas(ctx, leer(ctx.getSharedPreferences(PREFERENCIAS, Context.MODE_PRIVATE)));
    }

    private static void programarTodas(Context ctx, JSONArray lista) {
        AlarmManager am = (AlarmManager) ctx.getSystemService(Context.ALARM_SERVICE);
        long ahora = System.currentTimeMillis();
        for (int i = 0; i < lista.length(); i++) {
            JSONObject a = lista.optJSONObject(i);
            if (a == null || a.optLong("en") <= ahora) continue;
            long en = a.optLong("en");
            PendingIntent mostrar = PendingIntent.getActivity(
                ctx, a.optInt("id"), abrirApp(ctx, a.toString()),
                PendingIntent.FLAG_UPDATE_CURRENT | PendingIntent.FLAG_IMMUTABLE);
            try {
                am.setAlarmClock(new AlarmManager.AlarmClockInfo(en, mostrar), alSonar(ctx, a));
            } catch (SecurityException sinPermiso) {
                // Sin permiso de alarmas exactas: mejor tarde que nunca.
                am.setAndAllowWhileIdle(AlarmManager.RTC_WAKEUP, en, alSonar(ctx, a));
            }
        }
    }

    private static PendingIntent alSonar(Context ctx, JSONObject a) {
        Intent intent = new Intent(ctx, AlarmaReceiver.class).putExtra(EXTRA, a.toString());
        return PendingIntent.getBroadcast(
            ctx, a.optInt("id"), intent, PendingIntent.FLAG_UPDATE_CURRENT | PendingIntent.FLAG_IMMUTABLE);
    }

    static Intent abrirApp(Context ctx, String datos) {
        return new Intent(ctx, MainActivity.class)
            .setFlags(Intent.FLAG_ACTIVITY_NEW_TASK | Intent.FLAG_ACTIVITY_SINGLE_TOP)
            .putExtra(EXTRA, datos);
    }

    /** Canal de la alarma: sonido de alarma (suena aunque el celular esté en silencio). */
    static void crearCanal(Context ctx) {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.O) return;
        NotificationManager nm = ctx.getSystemService(NotificationManager.class);
        if (nm.getNotificationChannel(CANAL) != null) return;
        NotificationChannel canal = new NotificationChannel(CANAL, "Alarmas", NotificationManager.IMPORTANCE_HIGH);
        canal.setDescription("Abre el video de la alarma con el celular bloqueado");
        canal.setLockscreenVisibility(android.app.Notification.VISIBILITY_PUBLIC);
        canal.enableVibration(true);
        canal.setVibrationPattern(new long[] { 0, 700, 300, 700, 300, 700 });
        Uri sonido = Uri.parse(ContentResolver.SCHEME_ANDROID_RESOURCE + "://" + ctx.getPackageName() + "/raw/alarma");
        canal.setSound(sonido, new AudioAttributes.Builder()
            .setUsage(AudioAttributes.USAGE_ALARM)
            .setContentType(AudioAttributes.CONTENT_TYPE_SONIFICATION)
            .build());
        nm.createNotificationChannel(canal);
    }

    private static JSONArray leer(SharedPreferences prefs) {
        try {
            return new JSONArray(prefs.getString(CLAVE_LISTA, "[]"));
        } catch (JSONException e) {
            return new JSONArray();
        }
    }
}
