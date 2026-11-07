package mx.udem.library.session;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;

import java.nio.charset.StandardCharsets;
import java.util.Base64;

/** Tokens JWT de la sesion y los claims que el servicio login pone dentro (user_id, role_id, exp). */
public final class Sesion {
    public static final int ROL_ADMIN = 1;
    private static final ObjectMapper OM = new ObjectMapper();

    private String accessToken;
    private String refreshToken;
    private long userId;
    private int roleId;
    private long expEpoch;

    public Sesion(String accessToken, String refreshToken) {
        this.refreshToken = refreshToken;
        actualizarAcceso(accessToken);
    }

    /** Lee el payload SIN verificar la firma (el cliente no tiene el secreto; la verifica cada servicio). */
    public static JsonNode payload(String jwt) {
        try {
            String[] partes = jwt.split("\\.");
            if (partes.length != 3) throw new IllegalArgumentException("no es un JWT");
            return OM.readTree(Base64.getUrlDecoder().decode(partes[1].getBytes(StandardCharsets.UTF_8)));
        } catch (Exception e) {
            throw new IllegalArgumentException("Token JWT ilegible.", e);
        }
    }

    public synchronized void actualizarAcceso(String nuevoToken) {
        JsonNode p = payload(nuevoToken);
        this.accessToken = nuevoToken;
        this.userId = p.path("user_id").asLong();
        this.roleId = p.path("role_id").asInt();
        this.expEpoch = p.path("exp").asLong();
    }

    public synchronized String accessToken() { return accessToken; }
    public synchronized String refreshToken() { return refreshToken; }
    public synchronized long userId() { return userId; }
    public synchronized int roleId() { return roleId; }
    public synchronized boolean esAdmin() { return roleId == ROL_ADMIN; }
    public synchronized boolean expirado() { return System.currentTimeMillis() / 1000 >= expEpoch; }
}
