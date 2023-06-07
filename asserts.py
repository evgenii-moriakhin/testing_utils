""" useful assert statements for tests """

import logging
from functools import partial
from typing import Any, Dict

import schema


def assert_equal_dicts(actual: Dict[Any, Any], _ignore_extra_keys: bool = False, **expected: Any) -> None:
    """
    Schema-library wrapper for check dicts equality
    with _ignore_extra_keys is True checks only subset actual dict keys, otherwise all actual dict keys

    :raises:
        AssertionError: if actual dict is not valid, with SchemaError.code verbose fail info
    """
    try:
        schema.Schema(expected, ignore_extra_keys=_ignore_extra_keys).validate(actual)
    except schema.SchemaError as schema_exc:
        # add verbosity for AssertionError via SchemaError.code, but force clean traceback
        raise AssertionError(schema_exc.code) from None


# all responses for ... based applications have qid and api_version fields
assert_equalapi_response = partial(assert_equal_dicts, qid=schema.Regex(".*"), api_version="1.0")


def assert_equal_log_message(
    log_record: logging.LogRecord,
    _log_separator: str,
    _log_kv_separator: str,
    _ignore_extra_keys: bool = False,
    **expected_log: Any,
) -> None:
    """
    assert_equal_dicts() wrapper for check log msgs such
    QID:3b7e49d1504a403980a4c852f9f944b6, IP:127.0.0.1, METHOD:GET etc
    """
    log_msg_items = {}
    for log in log_record.message.split(_log_separator):
        key, val = log.split(_log_kv_separator, maxsplit=1)
        log_msg_items[key] = val
    assert_equal_dicts(log_msg_items, _ignore_extra_keys, **expected_log)


# check main extra log field QID
assert_equal_api_extra_log = partial(
    assert_equal_log_message,
    _log_separator="\t",
    _log_kv_separator=":",
    QID=schema.Regex(".*"),
)

# check main access log fields
assert_equal_api_access_log = partial(
    assert_equal_log_message,
    _log_separator="\t",
    _log_kv_separator=":",
    QID=schema.Regex(".*"),
    METHOD=schema.Regex(".*"),
    REMOTE=schema.Regex(".*"),
    REQUEST_TIME=schema.Regex(".*"),
    STATUS=schema.Regex(".*"),
    URL=schema.Regex(".*"),
    USER_AGENT=schema.Regex(".*"),
)
