import logging
from unittest.mock import Mock

import pytest
from schema import Regex, Schema, SchemaError

from asserts import (
    assert_equal_dicts,
    assert_equal_api_access_log,
    assert_equal_api_extra_log,
    assert_equalapi_response,
    assert_equal_log_message,
)

AE = pytest.raises(AssertionError)


class TestAssertEqualDicts:
    def test_assert_equal_dicts_verbosity(self):
        assert_equal_dicts({"a": 1}, a=1)  # no AssertionError raises
        with AE as assertion_error:
            assert_equal_dicts({"a": 2}, a=1)
        # SchemaError add verbosity for failed assert_equal_dicts() calls
        with pytest.raises(SchemaError) as schema_error:
            Schema({"a": 1}).validate({"a": 2})
        assert assertion_error.value.__cause__ is None  # force clean traceback
        assert assertion_error.value.args[0] == schema_error.value.code  # but save verbosity from SchemaError

    def test_assert_equal_dicts(self):
        actual_dict = {
            "foo": "bar",
            "foo1": "bar1",
            "nested1": {"nested1_foo": "nested1_bar", "nested2": {"nested2_foo": "nested2_bar"}},
        }
        assert_equal_dicts(actual_dict, **actual_dict)
        assert_equal_dicts(
            actual_dict,
            foo="bar",
            foo1=Regex("ba.*"),
            nested1={"nested1_foo": "nested1_bar", "nested2": {"nested2_foo": Regex("ne.*2.*bar")}},
        )
        with AE:
            assert_equal_dicts(actual_dict, foo2="bar2")
        with AE:
            assert_equal_dicts(actual_dict, foo3="bar3")
        with AE:
            assert_equal_dicts(actual_dict, foo="bar", foo1=Regex("fo.*"))
        with AE:
            assert_equal_dicts(actual_dict, foo="bar", foo1=Regex("fo.*"), nested1={"nested1_foo": "nested1_bar"})
        with AE:
            assert_equal_dicts(
                actual_dict,
                foo="bar",
                foo1=Regex("fo.*"),
                nested1={"nested2": {"nested2_foo": Regex("ne.*2.*bar")}},
            )

    def test_assert_equal_dicts_ignore_extra_keys(self):
        actual_dict = {
            "foo": "bar",
            "foo1": "bar1",
            "nested1": {"nested1_foo": "nested1_bar", "nested2": {"nested2_foo": "nested2_bar"}},
        }
        assert_equal_dicts(actual_dict, _ignore_extra_keys=True, **actual_dict)
        assert_equal_dicts(actual_dict, _ignore_extra_keys=True, foo="bar")
        assert_equal_dicts(actual_dict, _ignore_extra_keys=True, foo1=Regex("ba.*"))
        with AE:
            assert_equal_dicts(actual_dict, _ignore_extra_keys=True, foo2="bar2")
        with AE:
            assert_equal_dicts(actual_dict, _ignore_extra_keys=True, foo="bar", foo1=Regex("fo.*"))
        assert_equal_dicts(actual_dict, _ignore_extra_keys=True, foo="bar", nested1={"nested1_foo": "nested1_bar"})
        assert_equal_dicts(actual_dict, _ignore_extra_keys=True, foo="bar", nested1={"nested2": {}})
        assert_equal_dicts(
            actual_dict, _ignore_extra_keys=True, nested1={"nested2": {"nested2_foo": Regex("ne.*2.*bar")}}
        )
        with AE:
            assert_equal_dicts(actual_dict, _ignore_extra_keys=True, foo="bar", nested1={"nested1_foo": "nested2_bar"})
        with AE:
            assert_equal_dicts(actual_dict, _ignore_extra_keys=True, foo="bar", nested1={"nested2": "nested2_bar"})
        with AE:
            assert_equal_dicts(
                actual_dict, _ignore_extra_keys=True, nested1={"nested2": {"nested3_foo": Regex("ne.*2.*bar")}}
            )


def test_assert_equalapi_response():
    actual_response = {"qid": "123", "api_version": "1.0", "foo": "bar", "nested1": {"nested1_foo": "nested1_bar"}}
    assert_equalapi_response(actual_response, foo="bar", nested1={"nested1_foo": "nested1_bar"})
    assert_equalapi_response(actual_response, foo=Regex("ba.*"), nested1={"nested1_foo": "nested1_bar"})
    assert_equalapi_response(actual_response, _ignore_extra_keys=True, foo="bar")
    assert_equalapi_response(actual_response, _ignore_extra_keys=True, nested1={"nested1_foo": "nested1_bar"})
    with AE:
        assert_equalapi_response(actual_response, foo="foo")
    with AE:
        assert_equalapi_response(actual_response, foo=Regex("fo.*"))
    with AE:
        assert_equalapi_response(actual_response, bar="bar")
    with AE:
        assert_equalapi_response(actual_response, _ignore_extra_keys=True, nested2={"nested1_foo": "nested1_bar"})
    with AE:
        assert_equalapi_response(actual_response, _ignore_extra_keys=True, foo="bar1")
    with AE:
        assert_equalapi_response(actual_response, _ignore_extra_keys=True, foo=Regex("fo.*"))


@pytest.mark.parametrize("log_sep, log_kv_sep", (("\t", ":"), (":", "\t")))
def test_assert_equal_log_message(log_sep, log_kv_sep):
    mock_actual_log = Mock(spec=logging.LogRecord)
    log_msg_elems = {"QID": "3b7e49d1504a403980a4c852f9f944b6", "IP": "127.0.0.1", "METHOD": "GET", "Q": "query"}
    mock_actual_log.message = log_sep.join(f"{log_k}{log_kv_sep}{log_v}" for log_k, log_v in log_msg_elems.items())
    separators = {"_log_separator": log_sep, "_log_kv_separator": log_kv_sep}
    assert_equal_log_message(mock_actual_log, **separators, **log_msg_elems)
    assert_equal_log_message(
        mock_actual_log,
        **separators,
        QID=Regex(".*"),
        IP="127.0.0.1",
        METHOD="GET",
        Q=Regex(".*"),
    )
    assert_equal_log_message(mock_actual_log, **separators, _ignore_extra_keys=True, IP="127.0.0.1")
    assert_equal_log_message(mock_actual_log, **separators, _ignore_extra_keys=True, QID=Regex(".*"))
    with AE:
        assert_equal_log_message(
            mock_actual_log,
            **separators,
            QID=Regex(".*"),
            IP="127.0.0.1",
            METHOD="POST",
            Q=Regex(".*"),
        )
    with AE:
        assert_equal_log_message(
            mock_actual_log,
            **separators,
            _ignore_extra_keys=True,
            QID=Regex(".*foo.*"),
        )
    with AE:
        assert_equal_log_message(
            mock_actual_log,
            **separators,
            _ignore_extra_keys=True,
            IP="127.0.0",
        )
    with AE:
        assert_equal_log_message(
            mock_actual_log,
            **separators,
            _ignore_extra_keys=True,
            FOO="BAR",
        )


def test_assert_equal_api_access_log():
    mock_actual_access_log = Mock(spec=logging.LogRecord)
    log_msg_elems = {
        "QID": "3b7e49d1504a403980a4c852f9f944b6",
        "METHOD": "GET",
        "REQUEST_TIME": "15.5",
        "STATUS": "200",
        "REMOTE": "127.0.0.1",
        "URL": "http://localhost:8100/search",
        "USER_AGENT": "user_agent",
    }
    mock_actual_access_log.message = "\t".join(f"{log_k}:{log_v}" for log_k, log_v in log_msg_elems.items())
    assert_equal_api_access_log(mock_actual_access_log)
    with AE:
        assert_equal_api_access_log(mock_actual_access_log, FOO="BAR")
    with AE:
        assert_equal_api_access_log(mock_actual_access_log, _ignore_extra_keys=True, FOO="BAR")
    log_msg_elems["FOO"] = "BAR"
    mock_actual_access_log.message = "\t".join(f"{log_k}:{log_v}" for log_k, log_v in log_msg_elems.items())
    with AE:
        assert_equal_api_access_log(mock_actual_access_log)
    assert_equal_api_access_log(mock_actual_access_log, FOO="BAR")
    assert_equal_api_access_log(mock_actual_access_log, _ignore_extra_keys=True)
    assert_equal_api_access_log(mock_actual_access_log, _ignore_extra_keys=True, FOO="BAR")


def test_assert_equal_api_extra_log():
    mock_actual_extra_log = Mock(spec=logging.LogRecord)
    log_msg_elems = {
        "QID": "3b7e49d1504a403980a4c852f9f944b6",
    }
    mock_actual_extra_log.message = "\t".join(f"{log_k}:{log_v}" for log_k, log_v in log_msg_elems.items())
    assert_equal_api_extra_log(mock_actual_extra_log)
    with AE:
        assert_equal_api_extra_log(mock_actual_extra_log, FOO="BAR")
    with AE:
        assert_equal_api_extra_log(mock_actual_extra_log, _ignore_extra_keys=True, FOO="BAR")
    log_msg_elems[
        "APPS_ID"
    ] = '["317631","683796415","682687","315839","938943","313279","938687","311231","99092415","494736063"]'
    mock_actual_extra_log.message = "\t".join(f"{log_k}:{log_v}" for log_k, log_v in log_msg_elems.items())
    with AE:
        assert_equal_api_extra_log(mock_actual_extra_log)
    assert_equal_api_extra_log(
        mock_actual_extra_log,
        APPS_ID='["317631","683796415","682687","315839","938943","313279","938687","311231","99092415","494736063"]',
    )
    assert_equal_api_extra_log(mock_actual_extra_log, _ignore_extra_keys=True)
    assert_equal_api_extra_log(
        mock_actual_extra_log,
        _ignore_extra_keys=True,
        APPS_ID='["317631","683796415","682687","315839","938943","313279","938687","311231","99092415","494736063"]',
    )
