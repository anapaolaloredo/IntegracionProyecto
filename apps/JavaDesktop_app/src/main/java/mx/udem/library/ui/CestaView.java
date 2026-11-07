package mx.udem.library.ui;

import javafx.geometry.Insets;
import javafx.geometry.Pos;
import javafx.scene.control.*;
import javafx.scene.layout.*;
import mx.udem.library.api.PagosApi;
import mx.udem.library.api.CompraService;
import mx.udem.library.cart.Cesta;
import mx.udem.library.tracking.CodigoRastreo;

import java.util.function.Consumer;

public class CestaView extends BorderPane {
    private final Contexto ctx;
    private final Runnable alCambiar;
    private final Consumer<String> abrirRastreo;
    private final Runnable alComprar;
    private final VBox filas = new VBox(8);
    private final Label subtotal = new Label(), envio = new Label(), total = new Label(), estado = new Label();
    private final ComboBox<String> metodo = new ComboBox<>();
    private final Button confirmar = new Button("Confirmar compra");

    public CestaView(Contexto ctx, Runnable alCambiar, Runnable alComprar, Consumer<String> abrirRastreo) {
        this.ctx = ctx;
        this.alCambiar = alCambiar;
        this.alComprar = alComprar;
        this.abrirRastreo = abrirRastreo;
        metodo.getItems().addAll(PagosApi.METODOS);
        metodo.getSelectionModel().selectFirst();
        total.getStyleClass().add("total");
        confirmar.getStyleClass().add("primario");
        confirmar.setOnAction(e -> confirmar());
        Button vaciar = new Button("Vaciar cesta");
        vaciar.setOnAction(e -> { ctx.cesta.vaciar(); alCambiar.run(); });
        Label aviso = new Label("Pago simulado: no se solicitan datos bancarios.");
        aviso.getStyleClass().add("estado");
        VBox pie = new VBox(6, subtotal, envio, total, new HBox(8, new Label("Método de pago:"), metodo), aviso,
                new HBox(8, confirmar, vaciar), estado);
        pie.setPadding(new Insets(12));
        ScrollPane sp = new ScrollPane(filas);
        sp.setFitToWidth(true);
        filas.setPadding(new Insets(12));
        setCenter(sp);
        setBottom(pie);
        refrescar();
    }

    public void refrescar() {
        filas.getChildren().clear();
        if (ctx.cesta.vacia()) filas.getChildren().add(new Label("Tu cesta está vacía. Agrega libros desde el catálogo."));
        for (Cesta.Item i : ctx.cesta.items()) {
            Label t = new Label(i.libro().titulo());
            t.setWrapText(true);
            t.setPrefWidth(300);
            Label pu = new Label("$" + i.libro().precio().toPlainString());
            pu.setPrefWidth(80);
            Spinner<Integer> sp = new Spinner<>(1, Math.max(1, i.libro().stock()), i.cantidad());
            sp.setPrefWidth(80);
            sp.valueProperty().addListener((o, a, n) -> {
                try { ctx.cesta.cambiarCantidad(i.libro().isbn(), n); } catch (IllegalStateException ex) { Dialogos.error(ex.getMessage()); }
                alCambiar.run();
            });
            Label imp = new Label("$" + i.importe().toPlainString());
            imp.setPrefWidth(90);
            Button q = new Button("Quitar");
            q.setOnAction(e -> { ctx.cesta.quitar(i.libro().isbn()); alCambiar.run(); });
            HBox fila = new HBox(12, t, pu, sp, imp, q);
            fila.setAlignment(Pos.CENTER_LEFT);
            fila.getStyleClass().add("fila");
            filas.getChildren().add(fila);
        }
        subtotal.setText("Subtotal: $" + ctx.cesta.subtotal().toPlainString());
        envio.setText("Envío: $" + Cesta.ENVIO.toPlainString() + " (gratis)");
        total.setText("Total: $" + ctx.cesta.total().toPlainString() + " MXN");
        confirmar.setDisable(ctx.cesta.vacia());
    }

    private void confirmar() {
        confirmar.setDisable(true);
        estado.setText("Validando libros y precios con el catálogo...");
        ctx.async(() -> ctx.compra.validar(ctx.cesta), cambios -> {
            refrescar();
            if (!cambios.isEmpty()) {
                estado.setText("");
                Dialogos.info("La cesta cambió", "Actualizamos tu cesta con datos vigentes:\n\n• " + String.join("\n• ", cambios)
                        + "\n\nRevisa y confirma de nuevo.");
                alCambiar.run();
                return;
            }
            if (!Dialogos.confirmar("Confirmar compra", "Total: $" + ctx.cesta.total().toPlainString() + " MXN\nMétodo: "
                    + metodo.getValue() + " (simulado)\n\n¿Realizar la compra?")) { refrescar(); estado.setText(""); return; }
            estado.setText("Creando pedido y registrando pago...");
            ctx.async(() -> ctx.compra.comprar(ctx.cesta, metodo.getValue()), this::exito, msg -> {
                estado.setText("");
                refrescar();
                Dialogos.error("No se pudo completar la compra: " + msg);
            });
        }, msg -> { estado.setText(""); refrescar(); Dialogos.error(msg); });
    }

    private void exito(CompraService.Resultado r) {
        String codigo = CodigoRastreo.generar(r.pedido().idPedido(), r.pedido().fecha());
        estado.setText("");
        alCambiar.run();
        alComprar.run();
        Alert a = new Alert(Alert.AlertType.INFORMATION);
        a.setHeaderText("¡Compra confirmada!");
        a.setContentText("Pedido #" + r.pedido().idPedido() + " · estado: " + r.pedido().estado() + "\nPago #" + r.pago().idPago()
                + " por $" + r.pago().monto().toPlainString() + " (" + r.pago().metodo() + ")\n\nCódigo de rastreo:\n" + codigo);
        ButtonType rastrear = new ButtonType("Rastrear pedido");
        a.getButtonTypes().setAll(rastrear, ButtonType.CLOSE);
        a.showAndWait().filter(b -> b == rastrear).ifPresent(b -> abrirRastreo.accept(codigo));
    }
}
