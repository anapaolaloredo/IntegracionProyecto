package mx.udem.library.model;

import java.util.List;

public record Autor(long idAutor, String nombre, List<String> libros) {}
