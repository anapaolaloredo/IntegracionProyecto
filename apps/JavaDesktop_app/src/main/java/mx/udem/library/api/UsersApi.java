package mx.udem.library.api;

import com.fasterxml.jackson.databind.JsonNode;
import mx.udem.library.model.Usuario;

public class UsersApi {
    private final Http http;

    public UsersApi(Http http) { this.http = http; }

    /** GET /api/users/<id>: el servicio permite al usuario ver SU propio registro (admin ve cualquiera). */
    public Usuario perfil(long idUsuario) {
        JsonNode n = http.protegido("GET", http.endpoints().users() + "/api/users/" + idUsuario, null);
        return new Usuario(n.path("id_usuario").asLong(idUsuario), n.path("correo").asText(), n.path("nombre").asText(),
                n.path("apellido_paterno").asText(), n.path("apellido_materno").asText(""), n.path("rol").asText());
    }
}
