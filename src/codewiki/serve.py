"""Author mode: rebuild on save + live browser refresh.

    python -m codewiki serve [--port 8000] [--no-open] [--config ...]

Watches the wiki dir and every configured code root. The reload script is
injected while serving, never written to disk, so `build` output stays
byte-identical.
"""
from __future__ import annotations

import argparse, functools, http.server, json, os, socketserver, subprocess, sys, threading, time, webbrowser
from pathlib import Path

from .config import Wiki, load as load_wiki
from .languages import DEFAULT_FILE_MAP

STATE = {"build": 0, "error": ""}

RELOAD_JS = """
<script>
(() => {
  let last = null;
  const bar = document.createElement("div");
  bar.style.cssText = "position:fixed;left:0;right:0;bottom:0;padding:8px 14px;font:13px/1.4 ui-monospace,monospace;"
    + "background:#b3261e;color:#fff;white-space:pre-wrap;z-index:9999;display:none";
  document.body.appendChild(bar);
  async function tick() {
    try {
      const r = await fetch("/__build", {cache: "no-store"});
      const j = await r.json();
      if (last !== null && j.build !== last) { location.reload(); return; }
      last = j.build;
      bar.textContent = j.error; bar.style.display = j.error ? "block" : "none";
    } catch (e) {}
    setTimeout(tick, 700);
  }
  tick();
})();
</script>
"""


def watch_paths(w: Wiki):
    paths = [w.cfg_path, w.wiki_dir, *w.theme_dirs]
    for root in w.cfg["code_roots"]:
        p = w.abs(root)
        if p.exists():
            paths.append(p)
    return paths


def fingerprint(w: Wiki, paths):
    file_map = dict(DEFAULT_FILE_MAP); file_map.update(w.cfg.get("languages") or {})
    out = []
    for base in paths:
        if base.is_file():
            out.append((str(base), base.stat().st_mtime_ns)); continue
        for dp, dns, fns in os.walk(base):
            dns[:] = [d for d in dns if d not in (".git", "site", "__pycache__", "node_modules")]
            for fn in fns:
                p = Path(dp) / fn
                if base == w.wiki_dir or base in w.theme_dirs or fn in file_map or p.suffix in file_map:
                    try:
                        out.append((str(p), p.stat().st_mtime_ns))
                    except OSError:
                        pass
    return hash(tuple(sorted(out)))


# @wiki:impl authoring.preview
def build_once(w: Wiki):
    w = Wiki(w.cfg_path)
    r = subprocess.run([sys.executable, "-m", "codewiki", "build", "--strict", "--config", str(w.cfg_path)],
                       cwd=str(w.root), capture_output=True, text=True)
    if r.returncode == 0:
        STATE["error"] = ""
    else:
        errs = [l.strip() for l in r.stdout.splitlines() if "[error]" in l]
        STATE["error"] = "\n".join(errs) or (r.stdout + r.stderr).strip()
    STATE["build"] += 1
    stamp = time.strftime("%H:%M:%S")
    if not STATE["error"]:
        head = [l for l in r.stdout.splitlines() if l.startswith("docs=")]
        print(f"  {stamp}  rebuilt   {head[0] if head else ''}")
        for line in r.stdout.splitlines():
            if line.strip().startswith("["):
                print(f"            {line.strip()}")
    else:
        print(f"  {stamp}  BUILD FAILED")
        for line in STATE["error"].splitlines():
            print(f"            {line}")


def watcher(w: Wiki, interval=0.7):
    paths = watch_paths(w)
    last = fingerprint(w, paths)
    while True:
        time.sleep(interval)
        try:
            w = Wiki(w.cfg_path)
            paths = watch_paths(w)
            now = fingerprint(w, paths)
        except (ValueError, OSError) as exc:
            STATE["error"] = str(exc)
            continue
        if now != last:
            last = now
            build_once(w)


class Handler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_GET(self):
        if self.path.startswith("/__build"):
            body = json.dumps({"build": STATE["build"], "error": STATE["error"]}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)
            return
        path = self.translate_path(self.path)
        if path.endswith(".html") and os.path.isfile(path):
            html = Path(path).read_text(encoding="utf8").replace("</body>", RELOAD_JS + "</body>")
            body = html.encode("utf8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)
            return
        super().do_GET()


def main(argv=None):
    ap = argparse.ArgumentParser(prog="codewiki serve", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--port", type=int, default=8000)
    ap.add_argument("--no-open", action="store_true")
    ap.add_argument("--config", default=None)
    args = ap.parse_args(argv)
    w = load_wiki(args.config)
    build_once(w)
    threading.Thread(target=watcher, args=(w,), daemon=True).start()
    socketserver.TCPServer.allow_reuse_address = True
    handler = functools.partial(Handler, directory=str(w.site_dir))
    with socketserver.TCPServer(("127.0.0.1", args.port), handler) as httpd:
        url = f"http://localhost:{args.port}/index.html"
        print(f"\n  watching {', '.join(p.name for p in watch_paths(w))}")
        print(f"  serving  {url}    (ctrl-c to stop)\n")
        if not args.no_open:
            threading.Timer(0.4, lambda: webbrowser.open(url)).start()
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\n  stopped")
    return 0


if __name__ == "__main__":
    sys.exit(main())
