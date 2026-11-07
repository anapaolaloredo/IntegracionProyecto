package mx.udem.library.api;

import mx.udem.library.model.Libro;
import org.w3c.dom.Document;
import org.w3c.dom.Element;
import org.w3c.dom.Node;
import org.w3c.dom.NodeList;

import javax.xml.XMLConstants;
import javax.xml.parsers.DocumentBuilderFactory;
import java.io.ByteArrayInputStream;
import java.math.BigDecimal;
import java.net.URLEncoder;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.List;
import java.util.Optional;

/** Catalogo: servicio de libros existente (apps/services/soap). Responde XML, asi que se parsea con DOM. */
public class BooksApi {
    private final Http http;

    public BooksApi(Http http) { this.http = http; }

    public List<Libro> listar() {
        return parsear(http.publico("GET", http.endpoints().libros() + "/api/libros", null));
    }

    public List<Libro> buscarPorTitulo(String titulo) {
        if (titulo == null || titulo.isBlank()) return listar();
        return parsear(http.publico("GET", http.endpoints().libros() + "/api/libros/buscar?titulo="
                + URLEncoder.encode(titulo.trim(), StandardCharsets.UTF_8), null));
    }

    public Optional<Libro> porIsbn(String isbn) {
        try {
            return parsear(http.publico("GET", http.endpoints().libros() + "/api/libros/" + isbn, null)).stream().findFirst();
        } catch (ApiException e) {
            if (e.status() == 404) return Optional.empty();
            throw e;
        }
    }

    public static List<Libro> parsear(String xml) {
        try {
            DocumentBuilderFactory f = DocumentBuilderFactory.newInstance();
            f.setFeature(XMLConstants.FEATURE_SECURE_PROCESSING, true);
            f.setFeature("http://apache.org/xml/features/disallow-doctype-decl", true);
            Document doc = f.newDocumentBuilder().parse(new ByteArrayInputStream(xml.getBytes(StandardCharsets.UTF_8)));
            NodeList nodos = doc.getElementsByTagName("book");
            List<Libro> libros = new ArrayList<>();
            for (int i = 0; i < nodos.getLength(); i++) libros.add(aLibro((Element) nodos.item(i)));
            return libros;
        } catch (Exception e) {
            throw new ApiException(0, "No se pudo leer el XML del catalogo: " + e.getMessage());
        }
    }

    private static Libro aLibro(Element b) {
        long idLibro = 0;
        if (!b.getAttribute("id_libro").isBlank()) idLibro = Long.parseLong(b.getAttribute("id_libro"));
        List<Libro.Imagen> imagenes = new ArrayList<>();
        for (Element e : hijos(hijo(b, "images"), "image"))
            imagenes.add(new Libro.Imagen(e.getTextContent().trim(), "true".equals(e.getAttribute("cover")), e.getAttribute("alt")));
        List<Libro.Concepto> conceptos = new ArrayList<>();
        for (Element e : hijos(hijo(b, "concepts"), "concept"))
            conceptos.add(new Libro.Concepto(e.getAttribute("name"), texto(e, "definition")));
        String precio = texto(b, "price");
        String stock = texto(b, "stock");
        return new Libro(idLibro, b.getAttribute("isbn"), texto(b, "title"), lista(b, "authors", "author"),
                texto(b, "publicationYear"), lista(b, "genres", "genre"),
                precio.isBlank() ? BigDecimal.ZERO : new BigDecimal(precio), stock.isBlank() ? 0 : Integer.parseInt(stock),
                texto(b, "format"), imagenes, conceptos);
    }

    private static Element hijo(Element padre, String nombre) {
        if (padre == null) return null;
        for (Node n = padre.getFirstChild(); n != null; n = n.getNextSibling())
            if (n instanceof Element e && e.getTagName().equals(nombre)) return e;
        return null;
    }

    private static List<Element> hijos(Element padre, String nombre) {
        List<Element> r = new ArrayList<>();
        if (padre == null) return r;
        for (Node n = padre.getFirstChild(); n != null; n = n.getNextSibling())
            if (n instanceof Element e && e.getTagName().equals(nombre)) r.add(e);
        return r;
    }

    private static String texto(Element padre, String nombre) {
        Element e = hijo(padre, nombre);
        return e == null ? "" : e.getTextContent().trim();
    }

    private static List<String> lista(Element padre, String contenedor, String item) {
        List<String> r = new ArrayList<>();
        for (Element e : hijos(hijo(padre, contenedor), item)) r.add(e.getTextContent().trim());
        return r;
    }
}
