package mx.udem.library.api;

/**
 * Direcciones de los servicios a partir de UN solo host (IP o dominio de la instancia de GCP,
 * que cambia en cada sesion). Los puertos son los de apps/services/run_all.sh.
 */
public record Endpoints(String host) {
    public static final int P_LOGIN = 5000, P_LIBROS = 5001, P_USERS = 5002, P_AUTHORS = 5003,
            P_PEDIDOS = 5004, P_PAGOS = 5005, P_RASTREO = 5006;

    public static Endpoints desdeTexto(String texto) {
        String h = texto == null ? "" : texto.trim().replaceFirst("^(?i)(https?|wss?)://", "");
        h = h.replaceAll("[/:].*$", "");
        if (h.isEmpty()) throw new IllegalArgumentException("Escribe la IP o dominio del servidor.");
        return new Endpoints(h);
    }

    private String http(int puerto) { return "http://" + host + ":" + puerto; }

    public String login() { return http(P_LOGIN); }
    public String libros() { return http(P_LIBROS); }
    public String users() { return http(P_USERS); }
    public String authors() { return http(P_AUTHORS); }
    public String pedidos() { return http(P_PEDIDOS); }
    public String pagos() { return http(P_PAGOS); }
    public String rastreoWs() { return "ws://" + host + ":" + P_RASTREO + "/ws/rastreo"; }
}
