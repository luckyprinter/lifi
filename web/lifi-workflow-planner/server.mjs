import { createServer } from "node:http";
import { mkdir, readFile, stat, writeFile } from "node:fs/promises";
import { createReadStream } from "node:fs";
import { extname, join, normalize } from "node:path";
import { fileURLToPath } from "node:url";

const root = fileURLToPath(new URL(".", import.meta.url));
const distDir = join(root, "dist");
const handoffDir = join(root, "handoffs");
const archiveDir = join(handoffDir, "archive");
const latestJson = join(handoffDir, "latest.json");
const latestMd = join(handoffDir, "latest.md");
const port = Number(process.env.PORT || 5174);
const host = process.env.HOST || "0.0.0.0";

const contentTypes = {
  ".html": "text/html; charset=utf-8",
  ".js": "text/javascript; charset=utf-8",
  ".css": "text/css; charset=utf-8",
  ".json": "application/json; charset=utf-8",
  ".webmanifest": "application/manifest+json; charset=utf-8",
  ".svg": "image/svg+xml",
  ".ico": "image/x-icon",
};

function send(res, status, body, contentType = "application/json; charset=utf-8") {
  res.writeHead(status, {
    "Content-Type": contentType,
    "Cache-Control": "no-store",
  });
  res.end(body);
}

function safeFilePath(urlPath) {
  const clean = normalize(decodeURIComponent(urlPath.split("?")[0])).replace(/^(\.\.[/\\])+/, "");
  const relative = clean === "/" ? "index.html" : clean.replace(/^[/\\]/, "");
  return join(distDir, relative);
}

function markdownSummary(payload) {
  const notes = payload.notes || {};
  const components = payload.schematicComponents || [];
  const noteEntries = Object.entries(notes).filter(([, value]) => String(value || "").trim());

  return [
    "# LiFi Planner Handoff",
    "",
    `Saved at: ${payload.savedAt || payload.exportedAt || new Date().toISOString()}`,
    `Active view: ${payload.activeView || "unknown"}`,
    `Selected node: ${payload.selectedId || "unknown"}`,
    "",
    "## Project/System Note",
    "",
    notes.system_overall || "_No system note yet._",
    "",
    "## Node Notes",
    "",
    ...(noteEntries.length
      ? noteEntries.map(([key, value]) => `### ${key}\n\n${value}\n`)
      : ["_No node notes yet._"]),
    "",
    "## Schematic Components",
    "",
    ...(components.length
      ? components.map((item) => `- ${item.name || item.id}: ${item.value || ""} (${item.type || "component"}) - ${item.note || ""}`)
      : ["_No component edits yet._"]),
    "",
    "## How Codex Should Use This",
    "",
    "Read this file and `latest.json` before making future LiFi firmware, GUI, schematic, or thesis-planner changes.",
    "",
  ].join("\n");
}

async function readRequestBody(req) {
  const chunks = [];
  for await (const chunk of req) chunks.push(chunk);
  return Buffer.concat(chunks).toString("utf8");
}

async function handleApi(req, res) {
  if (req.method === "GET" && req.url.startsWith("/api/handoff/latest")) {
    try {
      const content = await readFile(latestJson, "utf8");
      send(res, 200, content);
    } catch {
      send(res, 204, "");
    }
    return true;
  }

  if (req.method === "POST" && req.url.startsWith("/api/handoff")) {
    try {
      const body = await readRequestBody(req);
      const payload = JSON.parse(body || "{}");
      const savedAt = new Date().toISOString();
      const saved = { ...payload, savedAt };

      await mkdir(archiveDir, { recursive: true });
      await writeFile(latestJson, `${JSON.stringify(saved, null, 2)}\n`, "utf8");
      await writeFile(latestMd, markdownSummary(saved), "utf8");

      if (payload.archive) {
        const stamp = savedAt.replace(/[:.]/g, "-");
        await writeFile(join(archiveDir, `handoff_${stamp}.json`), `${JSON.stringify(saved, null, 2)}\n`, "utf8");
      }

      send(res, 200, JSON.stringify({ ok: true, savedAt, path: "handoffs/latest.json" }));
    } catch (error) {
      send(res, 500, JSON.stringify({ ok: false, error: String(error.message || error) }));
    }
    return true;
  }

  return false;
}

async function serveStatic(req, res) {
  let filePath = safeFilePath(req.url || "/");

  try {
    const info = await stat(filePath);
    if (info.isDirectory()) filePath = join(filePath, "index.html");
  } catch {
    filePath = join(distDir, "index.html");
  }

  const ext = extname(filePath);
  res.writeHead(200, {
    "Content-Type": contentTypes[ext] || "application/octet-stream",
  });
  createReadStream(filePath).pipe(res);
}

const server = createServer(async (req, res) => {
  if (req.url?.startsWith("/api/")) {
    const handled = await handleApi(req, res);
    if (handled) return;
  }

  await serveStatic(req, res);
});

server.listen(port, host, () => {
  console.log(`LiFi workflow planner running at http://localhost:${port}/`);
  console.log(`Handoffs will be saved in ${handoffDir}`);
});
