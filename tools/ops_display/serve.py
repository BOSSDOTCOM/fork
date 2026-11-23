# SPDX-License-Identifier: GPL-3.0-or-later
"""Fork Operations Display: a display-only local page of the whole pipeline (DESIGN.md beside this file).

    python -I -B tools/ops_display/serve.py [--open] [--port 8719] [--no-net]

It serves one page on 127.0.0.1 and answers GET only. It writes no file anywhere, starts no process except
the read-only commands of procs.py (and the browser, once, with --open), and has no route or code that
starts, stops or changes a job. Everything it shows is read from files through fsread.py."""
import argparse
import importlib
import json
import os
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import collect  # noqa: E402
import fsread  # noqa: E402
import net  # noqa: E402
import procs  # noqa: E402
import readers  # noqa: E402
import rules  # noqa: E402

WEB = os.path.join(HERE, 'web')
PAGES = {'/': ('index.html', 'text/html; charset=utf-8'), '/app.js': ('app.js', 'text/javascript; charset=utf-8'),
         '/style.css': ('style.css', 'text/css; charset=utf-8')}
RELOADABLE = (readers, rules)


def git_log(repo, branch):
    git = procs.find('git')
    if not git:
        return ''
    rc, out, _ = procs.run([git, '-C', repo, 'log', '-400', '--format=%h %ad %s', '--date=short', branch], timeout=30)
    return out if rc == 0 else ''


class Display:
    """Holds the latest snapshot as JSON bytes; one thread refreshes it."""

    def __init__(self, paths, poller=None, clock=time.time):
        self.collector = collect.Collector(paths, clock=clock, git_log=git_log)
        self.poller = poller
        self.clock = clock
        self.body = b'{}'
        self.lock = threading.Lock()
        self.stopping = threading.Event()
        self.rules_cache = fsread.Cache(clock)
        self.code = {m.__name__: fsread.mtime(m.__file__) for m in RELOADABLE}
        self.code_error = None
        self.started = clock()
        self.ticks, self.busy = 0, 0.0

    def reload_code(self):
        """Re-import the pure modules when their files change; keep the old version if the new one fails."""
        for m in RELOADABLE:
            mt = fsread.mtime(m.__file__)
            if mt and mt != self.code[m.__name__]:
                self.code[m.__name__] = mt
                try:
                    importlib.reload(m)
                    self.code_error = None
                except Exception as e:  # noqa: BLE001
                    self.code_error = f'{m.__name__}.py did not load ({type(e).__name__}: {e}); the previous version keeps running'[:200]

    def refresh(self):
        t0 = time.perf_counter()
        self.reload_code()
        snap = self.collector.tick()
        try:
            cfg = self.rules_cache.load('rules.json', os.path.join(HERE, 'rules.json'), lambda p: rules.load(fsread.read_text(p)),
                                        default=rules.DEFAULTS, optional=True) or rules.DEFAULTS
            for k, v in self.rules_cache.health().items():
                if not v['ok']:
                    snap['health']['failing'][k] = v
            if self.code_error:
                snap['health']['failing']['display code'] = {'ok': False, 'error': self.code_error, 'missing': False, 'age': None}
            snap['alerts'] = rules.alerts(snap, cfg)
            snap['situation'] = rules.situation(snap)
        except Exception as e:  # noqa: BLE001  the page must still get the data
            snap['alerts'] = [{'id': 'rules', 'tier': 'attention', 'what': 'The alert rules failed', 'why': f'{type(e).__name__}: {e}'[:200],
                               'at': None, 'source': 'rules.py'}]
            snap['situation'] = {'text': '', 'nodes': [], 'edges': []}
        web = max((fsread.mtime(os.path.join(WEB, f)) or 0) for f, _ in PAGES.values())
        up = self.clock() - self.started
        snap['display'] = {'web': web, 'net': self.poller.status if self.poller else {'gh': 'off', 'kaggle': 'off'},
                           'uptime': round(up), 'busy_percent': round(100 * self.busy / up, 2) if up > 5 else None}
        text = fsread.scrub(json.dumps(snap, separators=(',', ':'), allow_nan=False, default=str))
        with self.lock:
            self.body = text.encode('utf-8')
        self.ticks += 1
        self.busy += time.perf_counter() - t0

    def loop(self):
        while not self.stopping.is_set():
            try:
                self.refresh()
            except Exception as e:  # noqa: BLE001
                with self.lock:
                    self.body = json.dumps({'now': self.clock(), 'fatal': f'{type(e).__name__}: {e}'[:300]}).encode()
            self.stopping.wait(2.0)        # the fastest source (CPU and memory) is read every 2 seconds


def make_handler(display, port):
    hosts = {f'127.0.0.1:{port}', f'localhost:{port}'}

    class Handler(BaseHTTPRequestHandler):
        server_version = 'ForkOpsDisplay'
        protocol_version = 'HTTP/1.1'

        def log_message(self, *a):   # no log file, no console noise
            pass

        def _send(self, code, body=b'', ctype='text/plain; charset=utf-8', extra=()):
            self.send_response(code)
            self.send_header('Content-Type', ctype)
            self.send_header('Content-Length', str(len(body)))
            self.send_header('Cache-Control', 'no-store')
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.send_header('Content-Security-Policy', "default-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:")
            for k, v in extra:
                self.send_header(k, v)
            self.end_headers()
            if body and self.command != 'HEAD':
                self.wfile.write(body)

        def do_GET(self):
            if self.headers.get('Host') not in hosts:
                return self._send(403, b'this display answers only on its local address')
            path = self.path.split('?', 1)[0]
            if path == '/snapshot':
                with display.lock:
                    body = display.body
                return self._send(200, body, 'application/json; charset=utf-8')
            if path in PAGES:
                name, ctype = PAGES[path]
                try:
                    return self._send(200, fsread.read_bytes(os.path.join(WEB, name)), ctype)
                except OSError:
                    return self._send(500, b'the page file is missing')
            return self._send(404, b'not found')

        def _refuse(self):
            try:
                n = int(self.headers.get('Content-Length') or 0)
            except ValueError:
                n = 0
            if 0 < n <= 65536:
                self.rfile.read(n)          # take the body off the wire, unread, so the refusal arrives cleanly
            self.close_connection = True
            self._send(405, b'this display only reads', extra=(('Allow', 'GET'), ('Connection', 'close')))

        do_POST = do_PUT = do_DELETE = do_PATCH = do_OPTIONS = do_HEAD = _refuse

    return Handler


def main(argv=None):
    ap = argparse.ArgumentParser(description='Fork Operations Display (display only)')
    ap.add_argument('--port', type=int, default=8719)
    ap.add_argument('--home', default=None, help='the folder holding fork-jobs and fork-data (default: the home folder)')
    ap.add_argument('--repo', default=None, help="the engine's working tree (default: HOME/fork)")
    ap.add_argument('--no-net', action='store_true', help='no GitHub or Kaggle polls')
    ap.add_argument('--open', action='store_true', help='open the page in the default browser')
    a = ap.parse_args(argv)
    paths = collect.Paths(a.home, a.repo)
    try:
        server = ThreadingHTTPServer(('127.0.0.1', a.port), None)
    except OSError:
        print(f'The display is already running, or port {a.port} is taken: http://127.0.0.1:{a.port}/', file=sys.stderr)
        if a.open:                  # a second start from the shortcut: show the page of the one that runs
            import webbrowser
            webbrowser.open(f'http://127.0.0.1:{a.port}/')
        return 3
    display = Display(paths)
    if not a.no_net:
        slug = net.repo_slug(fsread.read_text(os.path.join(paths.repo, '.git', 'config'))) if fsread.stat(os.path.join(paths.repo, '.git', 'config')) else None
        display.poller = net.Poller(display.collector, paths.repo, slug)
        display.poller.start()
    server.RequestHandlerClass = make_handler(display, a.port)
    server.daemon_threads = True
    threading.Thread(target=display.loop, daemon=True, name='ops-display-collect').start()
    url = f'http://127.0.0.1:{a.port}/'
    print(f'Fork Operations Display: {url} (display only; Ctrl+C to close)')
    if a.open:
        import webbrowser
        webbrowser.open(url)
    try:
        server.serve_forever(poll_interval=0.5)
    except KeyboardInterrupt:
        pass
    finally:
        display.stopping.set()
        if display.poller:
            display.poller.stop()
        server.server_close()
    return 0


if __name__ == '__main__':
    sys.exit(main())
