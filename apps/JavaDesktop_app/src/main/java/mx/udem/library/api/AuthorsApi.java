package mx.udem.library.api;

import com.fasterxml.jackson.databind.JsonNode;
import mx.udem.library.model.Autor;

import java.util.ArrayList;
import java.util.List;
import java.util.Optional;

/** Servicio authors (publico): GET /api/authors y GET /api/authors/<id> (con sus libros). */
public class AuthorsApi {
    private final Http http;

    public AuthorsApi(Http http) { this.http = http; }

    public Optional<Autor> buscarPorNombre(String nombre) {
        JsonNode lista = http.publicoJson("GET", http.endpoints().authors() + "/api/authors");
        for (JsonNode a : lista) {
            if (a.path("nombre_autor").asText().equalsIgnoreCase(nombre.trim())) return Optional.of(detalle(a.path("id_autor").asLong()));
        }
        return Optional.empty();
    }

    public Autor detalle(long idAutor) {
        JsonNode n = http.publicoJson("GET", http.endpoints().authors() + "/api/authors/" + idAutor);
        List<String> libros = new ArrayList<>();
        for (JsonNode l : n.path("libros")) libros.add(l.path("titulo").asText());
        return new Autor(idAutor, n.path("nombre_autor").asText(), libros);
    }
}
