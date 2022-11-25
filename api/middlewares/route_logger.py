import logging
import time
import typing
from typing import Callable
from uuid import uuid4

from fastapi import FastAPI, Request, Response
from starlette.datastructures import Headers
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import Scope, Receive, Send

from utils.logger import get_logger, set_correlation_id, set_session_id


class RouteLoggerMiddleware(BaseHTTPMiddleware):
    _cid_header: str = 'x-request-id'  # request correlation key header name
    _sid_header: str = 'x-session-id'  # session correlation key header name
    _cfray_header: str = 'cf-ray'

    def __init__(
            self,
            app: FastAPI,
            *,
            logger: typing.Optional[logging.Logger] = None,
            skip_routes: typing.List[str] = None,
    ):
        self._logger = logger or get_logger(__name__)
        self._skip_routes = skip_routes or []
        super().__init__(app)

    async def __call__(self, scope: Scope, receive: Receive, send: Send):
        """ Headers object is immutable. We should update headers before calling dispatch method """

        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        headers_dict = Headers(scope=scope)

        if self._cid_header not in headers_dict:
            request_id = headers_dict.get(self._cfray_header, uuid4().hex)
            scope['headers'].append((self._cid_header.encode(), request_id.encode()))

        if self._sid_header in headers_dict:
            set_session_id(headers_dict[self._sid_header])

        set_correlation_id(headers_dict[self._cid_header])
        await super().__call__(scope, receive, send)

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        if self._should_route_be_skipped(request):
            return await call_next(request)

        return await self._execute_request_with_logging(request, call_next)

    def _should_route_be_skipped(self, request: Request) -> bool:
        return any(
            [path for path in self._skip_routes if request.url.path.startswith(path)]
        )

    async def _execute_request_with_logging(
            self, request: Request, call_next: Callable
    ) -> Response:
        start_time = time.perf_counter()

        response = await self._execute_request(call_next, request)
        response.headers[self._cid_header] = request.headers[self._cid_header]

        finish_time = time.perf_counter()
        duration = round(finish_time - start_time, 4)
        log_args = {
            "request_method": request.method,
            "request_path": request.url.path,
            "request_duration": duration,
            "response_status": response.status_code,
        }
        msg = f"Request {'successful' if response.status_code < 500 else 'failed'}"
        self._logger.info(msg, log_args, extra=log_args)

        return response

    async def _execute_request(self, call_next: Callable, request: Request) -> Response:
        try:
            response = await call_next(request)
        except Exception:
            log_args = {
                "request_method": request.method,
                "request_path": request.url.path,
                "response_status": 500,
            }
            self._logger.exception(
                "Request failed with exception", log_args, extra=log_args
            )
            raise
        return response
