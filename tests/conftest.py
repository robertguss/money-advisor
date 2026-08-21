from __future__ import annotations

from collections.abc import Mapping

from finances.mercury import HttpResponse


class FakeHttp:
    def __init__(self, routes: Mapping[str, str]) -> None:
        self.routes = dict(routes)
        self.urls: list[str] = []

    def get(self, url: str, headers: Mapping[str, str]) -> HttpResponse:
        self.urls.append(url)
        for suffix, body in self.routes.items():
            if url.endswith(suffix) or suffix in url:
                return HttpResponse(200, body)
        return HttpResponse(404, "{}")
