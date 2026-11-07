package mx.udem.library.ui;

import javafx.application.Platform;
import mx.udem.library.api.*;
import mx.udem.library.cart.Cesta;
import mx.udem.library.tracking.ClienteRastreo;

import java.util.function.Consumer;
import java.util.function.Supplier;

/** Todo lo que comparten las pantallas despues del login. */
public class Contexto {
    public final Http http;
    public final AuthApi auth;
    public final UsersApi users;
    public final BooksApi libros;
    public final AuthorsApi autores;
    public final PedidosApi pedidos;
    public final PagosApi pagos;
    public final CompraService compra;
    public final Cesta cesta = new Cesta();
    public final ClienteRastreo rastreo = new ClienteRastreo();
    private final Runnable alExpirar;

    public Contexto(Http http, Runnable alExpirar) {
        this.http = http;
        this.alExpirar = alExpirar;
        auth = new AuthApi(http);
        users = new UsersApi(http);
        libros = new BooksApi(http);
        autores = new AuthorsApi(http);
        pedidos = new PedidosApi(http);
        pagos = new PagosApi(http);
        compra = new CompraService(libros, pedidos, pagos);
    }

    /** Ejecuta `trabajo` fuera del hilo de la interfaz y entrega el resultado (o el error) dentro de el. */
    public <T> void async(Supplier<T> trabajo, Consumer<T> ok, Consumer<String> error) {
        Thread t = new Thread(() -> {
            try {
                T r = trabajo.get();
                Platform.runLater(() -> ok.accept(r));
            } catch (SesionExpiradaException e) {
                Platform.runLater(() -> { rastreo.cerrar(); http.setSesion(null); alExpirar.run(); });
            } catch (RuntimeException e) {
                Platform.runLater(() -> error.accept(e.getMessage() == null ? e.toString() : e.getMessage()));
            }
        }, "api");
        t.setDaemon(true);
        t.start();
    }
}
