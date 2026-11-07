package mx.udem.library.api;

import com.fasterxml.jackson.databind.JsonNode;
import mx.udem.library.session.Sesion;

import java.util.Map;

/** Servicio login tal como esta: POST /login (envia codigo 2FA) y POST /login/verify (entrega los JWT). */
public class AuthApi {
    private final Http http;

    public AuthApi(Http http) { this.http = http; }

    /** Paso 1: valida correo y contrasena; el servidor envia un codigo al buzon de la instancia. */
    public void iniciarLogin(String email, String password) {
        http.publico("POST", http.endpoints().login() + "/login?format=json", Map.of("email", email, "password", password));
    }

    /** Paso 2: canjea el codigo por session_token (30 min) y refresh_token (7 dias). */
    public Sesion verificar(String email, String codigo) {
        String cuerpo = http.publico("POST", http.endpoints().login() + "/login/verify?format=json",
                Map.of("email", email, "codigo", codigo.trim()));
        try {
            JsonNode n = Http.JSON.readTree(cuerpo);
            Sesion s = new Sesion(n.path("session_token").asText(), n.path("refresh_token").asText(null));
            http.setSesion(s);
            return s;
        } catch (Exception e) {
            throw new ApiException(0, "Respuesta de login inesperada.");
        }
    }

    public void cerrarSesion() {
        try {
            http.protegido("POST", http.endpoints().login() + "/logout?format=json", null);
        } catch (RuntimeException ignorado) {
            // si el token ya estaba vencido, la sesion queda cerrada igual
        } finally {
            http.setSesion(null);
        }
    }
}
