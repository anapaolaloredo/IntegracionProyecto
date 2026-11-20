package mx.udem.library.api;

/**
 * Direcciones de los servicios a partir de UN solo host (IP o dominio de la instancia de GCP,
 * que cambia en cada sesion).
 *  - Modo directo: un puerto por servicio (los de apps/services/run_all.sh; rastreo en 5006).
 *  - Modo gateway: todo por el puerto 80 de NGINX (ver deploy/nginx/conf.d/01_reverse_proxy.conf):
 *      /api/auth/* -> login, /api/libros, /api/users, /api/authors, /api/pedidos, /api/pagos; WebSocket en :8090 (03_websocket.conf).
 */
public record Endpoints(String host, boolean gateway) {
    public static final int P_LOGIN = 5000, P_LIBROS = 5001, P_USERS = 5002, P_AUTHORS = 5003,
            P_PEDIDOS = 5004, P_PAGOS = 5005, P_RASTREO = 5006,
            P_WS_GATEWAY = 8090; // WebSockets exclusivos de NGINX (03_websocket.conf)

    public static Endpoints desdeTexto(String texto) { return desdeTexto(texto, false); }

    public static Endpoints desdeTexto(String texto, boolean gateway) {
        String h = texto == null ? "" : texto.trim().replaceFirst("^(?i)(https?|wss?)://", "");
        h = h.replaceAll("[/:].*$", "");
        if (h.isEmpty()) throw new IllegalArgumentException("Escribe la IP o dominio del servidor.");
        return new Endpoints(h, gateway);
    }

    private String http(int puerto) { return gateway ? "http://" + host : "http://" + host + ":" + puerto; }

    public String login() { return gateway ? "http://" + host + "/api/auth" : http(P_LOGIN); }
    public String libros() { return http(P_LIBROS); }
    public String users() { return http(P_USERS); }
    public String authors() { return http(P_AUTHORS); }
    public String pedidos() { return http(P_PEDIDOS); }
    public String pagos() { return http(P_PAGOS); }
    public String rastreoWs() { return gateway ? "ws://" + host + ":" + P_WS_GATEWAY + "/ws/rastreo" : "ws://" + host + ":" + P_RASTREO + "/ws/rastreo"; }
}
