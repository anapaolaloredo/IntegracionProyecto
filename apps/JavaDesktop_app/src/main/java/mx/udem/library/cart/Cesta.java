package mx.udem.library.cart;

import mx.udem.library.model.Libro;

import java.math.BigDecimal;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/** Cesta en memoria. La clave es el ISBN; la cantidad nunca supera el stock conocido. */
public class Cesta {
    public static final BigDecimal ENVIO = BigDecimal.ZERO; // la entrega es gratuita

    public static final class Item {
        private Libro libro;
        private int cantidad;
        Item(Libro libro, int cantidad) { this.libro = libro; this.cantidad = cantidad; }
        public Libro libro() { return libro; }
        public int cantidad() { return cantidad; }
        public BigDecimal importe() { return libro.precio().multiply(BigDecimal.valueOf(cantidad)); }
    }

    private final Map<String, Item> items = new LinkedHashMap<>();

    public void agregar(Libro libro) {
        if (!libro.disponible()) throw new IllegalStateException("\"" + libro.titulo() + "\" no tiene stock.");
        Item existente = items.get(libro.isbn());
        if (existente == null) { items.put(libro.isbn(), new Item(libro, 1)); return; }
        if (existente.cantidad >= libro.stock()) throw new IllegalStateException("Solo hay " + libro.stock() + " ejemplares disponibles.");
        existente.cantidad++;
    }

    public void cambiarCantidad(String isbn, int cantidad) {
        Item i = items.get(isbn);
        if (i == null) return;
        if (cantidad <= 0) { items.remove(isbn); return; }
        if (cantidad > i.libro.stock()) throw new IllegalStateException("Solo hay " + i.libro.stock() + " ejemplares disponibles.");
        i.cantidad = cantidad;
    }

    public void quitar(String isbn) { items.remove(isbn); }
    public void vaciar() { items.clear(); }
    public boolean vacia() { return items.isEmpty(); }
    public List<Item> items() { return new ArrayList<>(items.values()); }
    public int unidades() { return items.values().stream().mapToInt(Item::cantidad).sum(); }

    public BigDecimal subtotal() { return items.values().stream().map(Item::importe).reduce(BigDecimal.ZERO, BigDecimal::add); }
    public BigDecimal total() { return subtotal().add(ENVIO); }

    /** Sustituye el libro por su version recien consultada (precio/stock actuales). Devuelve descripcion del cambio o null. */
    public String actualizarConCatalogo(Libro actual) {
        Item i = items.get(actual.isbn());
        if (i == null) return null;
        StringBuilder cambios = new StringBuilder();
        if (i.libro.precio().compareTo(actual.precio()) != 0)
            cambios.append("precio de \"").append(actual.titulo()).append("\": $").append(i.libro.precio()).append(" -> $").append(actual.precio()).append(". ");
        if (actual.stock() < i.cantidad) {
            cambios.append("stock de \"").append(actual.titulo()).append("\": solo quedan ").append(actual.stock()).append(". ");
            i.cantidad = actual.stock();
            if (i.cantidad == 0) items.remove(actual.isbn());
        }
        i.libro = actual;
        return cambios.isEmpty() ? null : cambios.toString().trim();
    }
}
