package io.github.axelitocoder.despertadorpato;

import android.app.NotificationManager;
import android.content.Context;
import android.content.Intent;
import android.net.Uri;
import android.os.Build;
import android.provider.Settings;
import com.getcapacitor.JSObject;
import com.getcapacitor.Plugin;
import com.getcapacitor.PluginCall;
import com.getcapacitor.PluginMethod;
import com.getcapacitor.annotation.CapacitorPlugin;
import org.json.JSONArray;
import org.json.JSONException;

/** Puente entre la app web (app.js) y las alarmas de pantalla completa. */
@CapacitorPlugin(name = "AlarmaNativa")
public class AlarmaPlugin extends Plugin {

    /** alarmas: [{id, en (ms), clave, alarmaId, etiqueta, hora}] — reemplaza las anteriores. */
    @PluginMethod
    public void programar(PluginCall call) {
        try {
            JSONArray lista = call.getArray("alarmas", new com.getcapacitor.JSArray());
            Alarmas.reemplazar(getContext(), new JSONArray(lista.toString()));
            call.resolve();
        } catch (JSONException e) {
            call.reject("Lista de alarmas inválida", e);
        }
    }

    /** Saca la notificación de una alarma (corta su sonido cuando ya arrancó el video). */
    @PluginMethod
    public void silenciar(PluginCall call) {
        NotificationManager nm = (NotificationManager) getContext().getSystemService(Context.NOTIFICATION_SERVICE);
        nm.cancel(call.getInt("id", 0));
        call.resolve();
    }

    /** Al apagar o posponer: la app deja de mostrarse encima de la pantalla de bloqueo. */
    @PluginMethod
    public void terminar(PluginCall call) {
        getActivity().runOnUiThread(() -> ((MainActivity) getActivity()).mostrarSobreBloqueo(false));
        call.resolve();
    }

    @PluginMethod
    public void estado(PluginCall call) {
        boolean pantallaCompleta = true;
        if (Build.VERSION.SDK_INT >= 34) {
            NotificationManager nm = (NotificationManager) getContext().getSystemService(Context.NOTIFICATION_SERVICE);
            pantallaCompleta = nm.canUseFullScreenIntent();
        }
        JSObject resultado = new JSObject();
        resultado.put("pantallaCompleta", pantallaCompleta);
        call.resolve(resultado);
    }

    /** Desde Android 14 el permiso de pantalla completa se puede desactivar en Ajustes. */
    @PluginMethod
    public void abrirAjustePantallaCompleta(PluginCall call) {
        if (Build.VERSION.SDK_INT >= 34) {
            Intent intent = new Intent(Settings.ACTION_MANAGE_APP_USE_FULL_SCREEN_INTENT,
                Uri.parse("package:" + getContext().getPackageName()));
            intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
            getContext().startActivity(intent);
        }
        call.resolve();
    }

    /**
     * Capacitor llama a este método con el intent que abrió la app (también al
     * arrancar en frío). Si viene de una alarma, se avisa a la app web; el evento
     * queda guardado hasta que app.js se suscriba.
     */
    @Override
    protected void handleOnNewIntent(Intent intent) {
        String datos = intent.getStringExtra(Alarmas.EXTRA);
        if (datos == null) return;
        intent.removeExtra(Alarmas.EXTRA);   // que no vuelva a sonar al girar la pantalla
        try {
            notifyListeners("alarma", new JSObject(datos), true);
        } catch (JSONException ignorado) {
            // datos inválidos: no hay nada que mostrar
        }
    }
}
