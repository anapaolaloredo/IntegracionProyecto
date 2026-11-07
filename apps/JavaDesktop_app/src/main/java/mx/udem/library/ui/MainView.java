package mx.udem.library.ui;

import javafx.geometry.Insets;
import javafx.geometry.Pos;
import javafx.scene.Parent;
import javafx.scene.control.*;
import javafx.scene.layout.*;

/** Ventana principal tras autenticarse: pestanas + barra superior con el usuario y "Cerrar sesion". */
public class MainView {
    private final BorderPane raiz = new BorderPane();
    private final Contexto ctx;
    private final Tab tabCesta = new Tab("Cesta");
    private final TabPane tabs = new TabPane();
    private final Label usuario = new Label("Usuario #");
    private final RastreoView rastreo;
    private final CestaView cesta;
    private final ComprasView compras;
    private final Tab tabRastreo = new Tab("Rastrear pedido");
    private final Tab tabCompras = new Tab("Mis compras");

    public MainView(Contexto ctx, Runnable alCerrarSesion) {
        this.ctx = ctx;
        rastreo = new RastreoView(ctx);
        compras = new ComprasView(ctx, this::irARastreo);
        cesta = new CestaView(ctx, this::actualizarCesta, compras::cargar, this::irARastreo);
        CatalogoView catalogo = new CatalogoView(ctx, this::actualizarCesta);
        PerfilView perfil = new PerfilView(ctx, u -> usuario.setText(u.nombreCompleto() + " · " + u.rol()));

        Tab tabCatalogo = new Tab("Catálogo", catalogo);
        tabCesta.setContent(cesta);
        tabCompras.setContent(compras);
        tabRastreo.setContent(rastreo);
        Tab tabPerfil = new Tab("Perfil", perfil);
        tabs.getTabs().addAll(tabCatalogo, tabCesta, tabCompras, tabRastreo, tabPerfil);
        tabs.getTabs().forEach(t -> t.setClosable(false));
        tabs.getSelectionModel().selectedItemProperty().addListener((o, a, t) -> {
            if (t == tabCompras) compras.cargar();
            if (t == tabCesta) cesta.refrescar();
        });

        Label marca = new Label("Library");
        marca.getStyleClass().add("marca");
        usuario.setText("Usuario #" + ctx.http.sesion().userId());
        Region espacio = new Region();
        HBox.setHgrow(espacio, Priority.ALWAYS);
        Button salir = new Button("Cerrar sesión");
        salir.setOnAction(e -> {
            rastreo.detener();
            ctx.async(() -> { ctx.auth.cerrarSesion(); return true; }, ok -> alCerrarSesion.run(), m -> alCerrarSesion.run());
        });
        HBox barra = new HBox(12, marca, espacio, usuario, salir);
        barra.setAlignment(Pos.CENTER_LEFT);
        barra.setPadding(new Insets(10, 16, 10, 16));
        barra.getStyleClass().add("barra");
        raiz.setTop(barra);
        raiz.setCenter(tabs);
        actualizarCesta();
    }

    public Parent vista() { return raiz; }

    private void actualizarCesta() {
        tabCesta.setText("Cesta (" + ctx.cesta.unidades() + ")");
        cesta.refrescar();
    }

    private void irARastreo(String codigo) {
        tabs.getSelectionModel().select(tabRastreo);
        rastreo.rastrear(codigo);
    }
}
