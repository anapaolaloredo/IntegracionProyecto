package mx.udem.library.ui;

import javafx.geometry.Insets;
import javafx.scene.control.Label;
import javafx.scene.layout.GridPane;
import mx.udem.library.model.Usuario;

public class PerfilView extends GridPane {
    private final Label nombre = new Label("..."), correo = new Label("..."), rol = new Label("..."), id = new Label("...");

    public PerfilView(Contexto ctx, java.util.function.Consumer<Usuario> alCargar) {
        setPadding(new Insets(24));
        setHgap(16);
        setVgap(12);
        addRow(0, new Label("Nombre:"), nombre);
        addRow(1, new Label("Correo:"), correo);
        addRow(2, new Label("Rol:"), rol);
        addRow(3, new Label("Identificador:"), id);
        long uid = ctx.http.sesion().userId();
        id.setText(String.valueOf(uid));
        ctx.async(() -> ctx.users.perfil(uid), u -> {
            nombre.setText(u.nombreCompleto());
            correo.setText(u.correo());
            rol.setText(u.rol());
            alCargar.accept(u);
        }, msg -> nombre.setText(msg));
    }
}
