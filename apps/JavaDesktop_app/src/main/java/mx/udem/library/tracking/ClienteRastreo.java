package mx.udem.library.tracking;

import com.fasterxml.jackson.databind.ObjectMapper;

import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.WebSocket;
import java.time.Duration;
import java.util.Map;
import java.util.concurrent.CompletionStage;
import java.util.function.Consumer;

/**
 * WebSocket DESDE Java (java.net.http). Manda el JWT y el codigo en el primer mensaje, recibe las
 * posiciones y las entrega a quien llame; el mapa solo dibuja lo que Java le pasa.
 */
public class ClienteRastreo {
    private static final ObjectMapper OM = new ObjectMapper();
    private volatile WebSocket socket;
    private volatile boolean cerradoPorUsuario;

    public void conectar(String url, String token, String codigo, Consumer<EventoRastreo> alEvento, Consumer<String> alCerrar) {
        cerrar();
        cerradoPorUsuario = false;
        HttpClient.newHttpClient().newWebSocketBuilder().connectTimeout(Duration.ofSeconds(8))
                .buildAsync(URI.create(url), new WebSocket.Listener() {
                    private final StringBuilder parcial = new StringBuilder();

                    @Override public void onOpen(WebSocket ws) {
                        try {
                            ws.sendText(OM.writeValueAsString(Map.of("token", token, "codigo", codigo)), true);
                        } catch (Exception e) {
                            alCerrar.accept("No se pudo enviar la solicitud: " + e.getMessage());
                        }
                        ws.request(1);
                    }

                    @Override public CompletionStage<?> onText(WebSocket ws, CharSequence datos, boolean ultimo) {
                        parcial.append(datos);
                        if (ultimo) {
                            try {
                                alEvento.accept(EventoRastreo.desde(OM.readTree(parcial.toString())));
                            } catch (Exception e) {
                                alCerrar.accept("Mensaje ilegible del servidor de rastreo.");
                            }
                            parcial.setLength(0);
                        }
                        ws.request(1);
                        return null;
                    }

                    @Override public CompletionStage<?> onClose(WebSocket ws, int codigoCierre, String motivo) {
                        if (!cerradoPorUsuario) alCerrar.accept(null);
                        return null;
                    }

                    @Override public void onError(WebSocket ws, Throwable error) {
                        if (!cerradoPorUsuario) alCerrar.accept("Conexion de rastreo interrumpida: " + error.getMessage());
                    }
                }).whenComplete((ws, error) -> {
                    if (error != null) alCerrar.accept("No se pudo conectar al servidor de rastreo (" + url + ").");
                    else socket = ws;
                });
    }

    public void cerrar() {
        cerradoPorUsuario = true;
        WebSocket ws = socket;
        socket = null;
        if (ws != null && !ws.isOutputClosed()) ws.sendClose(WebSocket.NORMAL_CLOSURE, "fin");
    }
}
