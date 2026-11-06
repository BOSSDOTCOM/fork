#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-3.0-or-later
# Simulated spot interruption for tools/cloud/spot_watch.sh: a fake instance
# metadata service (IMDSv2: GET needs the token a PUT handed out) answers
# 404 for spot/instance-action until the test raises the notice, then 200.
# Checks: no stop before the notice, the job gets SIGTERM once the notice
# appears, a job that ends by itself ends the watcher, and a request
# without the token is refused (so the watcher must use IMDSv2). Uses
# python3 (or $PYTHON) and curl.
#
#   bash tools/cloud/test_spot_watch.sh
set -uo pipefail
here=$(cd "$(dirname "$0")" && pwd)
tmp=$(mktemp -d)
failures=0
check() {  # description, command...
  local what=$1
  shift
  if "$@"; then echo "PASS  $what"; else echo "FAIL  $what"; failures=$((failures + 1)); fi
}
py=${PYTHON:-python3}
cat >"$tmp/imds.py" <<'EOF'
import http.server, os, sys
flag, port_file = sys.argv[1], sys.argv[2]
class H(http.server.BaseHTTPRequestHandler):
    def log_message(self, *a): pass
    def reply(self, code, body=b''):
        self.send_response(code)
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)
    def do_PUT(self):
        ok = self.path == '/latest/api/token' and self.headers.get('X-aws-ec2-metadata-token-ttl-seconds')
        self.reply(200, b'tok-123') if ok else self.reply(400)
    def do_GET(self):
        if self.headers.get('X-aws-ec2-metadata-token') != 'tok-123':
            return self.reply(401)
        if self.path == '/latest/meta-data/spot/instance-action' and os.path.exists(flag):
            return self.reply(200, b'{"action": "terminate", "time": "2026-10-30T12:00:00Z"}')
        self.reply(404)
s = http.server.HTTPServer(('127.0.0.1', 0), H)
open(port_file, 'w').write(str(s.server_address[1]))
s.serve_forever()
EOF
"$py" "$tmp/imds.py" "$tmp/notice" "$tmp/port" &
server=$!
trap 'kill $server 2>/dev/null; rm -rf "$tmp"' EXIT
for _ in $(seq 1 50); do [ -s "$tmp/port" ] && break; sleep 0.1; done
imds=http://127.0.0.1:$(cat "$tmp/port")

# A job that records how it ended.
job() { trap 'echo term >"$tmp/job"; exit 0' TERM; for _ in $(seq 1 600); do sleep 0.1; done; echo timeout >"$tmp/job"; }

# 1-2: the notice stops the job, and not before.
job &
jp=$!
bash "$here/spot_watch.sh" $jp --imds "$imds" --interval 0.2 >"$tmp/watch.out" &
wp=$!
sleep 1.5
check "no stop before the notice" kill -0 $jp
touch "$tmp/notice"
for _ in $(seq 1 50); do kill -0 $jp 2>/dev/null || break; sleep 0.1; done
wait $wp
check "the notice sends SIGTERM to the job" grep -qx term "$tmp/job"
check "the watcher reports the notice" grep -qx "spot interruption notice" "$tmp/watch.out"
rm -f "$tmp/notice" "$tmp/job"

# 3: a job that ends by itself ends the watcher, which reports nothing.
(sleep 0.5) &
jp=$!
bash "$here/spot_watch.sh" $jp --imds "$imds" --interval 0.2 >"$tmp/watch.out" &
wp=$!
ended=0
for _ in $(seq 1 50); do kill -0 $wp 2>/dev/null || { ended=1; break; }; sleep 0.1; done
check "the watcher ends with its job" [ $ended = 1 ]
check "no notice reported without one" [ ! -s "$tmp/watch.out" ]

# 4: the fake service is strict about IMDSv2.
touch "$tmp/notice"
check "a request without the token is refused" \
  [ "$(curl -s -o /dev/null -w '%{http_code}' "$imds/latest/meta-data/spot/instance-action")" = 401 ]

echo "$failures failure(s)"
[ $failures -eq 0 ]
