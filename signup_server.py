#!/usr/bin/env python3
"""
Alpha Pulse — Signup HTTP Server
Receives email signups and stores in SQLite.
"""
import http.server
import json
import urllib.parse
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))
from subscriber_db import add_subscriber, get_active_subscribers

class SignupHandler(http.server.BaseHTTPRequestHandler):
    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'POST, GET, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()
    
    def do_POST(self):
        path = urllib.parse.urlparse(self.path).path
        content_length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(content_length).decode('utf-8') if content_length else '{}'
        data = json.loads(body) if body else {}
        
        if path == '/signup' or path == '/':
            email = data.get('email', '')
            name = data.get('name', '')
            if not email or '@' not in email:
                self.send_json({'success': False, 'error': 'Invalid email'}, 400)
                return
            ok = add_subscriber(email, name if name else None, source='web')
            self.send_json({
                'success': ok,
                'message': 'Welcome to Alpha Pulse Free!' if ok else 'Already subscribed'
            })
        else:
            self.send_json({'error': 'not found'}, 404)
    
    def do_GET(self):
        path = urllib.parse.urlparse(self.path).path
        if path == '/stats':
            subs = get_active_subscribers('free')
            self.send_json({'subscribers': len(subs)})
        elif path == '/health':
            self.send_json({'status': 'ok', 'service': 'alpha-pulse-signup'})
        else:
            self.send_json({'error': 'not found'}, 404)
    
    def send_json(self, data, status=200):
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()
        self.wfile.write(json.dumps(data).encode('utf-8'))
    
    def log_message(self, format, *args):
        pass  # Suppress logs

def run_server(port=8080):
    server = http.server.HTTPServer(('0.0.0.0', port), SignupHandler)
    print(f"📡 Alpha Pulse signup server → port {port}")
    print(f"   POST /signup  — register email")
    print(f"   GET  /stats   — subscriber count")
    print(f"   GET  /health  — health check")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutdown.")
        server.server_close()

if __name__ == '__main__':
    run_server(int(sys.argv[1]) if len(sys.argv) > 1 else 8080)
