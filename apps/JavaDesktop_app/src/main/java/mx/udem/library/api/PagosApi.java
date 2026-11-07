package mx.udem.library.api;

import com.fasterxml.jackson.databind.JsonNode;
import mx.udem.library.model.Pago;

import java.util.ArrayList;
import java.util.List;
import java.util.Map;

/** Servicio pagos. Pago SIMULADO: solo se envia id_pedido y metodo; nunca datos bancarios. */
public class PagosApi {
    public static final List<String> METODOS = List.of("tarjeta", "transferencia", "efectivo");
    private final Http http;

    public PagosApi(Http http) { this.http = http; }

    private String base() { return http.endpoints().pagos() + "/api/pagos"; }

    public Pago pagar(long idPedido, String metodo) {
        return aPago(http.protegido("POST", base(), Map.of("id_pedido", idPedido, "metodo", metodo)));
    }

    public List<Pago> listar() {
        List<Pago> r = new ArrayList<>();
        for (JsonNode n : http.protegido("GET", base(), null)) r.add(aPago(n));
        return r;
    }

    static Pago aPago(JsonNode n) {
        return new Pago(n.path("id_pago").asLong(), n.path("id_pedido").asLong(), PedidosApi.decimal(n.path("monto")),
                n.path("metodo").asText(), n.path("fecha_pago").asText());
    }
}
