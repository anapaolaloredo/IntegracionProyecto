package mx.udem.library.ui;

import com.fasterxml.jackson.core.JsonProcessingException;
import javafx.application.Platform;
import javafx.geometry.Insets;
import javafx.scene.control.*;
import javafx.scene.layout.*;
import javafx.scene.web.WebEngine;
import javafx.scene.web.WebView;
import mx.udem.library.api.Http;
import mx.udem.library.tracking.CodigoRastreo;
import mx.udem.library.tracking.EventoRastreo;

import java.util.ArrayList;
import java.util.List;
import java.util.Locale;

/**
 * Seguimiento: el WebSocket vive en Java (ClienteRastreo); este panel solo pinta lo que llega.
 * El mapa (Leaflet + OpenStreetMap) se embebe en un WebView y se maneja con executeScript.
 */
public class RastreoView extends BorderPane {
    private static final List<String> ETAPAS = List.of("Pedido confirmado", "Preparando pedido", "Pedido enviado", "En ruta de entrega", "Entregado");

    private final Contexto ctx;
    private final TextField codigo = new TextField();
    private final Label mensaje = new Label();
    private final Label estadoActual = new Label("—");
    private final Label coordenadas = new Label("Ubicación: —");
    private final Label destino = new Label("Destino: —");
    private final ProgressBar barra = new ProgressBar(0);
    private final List<Label> etapas = new ArrayList<>();
    private final WebEngine motor;
    private final List<String> pendientes = new ArrayList<>();
    private boolean mapaListo;

    public RastreoView(Contexto ctx) {
        this.ctx = ctx;
        WebView web = new WebView();
        motor = web.getEngine();
        motor.getLoadWorker().stateProperty().addListener((o, a, s) -> {
            if (s == javafx.concurrent.Worker.State.SUCCEEDED) {
                mapaListo = true;
                pendientes.forEach(motor::executeScript);
                pendientes.clear();
            }
        });
        motor.load(getClass().getResource("/mapa/mapa.html").toExternalForm());
        // Leaflet debe recalcular su tamano cada vez que el panel cambia o la pestana se muestra.
        web.widthProperty().addListener((o, a, n) -> ejecutar("mapa.invalidateSize()"));
        web.heightProperty().addListener((o, a, n) -> ejecutar("mapa.invalidateSize()"));
        sceneProperty().addListener((o, a, n) -> { if (n != null) ejecutar("mapa.invalidateSize()"); });
        visibleProperty().addListener((o, a, v) -> { if (v) ejecutar("mapa.invalidateSize()"); });

        codigo.setPromptText("LIB-MTY-2026-000125");
        codigo.setPrefColumnCount(22);
        Button rastrear = new Button("Rastrear pedido");
        rastrear.getStyleClass().add("primario");
        rastrear.setDefaultButton(false);
        rastrear.setOnAction(e -> rastrear(codigo.getText()));
        codigo.setOnAction(e -> rastrear(codigo.getText()));
        HBox arriba = new HBox(8, new Label("Código de rastreo:"), codigo, rastrear, mensaje);
        arriba.setPadding(new Insets(12));
        arriba.setAlignment(javafx.geometry.Pos.CENTER_LEFT);
        mensaje.getStyleClass().add("estado");

        estadoActual.getStyleClass().add("estado-grande");
        barra.setMaxWidth(Double.MAX_VALUE);
        VBox lateral = new VBox(10, new Label("Estado de la entrega"), estadoActual, barra);
        for (String e : ETAPAS) {
            Label l = new Label("○  " + e);
            l.getStyleClass().add("etapa");
            etapas.add(l);
            lateral.getChildren().add(l);
        }
        lateral.getChildren().addAll(coordenadas, destino);
        lateral.setPadding(new Insets(12));
        lateral.setPrefWidth(260);
        setTop(arriba);
        setCenter(web);
        setRight(lateral);
    }

    /** Punto de entrada tambien para "Rastrear" desde Mis compras o desde la confirmacion de compra. */
    public void rastrear(String texto) {
        String c = CodigoRastreo.normalizar(texto);
        codigo.setText(c);
        if (!CodigoRastreo.valido(c)) { mensaje.setText("Formato inválido. Ejemplo: LIB-MTY-2026-000125"); return; }
        mensaje.setText("Conectando con el servidor de rastreo...");
        reiniciarPanel();
        ejecutar("limpiar()");
        String token = ctx.http.sesion().accessToken();
        ctx.rastreo.conectar(ctx.http.endpoints().rastreoWs(), token, c,
                ev -> Platform.runLater(() -> alEvento(ev)),
                err -> Platform.runLater(() -> { if (err != null) mensaje.setText(err); }));
    }

    private void alEvento(EventoRastreo ev) {
        switch (ev.tipo()) {
            case "error" -> { mensaje.setText(ev.mensaje()); estadoActual.setText("—"); }
            case "inicio" -> {
                mensaje.setText("Seguimiento activo (" + codigo.getText() + ")");
                destino.setText("Destino: " + ev.destino());
                try {
                    ejecutar("setRuta(" + Http.JSON.writeValueAsString(ev.ruta()) + "," + Http.JSON.writeValueAsString(ev.destino()) + ")");
                } catch (JsonProcessingException e) {
                    mensaje.setText("No se pudo dibujar la ruta.");
                }
            }
            case "posicion" -> {
                estadoActual.setText(ev.estado());
                coordenadas.setText(String.format(Locale.US, "Ubicación: %.5f, %.5f", ev.lat(), ev.lng()));
                barra.setProgress(ev.progreso());
                marcarEtapas(ev.estado());
                ejecutar(String.format(Locale.US, "mover(%f,%f,%b)", ev.lat(), ev.lng(),
                        "En ruta de entrega".equals(ev.estado()) || ev.entregado()));
                if (ev.entregado()) mensaje.setText("Pedido entregado. Puedes consultarlo de nuevo con su código.");
            }
            default -> { }
        }
    }

    private void marcarEtapas(String actual) {
        int idx = ETAPAS.indexOf(actual);
        for (int i = 0; i < etapas.size(); i++) {
            Label l = etapas.get(i);
            l.setText((i < idx || (i == idx && idx == ETAPAS.size() - 1) ? "●  " : i == idx ? "◉  " : "○  ") + ETAPAS.get(i));
            l.getStyleClass().removeAll("etapa-actual", "etapa-hecha");
            if (i == idx) l.getStyleClass().add("etapa-actual");
            else if (i < idx) l.getStyleClass().add("etapa-hecha");
        }
    }

    private void reiniciarPanel() {
        estadoActual.setText("—");
        coordenadas.setText("Ubicación: —");
        destino.setText("Destino: —");
        barra.setProgress(0);
        marcarEtapas("");
    }

    private void ejecutar(String js) {
        if (mapaListo) motor.executeScript(js); else pendientes.add(js);
    }

    public void detener() { ctx.rastreo.cerrar(); }
}
