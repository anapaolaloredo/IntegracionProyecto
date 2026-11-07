package mx.udem.library.api;

/** Error devuelto por un microservicio (status HTTP + mensaje legible). */
public class ApiException extends RuntimeException {
    private final int status;

    public ApiException(int status, String mensaje) {
        super(mensaje);
        this.status = status;
    }

    public int status() { return status; }
}
