# Electron App — Catalogo de libros

App de escritorio (Electron) que muestra el catalogo de libros de la
biblioteca en tarjetas (imagen, autor(es), ISBN, stock, anio, genero y
precio), con paginacion, consumiendo unicamente XML de un microservicio
en la nube cuya URL y endpoint son configurables desde la propia app.

## Requisitos (Windows 11)

- Node.js LTS (18 o superior) instalado — https://nodejs.org
- El microservicio de libros (`apps/services/soap/app.py`) accesible por red
  desde esta maquina (por defecto expone `GET /api/libros/catalogo` en el
  puerto 5001, con los datos minimos de cada libro e imagenes).

## Instalacion

Desde una terminal (PowerShell o CMD) dentro de la carpeta del proyecto:

```powershell
cd apps\Electron_app
npm install
```

## Ejecucion

```powershell
npm start
```

Al abrir la app:

1. En "URL base del microservicio" escribe la URL del servidor en la nube,
   por ejemplo `http://34.10.20.30:5001`.
2. En "Endpoint" deja `/api/libros/catalogo` (valor por defecto) o cambialo
   si el microservicio expone otra ruta.
3. Pulsa "Cargar catalogo". La URL y el endpoint quedan guardados
   (localStorage) para la siguiente vez que abras la app.
4. Usa "Anterior" / "Siguiente" para paginar el catalogo ya descargado.

## Pruebas unitarias

El parseo de XML y la paginacion (`catalogo.js`) no dependen de Electron ni
del DOM, asi que se prueban con el runner de pruebas incluido en Node:

```powershell
npm test
```
