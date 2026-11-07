package mx.udem.library.ui;

import javafx.scene.control.Alert;
import javafx.scene.control.ButtonType;

import java.util.Optional;

final class Dialogos {
    private Dialogos() {}

    static void error(String mensaje) { mostrar(Alert.AlertType.ERROR, "Error", mensaje); }
    static void info(String titulo, String mensaje) { mostrar(Alert.AlertType.INFORMATION, titulo, mensaje); }

    static boolean confirmar(String titulo, String mensaje) {
        Alert a = new Alert(Alert.AlertType.CONFIRMATION, mensaje, ButtonType.OK, ButtonType.CANCEL);
        a.setHeaderText(titulo);
        Optional<ButtonType> r = a.showAndWait();
        return r.isPresent() && r.get() == ButtonType.OK;
    }

    private static void mostrar(Alert.AlertType tipo, String titulo, String mensaje) {
        Alert a = new Alert(tipo, mensaje, ButtonType.OK);
        a.setHeaderText(titulo);
        a.getDialogPane().setMinWidth(420);
        a.showAndWait();
    }
}
