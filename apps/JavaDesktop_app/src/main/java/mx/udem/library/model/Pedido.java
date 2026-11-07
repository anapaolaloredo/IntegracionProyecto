package mx.udem.library.model;

import java.math.BigDecimal;
import java.util.List;

public record Pedido(long idPedido, long idCuenta, String estado, BigDecimal total, String fecha, List<Linea> lineas) {
    public record Linea(long idLibro, String isbn, String titulo, int cantidad, BigDecimal precioUnitario) {
        public BigDecimal importe() { return precioUnitario.multiply(BigDecimal.valueOf(cantidad)); }
    }
}
