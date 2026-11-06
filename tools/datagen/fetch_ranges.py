# SPDX-License-Identifier: GPL-3.0-or-later

"""Copies a URL to stdout as one unbroken stream, reconnecting where a
connection breaks (owner, 2026-10-30: the openings stream must survive a
broken download). A dropped connection is reopened from the next byte with
an HTTP Range request; the server must answer 206 with that start, the same
total length and the same ETag (sent as If-Range, so a changed file comes
back whole as 200 and is refused). datagen_openings.py reading stdin then
never sees the break and never re-reads what it already has.

    python -I tools/datagen/fetch_ranges.py URL [--retries 30] [--wait 60] \\
        | python -I tools/datagen/datagen_openings.py - OUT.epd ...

Exit status: 0 when every byte of the resource was written; 2 when the
resource changed (ETag or length) or the server ignores ranges; 1 when the
retries ran out; 3 when the reader closed its input (a write failed, never
retried). Progress and reconnections go to stderr.
"""
import argparse
import http.client
import re
import sys
import time
import urllib.request

BLOCK = 1 << 20
CONTENT_RANGE = re.compile(r'bytes (\d+)-\d+/(\d+)$')


class SourceChanged(Exception):
    pass


def open_from(url, offset, etag, total, timeout):
    """The resource from byte `offset`, checked against the first response's
    ETag and total length (None on the first request)."""
    headers = {}
    if offset:
        headers['Range'] = f'bytes={offset}-'
        if etag:
            headers['If-Range'] = etag
    r = urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=timeout)
    if offset:
        m = CONTENT_RANGE.match(r.headers.get('Content-Range', ''))
        if r.status != 206 or not m:
            r.close()
            raise SourceChanged(f'resume at byte {offset}: status {r.status}, no matching range (changed or no ranges)')
        if int(m.group(1)) != offset or int(m.group(2)) != total or r.headers.get('ETag') != etag:
            r.close()
            raise SourceChanged(f'resume at byte {offset}: got {m.group(0)}, ETag {r.headers.get("ETag")}')
    return r


def copy(url, out, retries, wait, timeout=120, log=sys.stderr):
    """Writes the whole resource to `out`; returns the number of bytes. Only
    reading and reconnecting are retried: a failed write ends the copy."""
    r = open_from(url, 0, None, None, timeout)
    etag = r.headers.get('ETag')
    total = int(r.headers['Content-Length'])
    done = failures = 0
    while done < total:
        try:
            if r is None:
                r = open_from(url, done, etag, total, timeout)
            block = r.read(min(BLOCK, total - done))
            if not block:
                raise OSError(f'connection closed at byte {done} of {total}')
        except (OSError, http.client.HTTPException) as e:
            if r is not None:
                r.close()
                r = None
            failures += 1
            if failures > retries:
                raise OSError(f'{retries} retries used; last: {e}') from e
            print(f'fetch_ranges: {e}; reconnecting at byte {done} in {wait} s ({failures}/{retries})',
                  file=log, flush=True)
            time.sleep(wait)
            continue
        out.write(block)
        done += len(block)
    r.close()
    return done


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    p.add_argument('url')
    p.add_argument('--retries', type=int, default=30)
    p.add_argument('--wait', type=float, default=60)
    a = p.parse_args(argv)
    try:
        n = copy(a.url, sys.stdout.buffer, a.retries, a.wait)
    except SourceChanged as e:
        print(f'fetch_ranges: {e}', file=sys.stderr)
        return 2
    except BrokenPipeError:
        print('fetch_ranges: the reader closed its input', file=sys.stderr)
        return 3
    except OSError as e:
        print(f'fetch_ranges: gave up: {e}', file=sys.stderr)
        return 1
    sys.stdout.buffer.flush()
    print(f'fetch_ranges: {n} bytes', file=sys.stderr)
    return 0


if __name__ == '__main__':
    sys.exit(main())
