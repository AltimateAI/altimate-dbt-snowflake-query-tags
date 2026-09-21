"""Minimal dbt macro context for exercising this package's macros off-warehouse.

dbt's own integration tests need a live Snowflake account. These stubs render
the macros with Jinja directly so the tag-building logic can be tested in CI,
covering everything except the `alter session` statement actually reaching
Snowflake, which is captured and asserted on instead.

Requires jinja2. Run with `pytest tests/` or `python tests/test_query_tags.py`.
"""

import datetime
import hashlib
import json
import os
import types

from jinja2 import Environment, FileSystemLoader

MACRO_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "macros")
MACRO_FILES = ("build_metadata.sql", "fit_query_tag.sql", "query_comment.sql", "set_query_tag.sql")

SESSION_TAG = '{"dbt_integration_id": 228, "dbt_integration_environment": "PRD_404733"}'
DBT_CLOUD_ENV = {
    "DBT_CLOUD_PROJECT_ID": "466993",
    "DBT_CLOUD_JOB_ID": "967971",
    "DBT_CLOUD_RUN_ID": "474622739",
    "DBT_CLOUD_RUN_REASON_CATEGORY": "scheduled",
    "DBT_CLOUD_RUN_REASON": "Kicked off from UI",
}


class MacroReturn(Exception):
    """dbt's return() raises rather than returning; macros are wrapped to match."""

    def __init__(self, value):
        self.value = value


def _returns(macro):
    def wrapper(*args, **kwargs):
        try:
            return macro(*args, **kwargs)
        except MacroReturn as raised:
            return raised.value

    return wrapper


def _parses_as_json(value):
    if not isinstance(value, str):
        return False
    try:
        json.loads(value)
    except ValueError:
        return False
    return True


class Config:
    """Stand-in for dbt's `config` context member."""

    def __init__(self, values):
        self.values = values or {}

    def get(self, key, default=None):
        return self.values.get(key, default)


def build_context(
    session_tag=None,
    dbt_vars=None,
    env=None,
    model_config=None,
    resource_type="model",
    node_meta=None,
    node_tags=None,
    refs=None,
):
    """Render the macros against a stubbed context.

    Returns (context, executed_queries, log_messages).
    """
    dbt_vars = dbt_vars or {}
    env = env or {}
    queries = []
    logs = []

    model = types.SimpleNamespace(
        name="my_model",
        alias="my_model",
        package_name="jaffle",
        original_file_path="models/marts/my_model.sql",
        database="ANALYTICS",
        schema="MARTS",
        unique_id="model.jaffle.my_model",
        resource_type=resource_type,
        tags=["nightly"] if node_tags is None else node_tags,
        config=types.SimpleNamespace(
            meta={} if node_meta is None else node_meta,
            materialized="incremental",
        ),
        refs=[types.SimpleNamespace(name="stg_orders")] if refs is None else refs,
        raw_code="select 1",
    )

    context = {
        "get_current_query_tag": lambda: session_tag,
        "fromjson": lambda s, default=None: json.loads(s) if _parses_as_json(s) else default,
        "tojson": lambda o, default=None, sort_keys=False: json.dumps(o, sort_keys=sort_keys),
        "var": lambda key, default=None: dbt_vars.get(key, default),
        "env_var": lambda key, default=None: env.get(key, default),
        "log": lambda msg, info=False: logs.append(msg),
        "run_query": queries.append,
        "config": Config(model_config),
        "model": model,
        "thread_id": "Thread-2 (worker)",
        "execute": True,
        "is_incremental": lambda: True,
        "dbt_version": "1.12.5",
        "project_name": "jaffle",
        "target": types.SimpleNamespace(name="prod", database="ANALYTICS", schema="MARTS"),
        "invocation_id": "0b8b7a1e-34c9-4203-9dc6-bd288ca17e46",
        "run_started_at": datetime.datetime(2026, 9, 21, 18, 34, 53, tzinfo=datetime.timezone.utc),
        "flags": types.SimpleNamespace(
            FULL_REFRESH=False, WHICH="run", INVOCATION_COMMAND="dbt run --target prod"
        ),
        "local_md5": lambda s: hashlib.md5(s.encode()).hexdigest(),
        "return": _raise_return,
    }

    environment = Environment(
        loader=FileSystemLoader(MACRO_DIR), extensions=["jinja2.ext.do"]
    )
    package = types.SimpleNamespace()
    for filename in MACRO_FILES:
        module = environment.get_template(filename).make_module(vars=context)
        for name in dir(module):
            attribute = getattr(module, name)
            if callable(attribute) and not name.startswith("_"):
                wrapped = _returns(attribute)
                context[name] = wrapped
                setattr(package, name, wrapped)
        context["altimate_snowflake_query_tags"] = package

    return context, queries, logs


def _raise_return(value=None):
    raise MacroReturn(value)


def set_query_tag(**kwargs):
    """Run default__set_query_tag and return (tag_dict, logs, statement)."""
    context, queries, logs = build_context(**kwargs)
    context["default__set_query_tag"]()
    assert len(queries) == 1, "expected exactly one alter session statement: %r" % queries

    statement = queries[0]
    prefix = "alter session set query_tag = '"
    assert statement.startswith(prefix) and statement.endswith("'"), statement

    payload = statement[len(prefix): -1].replace("''", "'")
    return (json.loads(payload) if payload else {}), logs, statement


def query_comment(**kwargs):
    """Run get_query_comment and return the parsed comment dict."""
    context, _, _ = build_context(**kwargs)
    return json.loads(context["get_query_comment"](context["model"]))
