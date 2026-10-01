"""A page's queued static connections survive a temporarily busy accept loop."""
import http.client
import re
import threading

import pytest

from spriteforge.server import WEB_ROOT, make_server


@pytest.mark.parametrize("count", [24, 32])
def test_queued_studio_resource_connections_receive_complete_responses(workspace, count):
    resources = re.findall(r'(?:src|href)="(/static/[^\"]+)"', (WEB_ROOT / "studio.html").read_text())
    assert resources
    server = make_server(workspace, 0)
    accept_allowed, serving = threading.Event(), threading.Event()

    def run():
        accept_allowed.wait()
        serving.set()
        server.serve_forever()

    thread = threading.Thread(target=run, daemon=True)
    thread.start()
    connections = []
    try:
        # Establish the whole page burst before the server can accept any socket.
        # A small listen queue rejects/times out here even though the server is alive.
        for index in range(count):
            path = resources[index % len(resources)]
            connection = http.client.HTTPConnection("127.0.0.1", server.server_port, timeout=5)
            connections.append((connection, path))
            connection.connect()
            connection.request("GET", path)
        accept_allowed.set()
        assert serving.wait(5)
        for connection, path in connections:
            response = connection.getresponse()
            expected = (WEB_ROOT / path.removeprefix("/static/")).read_bytes()
            assert response.status == 200
            assert int(response.getheader("Content-Length")) == len(expected)
            assert response.read() == expected
    finally:
        accept_allowed.set()
        for connection, _ in connections:
            connection.close()
        assert serving.wait(5)
        server.shutdown()
        server.server_close()
        thread.join(5)
