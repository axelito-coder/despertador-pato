package io.github.axelitocoder.despertadorpato;

import android.app.Notification;
import android.app.PendingIntent;
import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;
import androidx.core.app.NotificationCompat;
import androidx.core.app.NotificationManagerCompat;
import org.json.JSONException;
import org.json.JSONObject;

/**
 * Se ejecuta a la hora de la alarma. Publica una notificación con "full screen
 * intent": con el celular bloqueado o la pantalla apagada, Android abre la app
 * directamente (encima del bloqueo) y arranca el video. Si el celular se está
 * usando, Android la muestra como notificación emergente con sonido.
 */
public class AlarmaReceiver extends BroadcastReceiver {

    @Override
    public void onReceive(Context ctx, Intent intent) {
        String datos = intent.getStringExtra(Alarmas.EXTRA);
        if (datos == null) return;
        JSONObject alarma;
        try {
            alarma = new JSONObject(datos);
        } catch (JSONException e) {
            return;
        }
        int id = alarma.optInt("id");
        String etiqueta = alarma.optString("etiqueta", "Alarma");
        String hora = alarma.optString("hora", "");

        Alarmas.crearCanal(ctx);
        PendingIntent abrir = PendingIntent.getActivity(
            ctx, id, Alarmas.abrirApp(ctx, datos),
            PendingIntent.FLAG_UPDATE_CURRENT | PendingIntent.FLAG_IMMUTABLE);

        Notification notificacion = new NotificationCompat.Builder(ctx, Alarmas.CANAL)
            .setSmallIcon(R.drawable.ic_stat_pato)
            .setColor(0xFFFFC93C)
            .setContentTitle("¡Arriba!")
            .setContentText(etiqueta + (hora.isEmpty() ? "" : " · " + hora) + ". Tocá para ver tu video.")
            .setPriority(NotificationCompat.PRIORITY_MAX)
            .setCategory(NotificationCompat.CATEGORY_ALARM)
            .setVisibility(NotificationCompat.VISIBILITY_PUBLIC)
            .setFullScreenIntent(abrir, true)
            .setContentIntent(abrir)
            .setOngoing(true)
            .setAutoCancel(true)
            .build();

        NotificationManagerCompat nm = NotificationManagerCompat.from(ctx);
        if (!nm.areNotificationsEnabled()) return;
        try {
            nm.notify(id, notificacion);
        } catch (SecurityException sinPermiso) {
            // Sin permiso de notificaciones: quedan los avisos de respaldo.
        }
    }
}
