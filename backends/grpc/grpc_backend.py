import dataclasses
from abc import ABC
from functools import partial
from typing import Any, Awaitable, Callable, Dict, Optional, Sequence, Type

import grpc  # type: ignore
from google.protobuf import message
from grpc._cython.cygrpc import _SyncServicerContext  # type: ignore # pylint: disable=no-name-in-module
from schema import Schema

from backends.abackend import ABackend


@dataclasses.dataclass
class GRPCRule:
    """
    A rule used by the gRPC backend to determine which result to give to the client
    based on the incoming request.

    """

    request_msg_cls: Type[message.Message]
    output_handler: Callable[..., bytes]
    grpc_method: Optional[str] = None
    message_args: Optional[Dict[Any, Any]] = None
    ignore_extra_message_args: bool = False

    def method_matches(self, method: str) -> bool:
        if self.grpc_method is None:
            return True
        return method.casefold() == self.grpc_method.casefold()

    def message_args_match(self, message_: message.Message) -> bool:
        if self.message_args is None:
            return True

        message_args = {field[0].name: field[1] for field in message_.ListFields()}
        return Schema(self.message_args, ignore_extra_keys=self.ignore_extra_message_args).is_valid(  # type: ignore
            message_args
        )


class GRPCBackend(ABackend, ABC):
    rules: Sequence[GRPCRule] = ()

    async def start_server(self) -> None:
        # Register the custom interceptor to handle rules
        server = grpc.aio.server(interceptors=(GRPCRuleInterceptor(self.rules),))

        listen_addr = f"[::]:{self.port}"
        server.add_insecure_port(listen_addr)

        await server.start()
        self.start_signal()
        await server.wait_for_termination()


class GRPCRuleInterceptor(grpc.aio.ServerInterceptor):  # type: ignore
    def __init__(self, rules: Sequence[GRPCRule]):
        self.rules = rules

    async def intercept_service(
        self,
        continuation: Callable[[grpc.HandlerCallDetails], Awaitable[grpc.RpcMethodHandler]],
        handler_call_details: grpc.HandlerCallDetails,
    ) -> Optional[grpc.RpcMethodHandler]:
        return grpc.unary_unary_rpc_method_handler(partial(self._handler, handler_call_details))

    def _handler(
        self, handler_call_details: grpc.HandlerCallDetails, request: bytes, context: _SyncServicerContext
    ) -> Optional[bytes]:
        grpc_method = handler_call_details.method  # noqa
        for rule in self.rules:
            if rule.method_matches(grpc_method):
                request_message = rule.request_msg_cls.FromString(request)
                if rule.message_args_match(request_message):
                    return rule.output_handler(request_message)
        context.abort(
            grpc.StatusCode.INVALID_ARGUMENT,
            "no matched GRPC rules found",
        )
        return None
