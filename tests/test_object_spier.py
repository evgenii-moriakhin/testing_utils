import inspect
from unittest.mock import AsyncMock, Mock

import pytest

from testing.objects_spier import Call


class CatUnderSpy:
    exc = Exception("wtf")

    def __init__(self, name: str = "Default Cat"):
        self._name = name
        self._weight = 200

    def __call__(self):
        return self

    def get_name(self) -> str:
        return self._name

    def see_laser_ray(self):
        raise self.exc

    def _add_weight(self, g: float):
        self._weight += g

    def mew(self):
        if self._weight < 1:
            print("mew")
        elif self._weight < 4:
            print("Mew")
        else:
            print("MEW")

    async def eat_feed(self, g: float):
        self._add_weight(g=0.05 * g)

    @staticmethod
    def create_cat(name: str):
        return CatUnderSpy(name)

    def __eq__(self, other):
        if isinstance(other, CatUnderSpy):
            if self._weight == self._weight and self.get_name() == self.get_name():
                return True
        return False


class TestObjectSpyFixture:
    async def test_methods_spy(self, object_spy):
        cat = CatUnderSpy("Kis")
        cat_spy = object_spy(cat)

        await cat.eat_feed(50)
        cat._add_weight(100)
        await cat.eat_feed(100)

        assert cat_spy.calls == [
            Call(cat._add_weight, args=(), kwargs={"g": 2.5}, result=None, exc=None),
            Call(cat.eat_feed, args=(50,), kwargs={}, result=None, exc=None),
            Call(cat._add_weight, args=(100,), kwargs={}, result=None, exc=None),
            Call(cat._add_weight, args=(), kwargs={"g": 5}, result=None, exc=None),
            Call(cat.eat_feed, args=(100,), kwargs={}, result=None, exc=None),
        ]
        assert cat.eat_feed.await_count == 2

    def test_magic_method(self, object_spy):
        cat = CatUnderSpy("Kis")
        cat_spy = object_spy(cat)

        _ = CatUnderSpy("Another Kis") == cat

        assert cat_spy.calls == []

    def test_return_value(self, object_spy):
        cat = CatUnderSpy("Kis")
        cat_spy = object_spy(cat)

        cat.get_name()

        assert cat_spy.calls == [Call(cat.get_name, args=(), kwargs={}, result="Kis", exc=None)]

    def test_spy_mock_return_value(self, object_spy, mocker):
        cat = CatUnderSpy("Kis")
        mocker.patch.object(cat, "get_name", return_value="foo")
        cat_spy = object_spy(cat)

        assert cat.get_name() == "foo"
        assert cat_spy.calls == [Call(cat.get_name, args=(), kwargs={}, result="foo", exc=None)]

    async def test_spy_async_mock_return_value(self, object_spy, mocker):
        cat = CatUnderSpy("Kis")
        mocker.patch.object(cat, "get_name", AsyncMock(return_value="foo"))
        cat_spy = object_spy(cat)

        name = await cat.get_name()

        assert name == "foo"
        cat.get_name.await_count = 1
        assert cat_spy.calls == [Call(cat.get_name, args=(), kwargs={}, result="foo", exc=None)]

    def test_raise_exception(self, object_spy):
        cat = CatUnderSpy("Kis")
        cat_spy = object_spy(cat)

        try:
            cat.see_laser_ray()
        except:  # noqa
            pass

        assert cat_spy.calls == [Call(cat.see_laser_ray, args=(), kwargs={}, result=None, exc=CatUnderSpy.exc)]

    def test_spy_mock_raise_exception(self, object_spy, mocker):
        cat = CatUnderSpy("Kis")
        exc = Exception("...")
        mocker.patch.object(cat, "get_name", side_effect=exc)
        cat_spy = object_spy(cat)

        with pytest.raises(Exception) as err:
            cat.get_name()
        assert err.value is exc
        assert cat_spy.calls == [Call(cat.get_name, args=(), kwargs={}, result=None, exc=exc)]

    async def test_spy_async_mock_raise_exception(self, object_spy, mocker):
        cat = CatUnderSpy("Kis")
        exc = Exception("...")
        mocker.patch.object(cat, "get_name", AsyncMock(side_effect=exc))
        cat_spy = object_spy(cat)

        with pytest.raises(Exception) as err:
            await cat.get_name()
        assert err.value is exc
        cat.get_name.await_count = 1

        assert cat_spy.calls == [Call(cat.get_name, args=(), kwargs={}, result=None, exc=exc)]

    def test_filter_name(self, object_spy):
        cat = CatUnderSpy("Kis")
        cat_spy = object_spy(cat, callable_filter=lambda name: name == "get_name")

        cat._add_weight(100)

        assert cat_spy.calls == []

    def test_mock_return_value(self, object_spy):
        cat = CatUnderSpy("Kis")
        cat_spy = object_spy(cat, mock_results={cat.get_name: ["foo", "bar", None]})

        assert cat.get_name() == "foo"
        assert cat.get_name() == "bar"
        assert cat.get_name() is None
        assert cat.get_name() == "Kis"
        assert cat_spy.calls == [
            Call(cat.get_name, args=(), kwargs={}, result="foo", exc=None),
            Call(cat.get_name, args=(), kwargs={}, result="bar", exc=None),
            Call(cat.get_name, args=(), kwargs={}, result=None, exc=None),
            Call(cat.get_name, args=(), kwargs={}, result="Kis", exc=None),
        ]

    def test_mock_return_value_for_mock(self, object_spy, mocker):
        cat = CatUnderSpy("Kis")
        mocker.patch.object(cat, "get_name", return_value="foo_bar")
        cat_spy = object_spy(cat, mock_results={cat.get_name: ["foo", "bar", None]})

        assert cat.get_name() == "foo"
        assert cat.get_name() == "bar"
        assert cat.get_name() is None
        assert cat.get_name() == "foo_bar"
        assert cat_spy.calls == [
            Call(cat.get_name, args=(), kwargs={}, result="foo", exc=None),
            Call(cat.get_name, args=(), kwargs={}, result="bar", exc=None),
            Call(cat.get_name, args=(), kwargs={}, result=None, exc=None),
            Call(cat.get_name, args=(), kwargs={}, result="foo_bar", exc=None),
        ]

    @pytest.mark.parametrize("under_spy", (CatUnderSpy("Kis"), CatUnderSpy))
    def test_new_spy_object_attrs(self, object_spy, mocker, under_spy):
        cat = under_spy()
        mocker.patch.object(cat, "get_name")
        cat_initial_attrs = {attr_name: getattr(cat, attr_name) for attr_name in dir(cat)}

        _ = object_spy(cat)

        for attr_name in dir(cat):
            attr = getattr(cat, attr_name)
            if callable(attr) and not attr_name.startswith("__"):
                if isinstance(cat_initial_attrs[attr_name], Mock):
                    assert attr is cat_initial_attrs[attr_name]
                else:
                    assert attr is not cat_initial_attrs[attr_name]

                    # check autospec from regular mocker.spy functional
                    if not (
                        inspect.isclass(cat)
                        and isinstance(inspect.getattr_static(cat, attr_name), (classmethod, staticmethod))
                    ):
                        some_mock = mocker.patch.object(CatUnderSpy("Some Cat"), attr_name, autospec=True)
                        assert isinstance(attr, type(some_mock))
                    else:
                        assert isinstance(attr, Mock)
            elif not callable(attr) and not attr_name.startswith("__"):
                assert attr is cat_initial_attrs[attr_name]
            else:
                # cat__eq__ is not cat__eq__ and other magic methods
                assert isinstance(attr, type(cat_initial_attrs[attr_name]))
