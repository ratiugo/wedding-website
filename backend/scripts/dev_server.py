"""
Local dev server: serves the website in frontend/ and forwards /api/* to the local
Lambda.

Does API Gateway's job locally: turns an HTTP request like `PUT /api/rsvp/GU4G9H`
into a payload 2.0 event, invokes the Lambda running in docker compose, and turns
its result back into an HTTP response. Uses only the standard library and runs on
the host:

    python3 backend/scripts/dev_server.py     # serves http://localhost:8080

Page addresses have no ".html", as on CloudFront (infra/.../clean_urls.js): /rsvp
serves rsvp.html, and /rsvp.html redirects to /rsvp.
"""

import json
import re
import urllib.parse
import urllib.request
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

PORT = 8080
SITE_ROOT = Path(__file__).resolve().parents[2] / "frontend"
LAMBDA_URL = "http://localhost:9000/2015-03-31/functions/function/invocations"

ROUTES = [(re.compile(r"^/api/rsvp/([^/]+)$"), "/rsvp/{invite_code}", "invite_code")]


class Handler(SimpleHTTPRequestHandler):
    """
    Serve the site's files, and forward /api/* to the Lambda.
    """

    def do_GET(self):
        if self.path.startswith("/api/"):
            return self.proxy()

        path, _, query = self.path.partition("?")
        query = f"?{query}" if query else ""
        if len(path) > 1 and path.endswith("/"):
            return self.redirect(path.rstrip("/") + query)
        if path.endswith(".html"):
            page = path.removesuffix(".html")
            return self.redirect(("/" if page == "/index" else page) + query)
        return super().do_GET()

    def translate_path(self, path):
        """
        The file for an address: a page like /rsvp is the file rsvp.html.
        """
        path = path.partition("?")[0]
        if path != "/" and "." not in path.rsplit("/", 1)[-1]:
            path += ".html"
        return super().translate_path(path)

    def redirect(self, location):
        """
        Send a permanent redirect, as CloudFront does for .html addresses.
        """
        self.send_response(301)
        self.send_header("Location", location)
        self.send_header("Content-Length", "0")
        self.end_headers()

    def do_PUT(self):
        """
        Forward PUTs to the Lambda.
        """
        self.proxy()

    def proxy(self):
        """
        Invoke the Lambda with an API Gateway event and relay its response.

        Path parameters are URL-decoded ("%20" -> " "), as API Gateway does. An
        unhandled exception comes back from the Lambda as {"errorMessage": ...}
        instead of a response, so it becomes a 502.
        """
        path = self.path.split("?")[0]
        for pattern, route, param in ROUTES:
            match = pattern.match(path)
            if match:
                break
        else:
            return self.send_json(404, {"error": "Not found"})

        length = int(self.headers.get("Content-Length") or 0)
        event = {
            "version": "2.0",
            "routeKey": f"{self.command} {route}",
            "rawPath": path,
            "pathParameters": {param: urllib.parse.unquote(match.group(1))},
            "body": self.rfile.read(length).decode() if length else None,
            "isBase64Encoded": False,
        }

        req = urllib.request.Request(
            LAMBDA_URL, data=json.dumps(event).encode(), method="POST"
        )
        try:
            with urllib.request.urlopen(req) as resp:
                result = json.load(resp)
        except OSError as e:
            return self.send_json(
                502,
                {"error": f"Couldn't reach the Lambda ({e}). Is docker compose up?"},
            )

        if "statusCode" not in result:
            print("Lambda error:", json.dumps(result, indent=2))
            return self.send_json(
                502, {"error": "The Lambda raised an error; see the dev server output."}
            )

        body = result.get("body", "").encode()
        self.send_response(result["statusCode"])
        for name, value in (result.get("headers") or {}).items():
            self.send_header(name, value)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def send_json(self, status, payload):
        """
        Send a JSON response.
        """
        body = json.dumps(payload).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


if __name__ == "__main__":
    server = ThreadingHTTPServer(
        ("localhost", PORT), partial(Handler, directory=SITE_ROOT)
    )
    print(f"Serving {SITE_ROOT} at http://localhost:{PORT} (API -> local Lambda)")
    server.serve_forever()
