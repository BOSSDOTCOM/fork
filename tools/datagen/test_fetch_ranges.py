# SPDX-License-Identifier: GPL-3.0-or-later

"""Tests of fetch_ranges.py against a local HTTP server that breaks every
connection after a set number of bytes, answers Range requests (honouring
If-Range), and can change its ETag or ignore ranges.

    .venv/Scripts/python.exe -I -B -m unittest discover -s tools/datagen -p 'test_fetch_ranges.py'
"""
import http.server
import io
import random
import sys
import threading
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import fetch_ranges  # noqa: E402

DATA = random.Random(7).randbytes(3_000_000)


class Handler(http.server.BaseHTTPRequestHandler):
    # Set per test on the server: cut (bytes per connection, 0 = whole),
    # etags (the ETag of each successive request), ranges (answer ranges).
    def do_GET(self):
        srv = self.server
        etag = srv.etags[min(srv.requests, len(srv.etags) - 1)]
        srv.requests += 1
        start = 0
        want = self.headers.get('Range')
        if want and srv.ranges and self.headers.get('If-Range', etag) == etag:
            start = int(want.split('=')[1].rstrip('-'))
            self.send_response(206)
            self.send_header('Content-Range', f'bytes {start}-{len(DATA) - 1}/{len(DATA)}')
        else:
            self.send_response(200)
        self.send_header('Content-Length', str(len(DATA) - start))
        self.send_header('ETag', etag)
        self.end_headers()
        body = DATA[start:]
        if srv.cut:
            body = body[:srv.cut]
        self.wfile.write(body)
        self.wfile.flush()
        self.close_connection = True

    def log_message(self, *args):
        pass


class FetchRanges(unittest.TestCase):
    def serve(self, cut=0, etags=('"a"',), ranges=True):
        srv = http.server.ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        srv.cut, srv.etags, srv.ranges, srv.requests = cut, list(etags), ranges, 0
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        self.addCleanup(srv.server_close)
        self.addCleanup(srv.shutdown)
        return srv, f'http://127.0.0.1:{srv.server_address[1]}/f'

    def fetch(self, url, retries=20):
        out, log = io.BytesIO(), io.StringIO()
        n = fetch_ranges.copy(url, out, retries, 0, timeout=10, log=log)
        return n, out.getvalue(), log.getvalue()

    def test_unbroken(self):
        srv, url = self.serve()
        n, got, log = self.fetch(url)
        self.assertEqual((n, got, log, srv.requests), (len(DATA), DATA, '', 1))

    def test_breaks_are_resumed_without_rereading(self):
        srv, url = self.serve(cut=700_000)
        n, got, log = self.fetch(url)
        self.assertEqual(got, DATA)
        self.assertEqual(srv.requests, 5)  # 3,000,000 bytes at most 700,000 per connection
        self.assertEqual(log.count('reconnecting'), 4)

    def test_changed_file_is_refused(self):
        srv, url = self.serve(cut=700_000, etags=('"a"', '"b"'))
        with self.assertRaises(fetch_ranges.SourceChanged):
            self.fetch(url)

    def test_server_without_ranges_is_refused(self):
        srv, url = self.serve(cut=700_000, ranges=False)
        with self.assertRaises(fetch_ranges.SourceChanged):
            self.fetch(url)

    def test_retries_run_out(self):
        srv, url = self.serve(cut=100_000)
        with self.assertRaises(OSError):
            self.fetch(url, retries=3)
        self.assertEqual(srv.requests, 4)

    def test_main_exit_status(self):
        srv, url = self.serve(cut=700_000, etags=('"a"', '"b"'))
        old = sys.stdout
        sys.stdout = io.TextIOWrapper(io.BytesIO())
        try:
            self.assertEqual(fetch_ranges.main([url, '--wait', '0']), 2)
        finally:
            sys.stdout = old

    def test_a_failed_write_is_not_retried(self):
        srv, url = self.serve(cut=700_000)

        class Closed(io.RawIOBase):
            def write(self, b):
                raise BrokenPipeError('reader gone')

        with self.assertRaises(BrokenPipeError):
            fetch_ranges.copy(url, Closed(), 20, 0, timeout=10, log=io.StringIO())
        self.assertEqual(srv.requests, 1)


if __name__ == '__main__':
    unittest.main()
