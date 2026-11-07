package mx.udem.library;

import javafx.application.Application;
import javafx.scene.Scene;
import javafx.stage.Stage;
import mx.udem.library.ui.Contexto;
import mx.udem.library.ui.LoginView;
import mx.udem.library.ui.MainView;

public class App extends Application {
    private Stage ventana;

    @Override
    public void start(Stage stage) {
        ventana = stage;
        stage.setTitle("Library · Cliente de escritorio");
        mostrarLogin(null);
        stage.show();
    }

    private void mostrarLogin(String mensaje) {
        LoginView login = new LoginView(this::mostrarPrincipal, () -> mostrarLogin("Tu sesión expiró o ya no es válida. Inicia sesión de nuevo."), mensaje);
        poner(login.vista(), 1000, 700);
        login.enfocar();
    }

    private void mostrarPrincipal(Contexto ctx) {
        MainView principal = new MainView(ctx, () -> mostrarLogin(null));
        poner(principal.vista(), 1200, 760);
    }

    private void poner(javafx.scene.Parent raiz, double w, double h) {
        Scene escena = new Scene(raiz, w, h);
        escena.getStylesheets().add(getClass().getResource("/estilos.css").toExternalForm());
        ventana.setScene(escena);
        ventana.centerOnScreen();
    }

    public static void main(String[] args) { launch(args); }
}
