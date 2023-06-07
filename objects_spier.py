import asyncio
import copy
import dataclasses
import functools
import inspect
from typing import Any, Callable, Dict, List, Optional, Sequence
from unittest.mock import AsyncMock, Mock

import pytest_mock

__all__ = ["create_object_spy", "Call"]


def create_object_spy(
    mocker: pytest_mock.MockerFixture,
    obj: object,
    callable_filter: Optional[Callable[[str], bool]] = None,
    mock_results: Optional[Dict[Callable[..., Any], List[Any]]] = None,
) -> "ObjectSpy":
    """
    define such fixture and use it

    @pytest.fixture
    def object_spy(mocker):
        return partial(create_object_spy, mocker)
    """
    object_spy = ObjectSpy(mock_results)
    filter_ = callable_filter or (lambda name: not name.startswith("__"))
    for attr_name in (attr for attr in dir(obj) if filter_(attr)):
        candidate_attr = getattr(obj, attr_name)
        if callable(candidate_attr):
            spy(mocker, obj, attr_name, object_spy)
    return object_spy


@dataclasses.dataclass
class Call:
    spy_obj: object
    args: Sequence[Any]
    kwargs: Dict[str, Any]
    result: Any
    exc: Optional[BaseException] = None


class ObjectSpy:
    def __init__(self, mock_calls: Optional[Dict[Callable[..., Any], List[Any]]] = None) -> None:
        self.calls: List[Call] = []
        self.mock_results = mock_calls or {}

    def append_to_calls(  # pylint: disable=too-many-arguments
        self, spy_obj: object, args: Sequence[Any], kwargs: Dict[str, Any], result: Any, exc: Optional[BaseException]
    ) -> None:
        self.calls.append(Call(spy_obj, args, kwargs, result, exc))


def spy(mocker: pytest_mock.MockerFixture, obj: object, name: str, object_spy: ObjectSpy) -> None:  # noqa: C901
    """
    Upgraded version on pytest_mock.MockerFixture.spy for custom fixture for spy of object callable attrs calls
    """
    method = getattr(obj, name)
    if inspect.isclass(obj) and isinstance(inspect.getattr_static(obj, name), (classmethod, staticmethod)):
        autospec = False
    else:
        autospec = inspect.ismethod(method) or inspect.isfunction(method)

    def wrapper(*args: Any, **kwargs: Any) -> Any:
        spy_obj.spy_return = None
        spy_obj.spy_exception = None
        if spy_obj.spy_method in object_spy.mock_results and object_spy.mock_results[spy_obj.spy_method]:
            spy_obj.spy_return = return_value = object_spy.mock_results[spy_obj.spy_method].pop(0)
        else:
            try:
                return_value = method(*args, **kwargs)
            except BaseException as exc:
                spy_obj.spy_exception = exc
                object_spy.append_to_calls(spy_obj, args, kwargs, spy_obj.spy_return, spy_obj.spy_exception)
                raise
            else:
                spy_obj.spy_return = return_value
        object_spy.append_to_calls(spy_obj, args, kwargs, spy_obj.spy_return, spy_obj.spy_exception)
        return return_value

    async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
        spy_obj.spy_return = None
        spy_obj.spy_exception = None
        if spy_obj.spy_method in object_spy.mock_results and object_spy.mock_results[spy_obj.spy_method]:
            spy_obj.spy_return = return_value = object_spy.mock_results[spy_obj.spy_method].pop(0)
        else:
            try:
                return_value = await method(*args, **kwargs)
            except BaseException as exc:
                spy_obj.spy_exception = exc
                object_spy.append_to_calls(spy_obj, args, kwargs, spy_obj.spy_return, spy_obj.spy_exception)
                raise
            else:
                spy_obj.spy_return = return_value
        object_spy.append_to_calls(spy_obj, args, kwargs, spy_obj.spy_return, spy_obj.spy_exception)
        return return_value

    if isinstance(method, Mock):
        if isinstance(method, AsyncMock):
            side_effect = async_wrapper
        else:
            side_effect = wrapper
        spy_obj = method
        spy_obj.spy_method = method
        method.side_effect, method = side_effect, copy.copy(method)
    else:
        if asyncio.iscoroutinefunction(method):
            wrapped = functools.update_wrapper(async_wrapper, method)
        else:
            wrapped = functools.update_wrapper(wrapper, method)
        spy_obj = mocker.patch.object(obj, name, side_effect=wrapped, autospec=autospec)
        spy_obj.spy_method = method
    spy_obj.spy_return, spy_obj.spy_exception = None, None
