package mx.udem.library.ui;

import javafx.geometry.Insets;
import javafx.geometry.Pos;
import javafx.scene.Node;
import javafx.scene.control.*;
import javafx.scene.image.Image;
import javafx.scene.image.ImageView;
import javafx.scene.layout.*;
import mx.udem.library.model.Autor;
import mx.udem.library.model.Libro;

import java.util.List;
import java.util.function.Consumer;

public class CatalogoView extends BorderPane {
    private final Contexto ctx;
    private final Runnable alCambiarCesta;
    private final TextField busqueda = new TextField();
    private final FlowPane tarjetas = new FlowPane(16, 16);
    private final Label estado = new Label();

    public CatalogoView(Contexto ctx, Runnable alCambiarCesta) {
        this.ctx = ctx;
        this.alCambiarCesta = alCambiarCesta;
        busqueda.setPromptText("Buscar por título...");
        busqueda.setPrefColumnCount(28);
        Button buscar = new Button("Buscar");
        Button todos = new Button("Ver todo");
        buscar.setDefaultButton(false);
        buscar.setOnAction(e -> cargar(busqueda.getText()));
        busqueda.setOnAction(e -> cargar(busqueda.getText()));
        todos.setOnAction(e -> { busqueda.clear(); cargar(null); });
        HBox barra = new HBox(8, busqueda, buscar, todos, estado);
        barra.setAlignment(Pos.CENTER_LEFT);
        barra.setPadding(new Insets(12));
        tarjetas.setPadding(new Insets(12));
        ScrollPane scroll = new ScrollPane(tarjetas);
        scroll.setFitToWidth(true);
        setTop(barra);
        setCenter(scroll);
        cargar(null);
    }

    public void cargar(String titulo) {
        estado.setText("Cargando catálogo...");
        ctx.async(() -> ctx.libros.buscarPorTitulo(titulo), libros -> {
            tarjetas.getChildren().setAll(libros.stream().map(this::tarjeta).toList());
            estado.setText(libros.isEmpty() ? "Sin resultados." : libros.size() + " libro(s).");
        }, msg -> estado.setText("No se pudo cargar el catálogo: " + msg));
    }

    static Node portada(Libro l, double w, double h) {
        StackPane caja = new StackPane();
        caja.setPrefSize(w, h); caja.setMinSize(w, h); caja.setMaxSize(w, h);
        Label vacio = new Label("Portada\nno disponible");
        vacio.getStyleClass().add("sin-portada");
        vacio.setWrapText(true);
        vacio.setAlignment(Pos.CENTER);
        vacio.setPrefSize(w, h);
        caja.getChildren().add(vacio);
        String url = l.portadaUrl();
        if (url != null && !url.isBlank()) {
            Image img = new Image(url, w, h, true, true, true);
            ImageView iv = new ImageView(img);
            iv.setFitWidth(w); iv.setFitHeight(h); iv.setPreserveRatio(true);
            img.progressProperty().addListener((o, a, p) -> { if (p.doubleValue() >= 1 && !img.isError()) vacio.setVisible(false); });
            img.errorProperty().addListener((o, a, err) -> { if (err) { iv.setVisible(false); vacio.setVisible(true); } });
            caja.getChildren().add(iv);
        }
        return caja;
    }

    private Node tarjeta(Libro l) {
        Label titulo = new Label(l.titulo());
        titulo.setWrapText(true);
        titulo.getStyleClass().add("tarjeta-titulo");
        Label autor = new Label(l.autoresTexto());
        autor.setWrapText(true);
        Label precio = new Label("$" + l.precio().toPlainString() + " MXN");
        precio.getStyleClass().add("precio");
        Label disp = new Label(l.disponible() ? "Disponible (" + l.stock() + ")" : "Agotado");
        disp.getStyleClass().add(l.disponible() ? "ok" : "agotado");
        Button detalle = new Button("Detalles");
        detalle.setOnAction(e -> detalles(l));
        Button agregar = new Button("Agregar");
        agregar.setDisable(!l.disponible());
        agregar.setOnAction(e -> agregar(l));
        VBox v = new VBox(6, portada(l, 130, 185), titulo, autor, precio, disp, new HBox(6, detalle, agregar));
        v.setPrefWidth(160);
        v.setPadding(new Insets(10));
        v.getStyleClass().add("tarjeta");
        return v;
    }

    private void agregar(Libro l) {
        try {
            ctx.cesta.agregar(l);
            alCambiarCesta.run();
            estado.setText("\"" + l.titulo() + "\" agregado a la cesta.");
        } catch (IllegalStateException e) {
            Dialogos.error(e.getMessage());
        }
    }

    private void detalles(Libro l) {
        Dialog<Void> d = new Dialog<>();
        d.setTitle(l.titulo());
        d.getDialogPane().getButtonTypes().add(ButtonType.CLOSE);
        Label titulo = new Label(l.titulo());
        titulo.getStyleClass().add("detalle-titulo");
        titulo.setWrapText(true);
        HBox autores = new HBox(6, new Label("Autor(es):"));
        for (String a : l.autores()) {
            Hyperlink h = new Hyperlink(a);
            h.setOnAction(e -> infoAutor(a));
            autores.getChildren().add(h);
        }
        Label meta = new Label("ISBN: " + l.isbn() + "   ·   " + l.formato() + "   ·   " + l.anio() + "\nGéneros: " + String.join(", ", l.generos())
                + "\nPrecio: $" + l.precio().toPlainString() + " MXN   ·   " + (l.disponible() ? "Disponibilidad: " + l.stock() + " ejemplares" : "Agotado"));
        Label desc = new Label(l.descripcion());
        desc.setWrapText(true);
        ScrollPane sp = new ScrollPane(desc);
        sp.setFitToWidth(true);
        sp.setPrefHeight(170);
        VBox derecha = new VBox(8, titulo, autores, meta, sp);
        derecha.setPrefWidth(430);
        d.getDialogPane().setContent(new HBox(16, portada(l, 190, 270), derecha));
        d.showAndWait();
    }

    private void infoAutor(String nombre) {
        ctx.async(() -> ctx.autores.buscarPorNombre(nombre), op -> {
            if (op.isEmpty()) { Dialogos.info(nombre, "El servicio de autores no tiene más información."); return; }
            Autor a = op.get();
            Dialogos.info(a.nombre(), "Libros de este autor en la librería:\n\n• " + String.join("\n• ", a.libros()));
        }, Dialogos::error);
    }
}
