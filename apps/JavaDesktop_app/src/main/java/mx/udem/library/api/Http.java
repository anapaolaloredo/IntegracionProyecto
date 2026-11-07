package mx.udem.library.api;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import mx.udem.library.session.Sesion;

import java.io.IOException;
import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.time.Duration;

/**
 * Cliente HTTP unico. Si hay sesion, toda llamada protegida lleva "Authorization: Bearer <token>".
 * Ante un 401 intenta UNA renovacion con el refresh token (POST /session/refresh); si tambien
 * falla lanza SesionExpiradaException para que la interfaz pida iniciar sesion otra vez.
 */
public class Http {
    public static final ObjectMapper JSON = new ObjectMapper();

    private final HttpClient cliente = HttpClient.newBuilder().connectTimeout(Duration.ofSeconds(8)).build();
    private final Endpoints endpoints;
    private volatile Sesion sesion;

    public Http(Endpoints endpoints) { this.endpoints = endpoints; }

    public Endpoints endpoints() { return endpoints; }
    public Sesion sesion() { return sesion; }
    public void setSesion(Sesion s) { this.sesion = s; }

    public record Respuesta(int status, String cuerpo) {
        public JsonNode json() {
            try { return JSON.readTree(cuerpo); } catch (IOException e) { throw new ApiException(status, "Respuesta no es JSON."); }
        }
    }

    /** Llamada sin token (login, catalogo publico). */
    public String publico(String metodo, String url, Object cuerpo) {
        return comprobar(enviar(metodo, url, cuerpo, null)).cuerpo();
    }

    /** Llamada sin token cuya respuesta es JSON. */
    public JsonNode publicoJson(String metodo, String url) {
        try {
            return JSON.readTree(publico(metodo, url, null));
        } catch (IOException e) {
            throw new ApiException(0, "Respuesta no es JSON.");
        }
    }

    /** Llamada protegida con JWT. */
    public JsonNode protegido(String metodo, String url, Object cuerpo) {
        if (sesion == null) throw new SesionExpiradaException("No hay sesion iniciada.");
        Respuesta r = enviar(metodo, url, cuerpo, sesion.accessToken());
        if (r.status() == 401 && renovar()) r = enviar(metodo, url, cuerpo, sesion.accessToken());
        if (r.status() == 401) throw new SesionExpiradaException("Tu sesion expiro o ya no es valida. Inicia sesion de nuevo.");
        comprobar(r);
        return r.cuerpo().isBlank() ? JSON.createObjectNode() : r.json();
    }

    private boolean renovar() {
        try {
            if (sesion.refreshToken() == null) return false;
            Respuesta r = enviar("POST", endpoints.login() + "/session/refresh?format=json",
                    java.util.Map.of("refresh_token", sesion.refreshToken()), null);
            if (r.status() != 200) return false;
            sesion.actualizarAcceso(r.json().path("session_token").asText());
            return true;
        } catch (RuntimeException e) {
            return false;
        }
    }

    public Respuesta enviar(String metodo, String url, Object cuerpo, String token) {
        try {
            HttpRequest.Builder b = HttpRequest.newBuilder(URI.create(url)).timeout(Duration.ofSeconds(20))
                    .header("Accept", "application/json, application/xml");
            if (token != null) b.header("Authorization", "Bearer " + token);
            if (cuerpo != null) {
                b.header("Content-Type", "application/json");
                b.method(metodo, HttpRequest.BodyPublishers.ofString(JSON.writeValueAsString(cuerpo)));
            } else {
                b.method(metodo, HttpRequest.BodyPublishers.noBody());
            }
            HttpResponse<String> r = cliente.send(b.build(), HttpResponse.BodyHandlers.ofString());
            return new Respuesta(r.statusCode(), r.body());
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
            throw new ApiException(0, "Operacion interrumpida.");
        } catch (IOException | IllegalArgumentException e) {
            throw new ApiException(0, "No se pudo conectar con " + url.replaceAll("^(https?://[^/]+).*", "$1") + ".");
        }
    }

    private Respuesta comprobar(Respuesta r) {
        if (r.status() >= 400) throw new ApiException(r.status(), mensajeDeError(r));
        return r;
    }

    static String mensajeDeError(Respuesta r) {
        try {
            JsonNode n = JSON.readTree(r.cuerpo());
            for (String campo : new String[]{"mensaje", "error", "message", "detalle"}) {
                if (n.hasNonNull(campo)) return n.get(campo).asText();
            }
        } catch (Exception ignorado) {
            // el cuerpo no era JSON (p. ej. XML de error)
        }
        String texto = r.cuerpo() == null ? "" : r.cuerpo().replaceAll("<[^>]+>", " ").replaceAll("\\s+", " ").trim();
        return texto.isEmpty() ? "Error HTTP " + r.status() : texto;
    }
}
