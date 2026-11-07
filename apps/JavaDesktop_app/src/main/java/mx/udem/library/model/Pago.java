package mx.udem.library.model;

import java.math.BigDecimal;

public record Pago(long idPago, long idPedido, BigDecimal monto, String metodo, String fecha) {}
