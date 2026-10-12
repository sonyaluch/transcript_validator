#!/usr/bin/env python3
"""Run the transcript validator on this laptop, streaming audio from a remote server over SSH.

Usage:
    python3 validator_server.py USER@HOST /remote/path/to/audio [--csv /remote/path/to/file.csv]

The validator opens at http://localhost:8765. Each recording is fetched over SSH into
memory when you play it; nothing is written to this laptop's disk and nothing is
installed or left running on the server. Only this laptop can reach the page.
Stop it with Ctrl+C.
"""
import argparse
import json
import os
import shlex
import subprocess
import sys
import threading
import webbrowser
from collections import OrderedDict
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import unquote, urlparse

HERE = os.path.dirname(os.path.abspath(__file__))
PAGE = os.path.join(HERE, 'transcript-validator.html')
AUDIO_TYPES = {'.oga': 'audio/ogg', '.ogg': 'audio/ogg', '.opus': 'audio/ogg', '.m4a': 'audio/mp4',
               '.mp3': 'audio/mpeg', '.wav': 'audio/wav', '.webm': 'audio/webm', '.aac': 'audio/aac',
               '.flac': 'audio/flac'}
CACHE_SIZE = 30  # recordings kept in memory, so going back to one doesn't refetch it


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('host', help='SSH login, e.g. ab123@server.uni.ac.uk (or a Host alias from ~/.ssh/config)')
    ap.add_argument('audio_dir', help='folder on the server that holds the audio files')
    ap.add_argument('--csv', help='optional: path on the server to the transcript CSV, loaded automatically')
    ap.add_argument('--port', type=int, default=8765)
    args = ap.parse_args()

    # One shared SSH connection: you sign in once, every recording reuses it.
    control = os.path.expanduser('~/.ssh/validator-%C')
    ssh = ['ssh', '-o', 'ControlMaster=auto', '-o', f'ControlPath={control}', '-o', 'ControlPersist=60m', args.host]

    def remote(cmd):
        return subprocess.run(ssh + [cmd], stdout=subprocess.PIPE, check=True).stdout

    print(f'Connecting to {args.host} (sign in if asked)...')
    try:
        listing = remote(f'cd {shlex.quote(args.audio_dir)} && find . -type f').decode('utf-8', 'replace')
    except subprocess.CalledProcessError:
        sys.exit(f'Could not list {args.audio_dir} on {args.host}. Check the login and the folder path.')
    names = sorted(n[2:] for n in listing.splitlines()
                   if os.path.splitext(n)[1].lower() in AUDIO_TYPES)
    allowed = set(names)
    print(f'Found {len(names)} recordings.')

    cache, lock = OrderedDict(), threading.Lock()

    def fetch_audio(name):
        with lock:
            if name in cache:
                cache.move_to_end(name)
                return cache[name]
        data = remote('cat ' + shlex.quote(f'{args.audio_dir.rstrip("/")}/{name}'))
        with lock:
            cache[name] = data
            while len(cache) > CACHE_SIZE:
                cache.popitem(last=False)
        return data

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            path = unquote(urlparse(self.path).path)
            try:
                if path in ('/', '/index.html', '/transcript-validator.html'):
                    with open(PAGE, 'rb') as f:
                        self.send(f.read(), 'text/html; charset=utf-8')
                elif path == '/audio-list':
                    self.send(json.dumps(names).encode(), 'application/json')
                elif path == '/data.csv' and args.csv:
                    self.send(remote('cat ' + shlex.quote(args.csv)), 'text/csv; charset=utf-8')
                elif path.startswith('/audio/') and path[7:] in allowed:
                    name = path[7:]
                    self.send(fetch_audio(name), AUDIO_TYPES[os.path.splitext(name)[1].lower()], ranged=True)
                else:
                    self.send_error(404)
            except subprocess.CalledProcessError:
                self.send_error(502, 'Could not read the file from the server')
            except (BrokenPipeError, ConnectionResetError):
                pass

        def send(self, data, ctype, ranged=False):
            total, start, end = len(data), 0, len(data) - 1
            rng = self.headers.get('Range', '')
            if ranged and rng.startswith('bytes='):
                first, _, last = rng[6:].split(',')[0].partition('-')
                if first:
                    start, end = int(first), min(int(last), total - 1) if last else total - 1
                else:
                    start = max(0, total - int(last))
                if start >= total or start > end:
                    self.send_response(416)
                    self.send_header('Content-Range', f'bytes */{total}')
                    self.end_headers()
                    return
                self.send_response(206)
                self.send_header('Content-Range', f'bytes {start}-{end}/{total}')
            else:
                self.send_response(200)
            self.send_header('Content-Type', ctype)
            self.send_header('Content-Length', str(end - start + 1))
            self.send_header('Cache-Control', 'no-store')
            if ranged:
                self.send_header('Accept-Ranges', 'bytes')
            self.end_headers()
            self.wfile.write(data[start:end + 1])

        def log_message(self, *a):
            pass

    server = ThreadingHTTPServer(('127.0.0.1', args.port), Handler)
    url = f'http://localhost:{args.port}/'
    print(f'Validator running at {url}  (Ctrl+C to stop)')
    webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print('\nStopped.')
        subprocess.run(ssh[:-1] + ['-O', 'exit', args.host], stderr=subprocess.DEVNULL)


if __name__ == '__main__':
    main()
