# SPDX-License-Identifier: GPL-3.0-or-later
"""Completes the page's network manifest when the page is built
(.github/workflows/web.yml; DESIGN.md §5.5): for each network in
web/nets.json, its module's path, size (the loader and the WebAssembly
together) and the WebAssembly's SHA-256, from SITE/engines/<id>/. Every
listed network must have its module and every module a listing. Writes
SITE/nets.json.

    python3 web/fill_nets.py web/nets.json SITE
"""
import hashlib
import json
import os
import sys


def main(manifest_path, site):
    manifest = json.load(open(manifest_path, encoding='utf-8'))
    listed = sorted(n['id'] for n in manifest['networks'])
    built = sorted(os.listdir(os.path.join(site, 'engines')))
    if listed != built:
        raise SystemExit(f'nets.json lists {listed}, modules built: {built}')
    for n in manifest['networks']:
        folder = os.path.join(site, 'engines', n['id'])
        n['module'] = f"engines/{n['id']}/fork_web.js"
        n['module_bytes'] = sum(os.path.getsize(os.path.join(folder, f)) for f in ('fork_web.js', 'fork_web.wasm'))
        with open(os.path.join(folder, 'fork_web.wasm'), 'rb') as f:
            n['wasm_sha256'] = hashlib.sha256(f.read()).hexdigest()
        print(f"{n['id']}: {n['module_bytes']} bytes, wasm {n['wasm_sha256']}")
    with open(os.path.join(site, 'nets.json'), 'w', encoding='utf-8', newline='\n') as f:
        json.dump(manifest, f, indent=1)
        f.write('\n')


if __name__ == '__main__':
    main(*sys.argv[1:3])
