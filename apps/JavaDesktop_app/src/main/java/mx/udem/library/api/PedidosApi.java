package mx.udem.library.api;

import com.fasterxml.jackson.databind.JsonNode;
import mx.udem.library.cart.Cesta;
import mx.udem.library.model.Pedido;

import java.math.BigDecimal;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;

/** Servicio pedidos: POST/GET /api/pedidos, GET /api/pedidos/<id>, PATCH /api/pedidos/<id>/estado. */
public class PedidosApi {
    private final Http http;

    public PedidosApi(Http http) { this.http = http; }

    private String base() { return http.endpoints().pedidos() + "/api/pedidos"; }

    public Pedido crear(Cesta cesta) {
        List<Map<String, Object>> lineas = new ArrayList<>();
        for (Cesta.Item i : cesta.items()) {
            if (i.libro().idLibro() <= 0) throw new ApiException(0, "El catalogo no entrego id_libro de \"" + i.libro().titulo() + "\".");
            lineas.add(Map.of("id_libro", i.libro().idLibro(), "cantidad", i.cantidad()));
        }
        return aPedido(http.protegido("POST", base(), Map.of("lineas", lineas)));
    }

    public List<Pedido> listar() {
        List<Pedido> r = new ArrayList<>();
        for (JsonNode n : http.protegido("GET", base(), null)) r.add(aPedido(n));
        return r;
    }

    public Pedido obtener(long id) { return aPedido(http.protegido("GET", base() + "/" + id, null)); }

    public void cambiarEstado(long id, String estado) {
        http.protegido("PATCH", base() + "/" + id + "/estado", Map.of("estado", estado));
    }

    static Pedido aPedido(JsonNode n) {
        List<Pedido.Linea> lineas = new ArrayList<>();
        for (JsonNode l : n.path("lineas"))
            lineas.add(new Pedido.Linea(l.path("id_libro").asLong(), l.path("isbn").asText(), l.path("titulo").asText(),
                    l.path("cantidad").asInt(), decimal(l.path("precio_unitario"))));
        return new Pedido(n.path("id_pedido").asLong(), n.path("id_cuenta").asLong(), n.path("estado").asText(),
                decimal(n.path("total")), n.path("fecha_creacion").asText(), lineas);
    }

    /** Flask serializa Decimal como texto; acepta numero o texto. */
    static BigDecimal decimal(JsonNode n) {
        return n.isMissingNode() || n.isNull() ? BigDecimal.ZERO : new BigDecimal(n.asText());
    }
}
