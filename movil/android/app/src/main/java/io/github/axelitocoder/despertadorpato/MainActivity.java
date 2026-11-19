package io.github.axelitocoder.despertadorpato;

import android.content.Intent;
import android.os.Build;
import android.os.Bundle;
import android.view.WindowManager;
import com.getcapacitor.BridgeActivity;

public class MainActivity extends BridgeActivity {

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        registerPlugin(AlarmaPlugin.class);
        super.onCreate(savedInstanceState);
    }

    @Override
    protected void onNewIntent(Intent intent) {
        // Se revisa antes de llamar a super: el plugin consume el dato de la alarma.
        if (intent != null && intent.getStringExtra(Alarmas.EXTRA) != null) {
            mostrarSobreBloqueo(true);
        }
        super.onNewIntent(intent);
    }

    /** Con una alarma sonando, la app se muestra encima del bloqueo y prende la pantalla. */
    void mostrarSobreBloqueo(boolean mostrar) {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O_MR1) {
            setShowWhenLocked(mostrar);
            setTurnScreenOn(mostrar);
        } else {
            int flags = WindowManager.LayoutParams.FLAG_SHOW_WHEN_LOCKED | WindowManager.LayoutParams.FLAG_TURN_SCREEN_ON;
            if (mostrar) getWindow().addFlags(flags);
            else getWindow().clearFlags(flags);
        }
        if (mostrar) getWindow().addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON);
        else getWindow().clearFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON);
    }
}
