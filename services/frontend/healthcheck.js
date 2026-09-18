// Minimal Node.js HTTP server — placeholder healthcheck for all service stubs
// Replace this file with your actual application entry point.
const http = require("http");
const PORT = parseInt(process.env.SERVICE_PORT || process.env.PORT || "3000", 10);

const server = http.createServer((req, res) => {
  if (req.url === "/health" && req.method === "GET") {
    res.writeHead(200, { "Content-Type": "application/json" });
    res.end(JSON.stringify({ status: "ok" }));
  } else {
    res.writeHead(404, { "Content-Type": "application/json" });
    res.end(JSON.stringify({ error: "not_implemented", message: "This is a placeholder service stub." }));
  }
});

server.listen(PORT, () => {
  console.log(`[stub] Listening on port ${PORT} — GET /health returns {"status":"ok"}`);
});
