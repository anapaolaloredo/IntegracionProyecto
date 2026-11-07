package mx.udem.library.api;

import mx.udem.library.cart.Cesta;
import mx.udem.library.model.Libro;
import mx.udem.library.model.Pago;
import mx.udem.library.model.Pedido;

import java.util.ArrayList;
import java.util.List;

/** Flujo de compra: revalidar cesta -> crear pedido -> pago simulado -> consultar resultado. */
public class CompraService {
    public record Resultado(Pedido pedido, Pago pago) {}

    private final BooksApi libros;
    private final PedidosApi pedidos;
    private final PagosApi pagos;

    public CompraService(BooksApi libros, PedidosApi pedidos, PagosApi pagos) {
        this.libros = libros;
        this.pedidos = pedidos;
        this.pagos = pagos;
    }

    /** Compara cada item con el catalogo vigente. Devuelve los cambios detectados (lista vacia = todo igual). */
    public List<String> validar(Cesta cesta) {
        List<String> cambios = new ArrayList<>();
        for (Cesta.Item item : cesta.items()) {
            Libro actual = libros.porIsbn(item.libro().isbn()).orElse(null);
            if (actual == null) {
                cesta.quitar(item.libro().isbn());
                cambios.add("\"" + item.libro().titulo() + "\" ya no existe en el catalogo y se quito.");
            } else {
                String c = cesta.actualizarConCatalogo(actual);
                if (c != null) cambios.add(c);
            }
        }
        return cambios;
    }

    public Resultado comprar(Cesta cesta, String metodo) {
        Pedido creado = pedidos.crear(cesta);
        Pago pago;
        try {
            pago = pagos.pagar(creado.idPedido(), metodo);
        } catch (RuntimeException e) {
            try { pedidos.cambiarEstado(creado.idPedido(), "cancelado"); } catch (RuntimeException ignorado) { /* ya se informa el fallo del pago */ }
            throw e;
        }
        Pedido final_ = pedidos.obtener(creado.idPedido());
        cesta.vaciar();
        return new Resultado(final_, pago);
    }
}
