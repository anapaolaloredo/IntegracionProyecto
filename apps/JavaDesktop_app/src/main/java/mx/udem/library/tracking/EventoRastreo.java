package mx.udem.library.tracking;

import com.fasterxml.jackson.databind.JsonNode;

import java.util.ArrayList;
import java.util.List;

/** Mensaje del servidor de rastreo: tipo = inicio | posicion | error. */
public record EventoRastreo(String tipo, String mensaje, String estado, double lat, double lng, double progreso,
                            boolean entregado, String destino, List<double[]> ruta) {

    public static EventoRastreo desde(JsonNode n) {
        List<double[]> ruta = new ArrayList<>();
        for (JsonNode p : n.path("ruta")) ruta.add(new double[]{p.get(0).asDouble(), p.get(1).asDouble()});
        return new EventoRastreo(n.path("tipo").asText(), n.path("mensaje").asText(""), n.path("estado").asText(""),
                n.path("lat").asDouble(), n.path("lng").asDouble(), n.path("progreso").asDouble(),
                n.path("entregado").asBoolean(), n.path("destino").asText(""), ruta);
    }
}
