#!/usr/bin/env python3
"""
Simple HTTP server for GUM Frontend

Serves the static frontend files for the GUM web interface.
"""

import os
import http.server
import socketserver
from pathlib import Path
from urllib.parse import urlparse

class GUMFrontendHandler(http.server.SimpleHTTPRequestHandler):
    """Custom handler to serve the frontend files."""
    
    def __init__(self, *args, **kwargs):
        # Set the directory to serve from
        self.frontend_dir = Path(__file__).parent
        super().__init__(*args, directory=str(self.frontend_dir), **kwargs)
    
    def do_GET(self):
        """Handle GET requests, with special handling for index.html to inject config."""
        if self.path == '/' or self.path == '/index.html':
            self.serve_index_with_config()
        else:
            super().do_GET()
    
    def serve_index_with_config(self):
        """Serve index.html with injected configuration."""
        try:
            # Read the .env file to get the backend address
            backend_address = self.load_backend_address()
            
            # Read the index.html file
            index_path = self.frontend_dir / 'index.html'
            with open(index_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Inject the backend address as a global JavaScript variable
            config_script = f"""
    <script>
        window.GUM_CONFIG = {{
            apiBaseUrl: '{backend_address}'
        }};
    </script>"""
            
            # Insert the config script before the closing </head> tag
            content = content.replace('</head>', f'{config_script}\n</head>')
            
            # Send the response
            self.send_response(200)
            self.send_header('Content-type', 'text/html; charset=utf-8')
            self.send_header('Content-Length', str(len(content.encode('utf-8'))))
            self.end_headers()
            self.wfile.write(content.encode('utf-8'))
            
        except Exception as e:
            print(f"Error serving index.html: {e}")
            self.send_error(500, f"Internal server error: {e}")
    
    def load_backend_address(self):
        """Load backend address from .env files or environment variables."""
        # Try environment variable first
        backend_address = os.getenv('BACKEND_ADDRESS')
        if backend_address:
            return backend_address
        
        # Try root .env file first (main configuration)
        root_env_path = self.frontend_dir.parent / '.env'
        backend_address = self._read_env_file(root_env_path)
        if backend_address:
            return backend_address
        
        # Try frontend .env file as fallback
        frontend_env_path = self.frontend_dir / '.env'
        backend_address = self._read_env_file(frontend_env_path)
        if backend_address:
            return backend_address
        
        # Default fallback
        return 'http://localhost:8001'
    
    def _read_env_file(self, env_path):
        """Read BACKEND_ADDRESS from a specific .env file."""
        if env_path.exists():
            try:
                with open(env_path, 'r') as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith('#') and '=' in line:
                            key, value = line.split('=', 1)
                            if key.strip() == 'BACKEND_ADDRESS':
                                return value.strip()
            except Exception as e:
                print(f"Error reading .env file {env_path}: {e}")
        return None
    
    def end_headers(self):
        # Add CORS headers to allow API calls
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        super().end_headers()

def serve_frontend(port=3000, host='localhost'):
    """Start the frontend server."""
    # Load and display the configuration
    handler = GUMFrontendHandler
    frontend_dir = Path(__file__).parent
    
    # Check backend address with proper hierarchy
    def load_config_for_display():
        """Load configuration for display purposes."""
        # Check environment variable
        backend_address = os.getenv('BACKEND_ADDRESS')
        if backend_address:
            return backend_address, 'environment variable'
        
        # Check root .env file
        root_env_path = frontend_dir.parent / '.env'
        if root_env_path.exists():
            try:
                with open(root_env_path, 'r') as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith('#') and '=' in line:
                            key, value = line.split('=', 1)
                            if key.strip() == 'BACKEND_ADDRESS':
                                return value.strip(), f'root .env ({root_env_path})'
            except Exception as e:
                print(f"Warning: Error reading root .env file: {e}")
        
        # Check frontend .env file
        frontend_env_path = frontend_dir / '.env'
        if frontend_env_path.exists():
            try:
                with open(frontend_env_path, 'r') as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith('#') and '=' in line:
                            key, value = line.split('=', 1)
                            if key.strip() == 'BACKEND_ADDRESS':
                                return value.strip(), f'frontend .env ({frontend_env_path})'
            except Exception as e:
                print(f"Warning: Error reading frontend .env file: {e}")
        
        return 'http://localhost:8001', 'default fallback'
    
    backend_address, source = load_config_for_display()
    
    print(f"Starting GUM Frontend Server")
    print(f"Serving from: {frontend_dir}")
    print(f"Frontend URL: http://{host}:{port}")
    print(f"API Backend URL: {backend_address}")
    print(f"Configuration source: {source}")
    print(f"Open the frontend URL in your browser to access the GUM interface")
    print("=" * 60)
    
    try:
        with socketserver.TCPServer((host, port), handler) as httpd:
            print(f"Server started successfully")
            print(f"Press Ctrl+C to stop the server")
            httpd.serve_forever()
    except OSError as e:
        if e.errno == 48:  # Address already in use
            print(f"Port {port} is already in use")
            print(f"Try a different port: python server.py --port {port + 1}")
        else:
            print(f"Failed to start server: {e}")
    except KeyboardInterrupt:
        print(f"\nServer stopped by user")

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="GUM Frontend Server")
    parser.add_argument("--port", type=int, default=3000, help="Port to serve on (default: 3000)")
    parser.add_argument("--host", default="0.0.0.0", help="Host to bind to (default: localhost)")
    
    args = parser.parse_args()
    serve_frontend(port=args.port, host=args.host)
