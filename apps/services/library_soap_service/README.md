# library_soap_service

Módulo SOAP independiente para clasificar (IaaS/PaaS/SaaS/FaaS) el catálogo
real de la librería. Se integra por base de datos con el monolito Node.js +
PostgreSQL ya existente (`apps/web-monolito01`), **sin modificar su código
ni su esquema**. Construye y procesa manualmente el SOAP Envelope con
`xml.etree.ElementTree` (no usa Spyne/Zeep/suds del lado del servidor).

## Mapeo de nombres (genérico del ejercicio → real de este proyecto)

| Nombre genérico (PDF) | Tabla/objeto real |
|---|---|
| `books` | `libros` |
| `concepts` | `conceptos` |
| `book_concepts` | `libro_concepto` |
| `categories` | `generos` (vía `libro_genero`) |

## Arquitectura

```
Aplicación de escritorio (Electron)
   │  construye el Envelope (xml.etree en el proceso principal, evita CORS)
   ▼
HTTP POST /soap  (XML)
   ▼
library_soap_service (Flask)
   │  app.py            → HTTP + orquestación de errores
   │  soap/envelope.py  → parseo/armado manual del Envelope
   │  soap/service.py   → lógica de cada operación
   │  soap/faults.py    → SOAP Fault (sin exponer detalle técnico)
   │  soap/security.py  → WS-Security UsernameToken
   │  db/repository.py  → SQL parametrizado (funciones/vistas)
   ▼
PostgreSQL (rol soap_service_user, mínimo privilegio)
   - Lee: libros, conceptos, libro_concepto, generos, libro_genero
   - Escribe: clasificadores, clasificaciones_cloud, clientes_servidos

En paralelo, el monolito Node.js sigue leyendo/escribiendo la misma base
de datos con su propio rol (library_user), de forma completamente
independiente — ninguno de los dos conoce al otro en tiempo de ejecución.
```

## Puesta en marcha

```bash
cd apps/services/library_soap_service
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env
# completar .env con las credenciales de soap_service_user

# 1) Crear las tablas propias + rol de mínimo privilegio (una sola vez,
#    como un rol con permiso para CREATE, p.ej. library_user o postgres):
psql -d library -f sql/soap_module.sql

# 2) Generar el hash de la contraseña WS-Security (no se guarda en texto plano):
python tests/generar_hash_wsse.py "una-contrasena-de-prueba"
# copiar el resultado a SOAP_STATS_PASSWORD_HASH en .env

# 3) Levantar el servicio
python app.py            # sirve en 0.0.0.0:5002 por defecto
```

WSDL: `GET http://<host>:5002/soap?wsdl`
Operaciones: `POST http://<host>:5002/soap` con el Envelope correspondiente.

## Decisiones de ingeniería

Formato: **Necesidad → Decisión → Justificación → Ventajas → Limitaciones**

### 1. Flask / Python
- **Necesidad:** un servidor HTTP ligero, independiente del monolito Node.js, que hable el mismo idioma de base de datos (psycopg2) que el resto del proyecto académico.
- **Decisión:** Flask sin extensiones de generación automática de SOAP.
- **Justificación:** el ejercicio exige construir el Envelope a mano; un framework como Spyne ocultaría justamente el aprendizaje que se busca.
- **Ventajas:** control total del XML, dependencias mínimas, fácil de depurar.
- **Limitaciones:** no hay validación automática contra el XSD ni generación de WSDL en runtime; ambas cosas se hacen a mano (el WSDL es un archivo estático, la validación de campos es código explícito en `soap/service.py`).

### 2. SOAP como protocolo
- **Necesidad:** el ejercicio requiere explícitamente un contrato SOAP/WSDL, no REST.
- **Decisión:** SOAP 1.1 sobre HTTP, estilo document/literal.
- **Justificación:** document/literal es el estilo más interoperable entre pilas SOAP distintas (Java, .NET, Python), evitando RPC/encoded, que es ambiguo y está deprecado en la práctica.
- **Ventajas:** contrato fuertemente tipado, interoperable, con manejo de errores estandarizado (SOAP Fault).
- **Limitaciones:** más verboso que REST/JSON para el mismo dato (ver Tarea 5, métricas).

### 3. WSDL / XSD
- **Necesidad:** un contrato explícito, escrito antes que el código.
- **Decisión:** un único archivo `wsdl/library-classifier.wsdl` con los tipos XSD embebidos (`wsdl:types`), 4 operaciones, un `portType`, un `binding` document/literal y un `service` con el endpoint.
- **Justificación:** mantener contrato y tipos en un solo archivo simplifica la evolución del servicio en un ejercicio académico (frente a separar XSD en archivos `.xsd` independientes, que sería preferible en un proyecto de mayor escala).
- **Ventajas:** un cliente en otro lenguaje (Tarea 4) puede generarse leyendo un solo archivo; el enum `ModeloCloud` impide en el tipo que se envíe un valor fuera de IaaS/PaaS/SaaS/FaaS.
- **Limitaciones:** Flask no valida el XML entrante contra este XSD automáticamente (no se agregó una librería de validación XSD para mantener las dependencias mínimas); por eso `soap/service.py` revalida manualmente los campos obligatorios y el enum.

### 4. Acceso a PostgreSQL
- **Necesidad:** leer datos reales del monolito y escribir las clasificaciones, sin acoplarse a su código Node.js.
- **Decisión:** acceso directo con `psycopg2`, siempre a través de funciones SQL parametrizadas (`sql/soap_module.sql`), nunca SQL concatenado.
- **Justificación:** las funciones encapsulan las reglas de negocio (duplicados, existencia de libro/concepto) en la base de datos, que es donde viven las restricciones (UNIQUE, FK), evitando condiciones de carrera que un `SELECT` + `INSERT` desde Python sí tendría.
- **Ventajas:** transacciones atómicas, reglas de integridad garantizadas por el motor, no solo por la aplicación.
- **Limitaciones:** la lógica queda repartida entre PL/pgSQL y Python; se documenta explícitamente para no perder trazabilidad.

### 5. Tablas propias vs. tablas del monolito
- **Necesidad:** registrar clasificaciones sin tocar el esquema del monolito ni reutilizar su tabla `usuarios`.
- **Decisión:** 3 tablas nuevas (`clasificadores`, `clasificaciones_cloud`, `clientes_servidos`) que referencian `libros`/`conceptos` por FK, más una vista (`vista_conceptos_pendientes`).
- **Justificación:** separar "quién compra libros" (monolito) de "quién clasifica conceptos" (este módulo) son dominios distintos aunque compartan infraestructura; mezclarlos violaría responsabilidad única.
- **Ventajas:** el monolito no ve ni depende de estas tablas; se pueden borrar sin afectarlo.
- **Limitaciones:** hay dos "nociones de usuario" en la misma base de datos (`usuarios` y `clasificadores`) sin relación entre sí — aceptable para este ejercicio, pero un rediseño de producción unificaría identidad.

### 6. Construcción manual del XML
- **Necesidad:** cumplir el requisito explícito de no ocultar el Envelope con un framework.
- **Decisión:** `xml.etree.ElementTree` para leer (`ET.fromstring`) y escribir (`ET.SubElement` + `ET.tostring`) todo el XML, namespaces incluidos.
- **Justificación:** ElementTree escapa automáticamente el texto de cada nodo, evitando inyección de XML por concatenación de strings.
- **Ventajas:** cero dependencias extra, comportamiento predecible, fácil de auditar línea por línea.
- **Limitaciones:** no valida contra el XSD (ver punto 3); tampoco protege contra ataques como "billion laughs" (entidades XML expansivas) — para producción se recomendaría `defusedxml`.

### 7. Autenticación (WS-Security)
- Ver `soap/security.py` — UsernameToken + PasswordText + hash `pbkdf2` (werkzeug) en servidor, en vez de PasswordDigest (que exigiría contraseña reversible en el servidor). Limitación documentada: requiere HTTPS en producción para proteger la contraseña en tránsito.

### 8. Manejo de errores (SOAP Fault)
- **Necesidad:** distinguir errores de entrada, conflictos y errores internos sin texto genérico.
- **Decisión:** jerarquía de excepciones en `soap/faults.py` (`XmlInvalidoFault`, `ValidacionFault`, `NoEncontradoFault`, `ConflictoFault`, `AutenticacionFault`, `ServidorFault`), cada una con `faultcode` SOAP, un `codigo` corto para la GUI y un `http_status` (400/401/404/409/500).
- **Justificación:** combinar el `faultcode` SOAP estándar con un código de negocio propio permite que la GUI reaccione sin parsear texto libre en `faultstring`.
- **Ventajas:** ningún Fault enviado al cliente contiene SQL, rutas o stacktrace; esos detalles solo llegan a `app.logger.exception`.
- **Limitaciones:** usar códigos HTTP distintos de 500 en SOAP 1.1 no es 100% estándar (la especificación original asume 500 para cualquier Fault), pero es una práctica común y documentada que facilita la vida a clientes HTTP genéricos; se explicita aquí como decisión consciente.

### 9. Interoperabilidad
- Ver Tarea 4 (`tests/interop_zeep_client.py`): un cliente Python generado con `zeep` a partir del WSDL, sin conocer la implementación Flask/ElementTree del servidor, consume `ObtenerConceptosPendientes` y `RegistrarClasificacion`.

## Estructura del proyecto

```
library_soap_service/
├── app.py                  # Endpoint HTTP, orquesta errores
├── config/settings.py      # Variables de entorno
├── db/
│   ├── connection.py       # Conexión psycopg2
│   └── repository.py       # SQL parametrizado + errores de negocio
├── soap/
│   ├── envelope.py         # Parseo/armado manual del Envelope
│   ├── service.py          # Lógica de cada operación
│   ├── faults.py           # SOAP Fault
│   └── security.py         # WS-Security UsernameToken
├── wsdl/library-classifier.wsdl
├── sql/soap_module.sql     # Tablas propias, vista, funciones, rol
├── tests/
│   ├── pruebas_manuales.py       # Plan de pruebas P01/P02/N01/N02/N03
│   ├── wsse_demo.py              # Tarea 1: WS-Security ok/incorrecto
│   ├── interop_zeep_client.py    # Tarea 4: interoperabilidad
│   └── generar_hash_wsse.py      # Utilidad para el hash de .env
├── .env.example
├── requirements.txt
└── README.md
```

## Seguridad y mínimo privilegio

`sql/soap_module.sql` crea el rol `soap_service_user` con:
- `SELECT` sobre `libros, conceptos, libro_concepto, generos, libro_genero`.
- `SELECT, INSERT, UPDATE` (nunca `DELETE`) sobre sus 3 tablas propias.
- `EXECUTE` sobre las funciones que encapsulan la lógica.
- Ningún permiso sobre `usuarios`, `usuarios_auditoria_rol`, `autores`, `formatos`, `imagenes_libro`.

No se usa el superusuario `postgres` ni `library_user` (dueño del monolito)
desde esta aplicación.
