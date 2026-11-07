package mx.udem.library.model;

import java.math.BigDecimal;
import java.util.List;
import java.util.stream.Collectors;

/** Libro del catalogo (XML del servicio de libros). El servicio no trae "descripcion": se arma con los conceptos. */
public record Libro(long idLibro, String isbn, String titulo, List<String> autores, String anio, List<String> generos,
                    BigDecimal precio, int stock, String formato, List<Imagen> imagenes, List<Concepto> conceptos) {

    public record Imagen(String url, boolean portada, String alt) {}
    public record Concepto(String nombre, String definicion) {}

    public String portadaUrl() {
        return imagenes.stream().filter(Imagen::portada).findFirst()
                .or(() -> imagenes.stream().findFirst()).map(Imagen::url).orElse(null);
    }

    public String descripcion() {
        if (conceptos.isEmpty()) return "Sin descripcion disponible.";
        return conceptos.stream().map(c -> c.nombre() + ": " + c.definicion()).collect(Collectors.joining("\n\n"));
    }

    public String autoresTexto() { return autores.isEmpty() ? "Autor desconocido" : String.join(", ", autores); }
    public boolean disponible() { return stock > 0; }
}
