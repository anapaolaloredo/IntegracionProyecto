package mx.udem.library.model;

public record Usuario(long idUsuario, String correo, String nombre, String apellidoPaterno, String apellidoMaterno, String rol) {
    public String nombreCompleto() {
        return (nombre + " " + apellidoPaterno + " " + (apellidoMaterno == null ? "" : apellidoMaterno)).trim();
    }
}
