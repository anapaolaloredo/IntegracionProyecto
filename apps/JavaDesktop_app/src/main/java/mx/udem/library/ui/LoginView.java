package mx.udem.library.ui;

import javafx.application.Platform;
import javafx.geometry.Insets;
import javafx.geometry.Pos;
import javafx.scene.Parent;
import javafx.scene.control.*;
import javafx.scene.layout.VBox;
import mx.udem.library.api.*;

import java.util.function.Consumer;

/** Login en dos pasos, tal como lo exige el servicio: correo+contrasena y luego el codigo 2FA del buzon de la instancia. */
public class LoginView {
    private final Consumer<Contexto> alAutenticar;
    private final Runnable alExpirar;
    private final VBox raiz = new VBox(12);
    private final TextField host = new TextField();
    private final TextField correo = new TextField();
    private final PasswordField clave = new PasswordField();
    private final TextField codigo = new TextField();
    private final Button continuar = new Button("Continuar");
    private final Button verificar = new Button("Verificar y entrar");
    private final Label estado = new Label();
    private Contexto ctx;

    public LoginView(Consumer<Contexto> alAutenticar, Runnable alExpirar, String mensajeInicial) {
        this.alAutenticar = alAutenticar;
        this.alExpirar = alExpirar;
        Label titulo = new Label("Library");
        titulo.getStyleClass().add("login-titulo");
        Label sub = new Label("Librería · cliente de escritorio");
        sub.getStyleClass().add("login-sub");
        host.setPromptText("IP o dominio del servidor GCP (ej. 34.12.56.78)");
        correo.setPromptText("Correo electrónico");
        clave.setPromptText("Contraseña");
        codigo.setPromptText("Código de 6 dígitos del buzón del servidor");
        codigo.setVisible(false); codigo.setManaged(false);
        verificar.setVisible(false); verificar.setManaged(false);
        continuar.setDefaultButton(true);
        continuar.setMaxWidth(Double.MAX_VALUE);
        verificar.setMaxWidth(Double.MAX_VALUE);
        estado.setWrapText(true);
        estado.getStyleClass().add("estado");
        if (mensajeInicial != null) estado.setText(mensajeInicial);
        continuar.setOnAction(e -> paso1());
        verificar.setOnAction(e -> paso2());
        codigo.setOnAction(e -> paso2());
        raiz.getChildren().addAll(titulo, sub, new Label("Servidor"), host, new Label("Cuenta"), correo, clave,
                continuar, codigo, verificar, estado);
        raiz.setAlignment(Pos.CENTER_LEFT);
        raiz.setPadding(new Insets(32));
        raiz.setMaxWidth(420);
        raiz.getStyleClass().add("login-card");
    }

    public Parent vista() {
        VBox centro = new VBox(raiz);
        centro.setAlignment(Pos.CENTER);
        centro.getStyleClass().add("login-fondo");
        return centro;
    }

    private void paso1() {
        try {
            Endpoints ep = Endpoints.desdeTexto(host.getText());
            if (correo.getText().isBlank() || clave.getText().isEmpty()) throw new IllegalArgumentException("Escribe correo y contraseña.");
            ctx = new Contexto(new Http(ep), alExpirar);
        } catch (IllegalArgumentException e) {
            estado.setText(e.getMessage());
            return;
        }
        continuar.setDisable(true);
        estado.setText("Validando credenciales...");
        Contexto c = ctx;
        c.async(() -> { c.auth.iniciarLogin(correo.getText().trim(), clave.getText()); return true; }, ok -> {
            continuar.setDisable(false);
            estado.setText("Te enviamos un código al buzón del servidor. Léelo ahí (SSH a la instancia) y escríbelo abajo.");
            for (var n : new javafx.scene.Node[]{codigo, verificar}) { n.setVisible(true); n.setManaged(true); }
            codigo.requestFocus();
        }, msg -> { continuar.setDisable(false); estado.setText(msg); });
    }

    private void paso2() {
        if (ctx == null || codigo.getText().isBlank()) { estado.setText("Escribe el código recibido."); return; }
        verificar.setDisable(true);
        Contexto c = ctx;
        c.async(() -> c.auth.verificar(correo.getText().trim(), codigo.getText()), s -> {
            verificar.setDisable(false);
            clave.clear();
            alAutenticar.accept(c);
        }, msg -> { verificar.setDisable(false); estado.setText(msg); });
    }

    public void enfocar() { Platform.runLater(host::requestFocus); }
}
