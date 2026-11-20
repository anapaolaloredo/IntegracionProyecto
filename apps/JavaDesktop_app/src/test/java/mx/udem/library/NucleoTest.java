package mx.udem.library;

import mx.udem.library.api.BooksApi;
import mx.udem.library.api.Endpoints;
import mx.udem.library.cart.Cesta;
import mx.udem.library.model.Libro;
import mx.udem.library.session.Sesion;
import mx.udem.library.tracking.CodigoRastreo;
import org.junit.jupiter.api.Test;

import java.math.BigDecimal;
import java.nio.charset.StandardCharsets;
import java.util.Base64;
import java.util.List;

import static org.junit.jupiter.api.Assertions.*;

class NucleoTest {
    static final String XML = """
            <?xml version='1.0' encoding='utf-8'?>
            <library>
              <book isbn="9780000000001" id_libro="7"><title>Don Quijote &amp; Sancho</title>
                <authors><author>Cervantes</author></authors><publicationYear>1605</publicationYear>
                <genres><genre>Novela</genre></genres><price currency="MXN">199.50</price><stock>3</stock>
                <format>Tapa dura</format>
                <images><image cover="false">http://x/b.jpg</image><image cover="true" alt="Portada">http://x/a.jpg</image></images>
                <concepts><concept name="Idealismo"><definition>Lucha contra molinos</definition></concept></concepts>
              </book>
              <book isbn="9780000000002"><title>Sin nada</title><authors/><publicationYear/><genres/>
                <price currency="MXN">10</price><stock>0</stock><format>E</format><images/><concepts/></book>
            </library>""";

    static Libro libro(String isbn, String precio, int stock) {
        return new Libro(1, isbn, "T" + isbn, List.of(), "", List.of(), new BigDecimal(precio), stock, "", List.of(), List.of());
    }

    @Test void parseaCatalogoXml() {
        List<Libro> l = BooksApi.parsear(XML);
        assertEquals(2, l.size());
        Libro q = l.get(0);
        assertEquals(7, q.idLibro());
        assertEquals("Don Quijote & Sancho", q.titulo());
        assertEquals("http://x/a.jpg", q.portadaUrl());
        assertEquals(new BigDecimal("199.50"), q.precio());
        assertTrue(q.descripcion().contains("molinos"));
        assertNull(l.get(1).portadaUrl());
        assertFalse(l.get(1).disponible());
        assertEquals("Sin descripcion disponible.", l.get(1).descripcion());
    }

    @Test void rechazaXmlConDoctype() {
        assertThrows(RuntimeException.class, () -> BooksApi.parsear("<!DOCTYPE x [<!ENTITY a \"b\">]><library/>"));
    }

    @Test void cestaCalculaYRespetaStock() {
        Cesta c = new Cesta();
        c.agregar(libro("A", "100.00", 2));
        c.agregar(libro("A", "100.00", 2));
        assertThrows(IllegalStateException.class, () -> c.agregar(libro("A", "100.00", 2)));
        c.agregar(libro("B", "50.50", 5));
        assertEquals(3, c.unidades());
        assertEquals(new BigDecimal("250.50"), c.subtotal());
        assertEquals(c.subtotal(), c.total());
        c.cambiarCantidad("B", 4);
        assertEquals(new BigDecimal("402.00"), c.total());
        assertThrows(IllegalStateException.class, () -> c.cambiarCantidad("B", 6));
        c.cambiarCantidad("A", 0);
        assertEquals(1, c.items().size());
        assertThrows(IllegalStateException.class, () -> c.agregar(libro("Z", "1", 0)));
    }

    @Test void revalidacionDetectaCambioDePrecioYStock() {
        Cesta c = new Cesta();
        c.agregar(libro("A", "100.00", 5));
        c.cambiarCantidad("A", 4);
        String cambio = c.actualizarConCatalogo(libro("A", "120.00", 2));
        assertTrue(cambio.contains("100.00 -> $120.00") && cambio.contains("quedan 2"));
        assertEquals(2, c.items().get(0).cantidad());
        assertEquals(new BigDecimal("240.00"), c.total());
        assertNull(c.actualizarConCatalogo(libro("A", "120.00", 2)));
    }

    @Test void codigoDeRastreo() {
        assertEquals("LIB-MTY-2026-000125", CodigoRastreo.generar(125, "Thu, 05 Nov 2026 10:00:00 GMT"));
        assertEquals("LIB-MTY-2026-000007", CodigoRastreo.generar(7, "2026-11-05T10:00:00"));
        assertTrue(CodigoRastreo.valido(" lib-mty-2026-000125 "));
        assertFalse(CodigoRastreo.valido("LIB-MTY-2026-125"));
    }

    @Test void leeClaimsDelJwt() {
        String p = Base64.getUrlEncoder().withoutPadding().encodeToString(
                "{\"user_id\":42,\"role_id\":1,\"exp\":4102444800}".getBytes(StandardCharsets.UTF_8));
        Sesion s = new Sesion("h." + p + ".s", "r");
        assertEquals(42, s.userId());
        assertTrue(s.esAdmin());
        assertFalse(s.expirado());
        String viejo = Base64.getUrlEncoder().withoutPadding().encodeToString(
                "{\"user_id\":1,\"role_id\":2,\"exp\":1000}".getBytes(StandardCharsets.UTF_8));
        assertTrue(new Sesion("h." + viejo + ".s", null).expirado());
    }

    @Test void endpointsNormalizaElHost() {
        assertEquals("http://34.1.2.3:5004", Endpoints.desdeTexto(" http://34.1.2.3:5000/ ").pedidos());
        assertEquals("ws://mi.dominio:5006/ws/rastreo", Endpoints.desdeTexto("mi.dominio").rastreoWs());
        assertThrows(IllegalArgumentException.class, () -> Endpoints.desdeTexto("  "));
    }

    @Test void endpointsEnModoGateway() {
        Endpoints g = Endpoints.desdeTexto("34.1.2.3", true);
        assertEquals("http://34.1.2.3/api/auth", g.login());
        assertEquals("http://34.1.2.3", g.libros());
        assertEquals("http://34.1.2.3", g.pedidos());
        assertEquals("http://34.1.2.3", g.pagos());
        assertEquals("ws://34.1.2.3:8090/ws/rastreo", g.rastreoWs());
    }
}
