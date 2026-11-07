package mx.udem.library.api;

/** El JWT expiro, fue revocado o es invalido y no se pudo renovar: hay que autenticarse de nuevo. */
public class SesionExpiradaException extends RuntimeException {
    public SesionExpiradaException(String mensaje) { super(mensaje); }
}
