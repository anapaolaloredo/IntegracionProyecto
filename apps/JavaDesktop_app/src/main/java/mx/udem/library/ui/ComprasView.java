package mx.udem.library.ui;

import javafx.collections.FXCollections;
import javafx.geometry.Insets;
import javafx.scene.control.*;
import javafx.scene.layout.*;
import mx.udem.library.model.Pago;
import mx.udem.library.model.Pedido;
import mx.udem.library.tracking.CodigoRastreo;

import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.function.Consumer;

/** Mis compras: pedidos y pagos reales. El estado de pago sale de la tabla de pagos, no se supone. */
public class ComprasView extends BorderPane {
    private final Contexto ctx;
    private final Consumer<String> abrirRastreo;
    private final TableView<Pedido> tabla = new TableView<>();
    private final Map<Long, Pago> pagoPorPedido = new HashMap<>();
    private final TextArea detalle = new TextArea();
    private final Button rastrear = new Button("Rastrear pedido");
    private final Button enviar = new Button("Marcar como enviado (admin)");
    private final Label estado = new Label();

    public ComprasView(Contexto ctx, Consumer<String> abrirRastreo) {
        this.ctx = ctx;
        this.abrirRastreo = abrirRastreo;
        columna("Pedido", 70, p -> "#" + p.idPedido());
        columna("Fecha", 190, Pedido::fecha);
        columna("Total", 100, p -> "$" + p.total().toPlainString());
        columna("Estado", 100, Pedido::estado);
        columna("Pago", 170, p -> pagoTexto(p));
        columna("Código de rastreo", 190, p -> CodigoRastreo.generar(p.idPedido(), p.fecha()));
        tabla.getSelectionModel().selectedItemProperty().addListener((o, a, p) -> mostrar(p));
        detalle.setEditable(false);
        detalle.setPrefRowCount(8);
        rastrear.setDisable(true);
        enviar.setVisible(ctx.http.sesion().esAdmin());
        enviar.setManaged(ctx.http.sesion().esAdmin());
        enviar.setDisable(true);
        rastrear.getStyleClass().add("primario");
        rastrear.setOnAction(e -> {
            Pedido p = tabla.getSelectionModel().getSelectedItem();
            if (p != null) abrirRastreo.accept(CodigoRastreo.generar(p.idPedido(), p.fecha()));
        });
        enviar.setOnAction(e -> cambiarEstado("enviado"));
        Button actualizar = new Button("Actualizar");
        actualizar.setOnAction(e -> cargar());
        HBox barra = new HBox(8, actualizar, estado);
        barra.setPadding(new Insets(12));
        VBox abajo = new VBox(8, new Label("Detalle del pedido"), detalle, new HBox(8, rastrear, enviar));
        abajo.setPadding(new Insets(12));
        setTop(barra);
        setCenter(tabla);
        setBottom(abajo);
    }

    private void columna(String titulo, double ancho, java.util.function.Function<Pedido, String> f) {
        TableColumn<Pedido, String> c = new TableColumn<>(titulo);
        c.setPrefWidth(ancho);
        c.setCellValueFactory(cd -> new javafx.beans.property.SimpleStringProperty(f.apply(cd.getValue())));
        tabla.getColumns().add(c);
    }

    private String pagoTexto(Pedido p) {
        Pago pago = pagoPorPedido.get(p.idPedido());
        if (pago != null) return "Pagado · " + pago.metodo() + " $" + pago.monto().toPlainString();
        return "cancelado".equals(p.estado()) ? "Sin pago (cancelado)" : "Sin pago registrado";
    }

    public void cargar() {
        estado.setText("Cargando...");
        record Datos(List<Pedido> pedidos, List<Pago> pagos) {}
        ctx.async(() -> new Datos(ctx.pedidos.listar(), ctx.pagos.listar()), d -> {
            pagoPorPedido.clear();
            d.pagos().forEach(p -> pagoPorPedido.put(p.idPedido(), p));
            tabla.setItems(FXCollections.observableArrayList(d.pedidos()));
            estado.setText(d.pedidos().size() + " pedido(s).");
        }, msg -> estado.setText(msg));
    }

    private void mostrar(Pedido p) {
        rastrear.setDisable(p == null);
        enviar.setDisable(p == null || !"pagado".equals(p.estado()));
        if (p == null) { detalle.clear(); return; }
        detalle.setText("Cargando...");
        ctx.async(() -> ctx.pedidos.obtener(p.idPedido()), full -> {
            StringBuilder sb = new StringBuilder("Pedido #" + full.idPedido() + " · " + full.estado() + " · total $" + full.total().toPlainString() + "\n");
            full.lineas().forEach(l -> sb.append(String.format("  %d x %s (ISBN %s)  $%s c/u = $%s%n", l.cantidad(), l.titulo(),
                    l.isbn(), l.precioUnitario().toPlainString(), l.importe().toPlainString())));
            sb.append("\nPago: ").append(pagoTexto(full)).append("\nCódigo de rastreo: ").append(CodigoRastreo.generar(full.idPedido(), full.fecha()));
            detalle.setText(sb.toString());
        }, detalle::setText);
    }

    private void cambiarEstado(String nuevo) {
        Pedido p = tabla.getSelectionModel().getSelectedItem();
        if (p == null) return;
        ctx.async(() -> { ctx.pedidos.cambiarEstado(p.idPedido(), nuevo); return true; }, ok -> cargar(), Dialogos::error);
    }
}
