package io.github.axelitocoder.despertadorpato;

import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;

/** Android borra las alarmas al reiniciar o actualizar la app: se vuelven a programar. */
public class ArranqueReceiver extends BroadcastReceiver {

    @Override
    public void onReceive(Context ctx, Intent intent) {
        String accion = intent.getAction();
        if (Intent.ACTION_BOOT_COMPLETED.equals(accion) || Intent.ACTION_MY_PACKAGE_REPLACED.equals(accion)) {
            Alarmas.restaurar(ctx);
        }
    }
}
