/**
 * Proceso principal de Electron. Igual que en
 * apps/desktop-clasificador-cloud/main.js: el microservicio corre en
 * la nube y esta app corre local, asi que la peticion HTTP se hace aqui
 * (Node puro, sin CORS) y el renderer solo recibe el XML ya descargado.
 */
const { app, BrowserWindow, ipcMain } = require("electron");
const path = require("path");
const http = require("http");
const https = require("https");

function createWindow() {
  const win = new BrowserWindow({
    width: 1100,
    height: 780,
    webPreferences: {
      preload: path.join(__dirname, "preload.js"),
      contextIsolation: true,
      nodeIntegration: false,
      // El preload necesita `require("./catalogo.js")" (un modulo local del
      // proyecto). El preload "sandboxed" (default) solo permite requerir
      // modulos built-in de Node/Electron, asi que sin esto el require
      // fallaba en silencio y nunca se llegaba a exponer window.catalogApi.
      // El renderer sigue aislado: contextIsolation true, nodeIntegration false.
      sandbox: false,
    },
  });
  win.loadFile("index.html");
}

app.whenReady().then(createWindow);

app.on("window-all-closed", () => {
  if (process.platform !== "darwin") app.quit();
});

/** Descarga XML exigiendo Accept: application/xml (nunca JSON). */
function httpGetXml(urlString) {
  return new Promise((resolve, reject) => {
    let target;
    try {
      target = new URL(urlString);
    } catch {
      reject(new Error(`URL invalida: ${urlString}`));
      return;
    }

    const client = target.protocol === "https:" ? https : http;
    const req = client.get(
      target,
      { headers: { Accept: "application/xml" } },
      (res) => {
        let body = "";
        res.setEncoding("utf8");
        res.on("data", (chunk) => (body += chunk));
        res.on("end", () => {
          if (res.statusCode >= 200 && res.statusCode < 300) {
            resolve(body);
          } else {
            reject(
              new Error(`El microservicio respondio con estado ${res.statusCode}: ${body}`)
            );
          }
        });
      }
    );

    req.on("error", (err) => reject(err));
    req.setTimeout(10000, () => {
      req.destroy(new Error("Tiempo de espera agotado al contactar el microservicio"));
    });
  });
}

// baseUrl + endpoint son configurables desde la GUI (ver renderer.js);
// aqui solo se combinan y se descarga el XML.
ipcMain.handle("catalogo:obtener-libros", async (_event, { baseUrl, endpoint }) => {
  const url = new URL(endpoint, baseUrl);
  return httpGetXml(url.toString());
});
