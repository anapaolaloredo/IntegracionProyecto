package mx.udem.library.tracking;

import java.util.regex.Matcher;
import java.util.regex.Pattern;

/** LIB-MTY-<anio>-<id_pedido a 6 digitos>. Es el mismo formato que valida tracking_server/tracking.py. */
public final class CodigoRastreo {
    private static final Pattern FORMATO = Pattern.compile("^LIB-MTY-(\\d{4})-(\\d{6})$");
    private static final Pattern ANIO = Pattern.compile("\\b(20\\d{2})\\b");

    private CodigoRastreo() {}

    public static String generar(long idPedido, String fechaCreacion) {
        Matcher m = ANIO.matcher(fechaCreacion == null ? "" : fechaCreacion);
        int anio = m.find() ? Integer.parseInt(m.group(1)) : java.time.Year.now().getValue();
        return String.format("LIB-MTY-%04d-%06d", anio, idPedido);
    }

    public static boolean valido(String codigo) {
        return codigo != null && FORMATO.matcher(codigo.trim().toUpperCase()).matches();
    }

    public static String normalizar(String codigo) { return codigo == null ? "" : codigo.trim().toUpperCase(); }
}
