"""Tests for the query tag and query comment macros."""

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from context import (  # noqa: E402
    DBT_CLOUD_ENV,
    SESSION_TAG,
    query_comment,
    set_query_tag,
)

ALL_FIELDS = {"altimate_query_tag_fields": "all"}

SESSION_LEVEL_KEYS = {
    "dbt_integration_id", "dbt_integration_environment", "thread_id", "is_incremental",
}

# Every key the select package writes to QUERY_TAG, from the Altimate vs Select
# comparison. 'all' is expected to match this set exactly, except for select's
# own dbt_query_tags_version.
SELECT_PACKAGE_KEYS = [
    "dbt_integration_id", "dbt_integration_environment", "node_name", "node_alias",
    "node_package_name", "node_database", "node_schema", "node_id", "node_resource_type",
    "node_meta", "node_tags", "materialized", "app", "dbt_snowflake_query_tags_version",
    "dbt_version", "project_name", "target_name", "target_database", "target_schema",
    "invocation_id", "run_started_at", "full_refresh", "dbt_cloud_project_id",
    "dbt_cloud_job_id", "dbt_cloud_run_id", "thread_id", "is_incremental", "which",
    "node_original_file_path", "invocation_command", "node_refs", "raw_code_hash",
    "dbt_cloud_run_reason_category", "dbt_cloud_run_reason",
]

IDENTITY_KEYS = [
    "node_id", "node_name", "node_alias", "project_name", "invocation_id",
    "target_database", "target_schema", "dbt_integration_id", "dbt_integration_environment",
]


# --------------------------------------------------------------------------
# field sets
# --------------------------------------------------------------------------

def test_session_is_the_default():
    """An unchanged project must emit what it emitted on 2.0."""
    tag, _, _ = set_query_tag(session_tag=SESSION_TAG)
    assert set(tag) == SESSION_LEVEL_KEYS


def test_all_carries_the_full_metadata_set():
    tag, _, _ = set_query_tag(session_tag=SESSION_TAG, dbt_vars=ALL_FIELDS)
    assert tag["node_id"] == "model.jaffle.my_model"
    assert tag["project_name"] == "jaffle"


def test_all_matches_the_select_package_key_set():
    tag, _, _ = set_query_tag(session_tag=SESSION_TAG, env=DBT_CLOUD_ENV, dbt_vars=ALL_FIELDS)
    assert [key for key in SELECT_PACKAGE_KEYS if key not in tag] == []
    assert [key for key in tag if key not in SELECT_PACKAGE_KEYS] == []


def test_all_fits_the_limit_for_a_typical_node():
    tag, _, _ = set_query_tag(session_tag=SESSION_TAG, env=DBT_CLOUD_ENV, dbt_vars=ALL_FIELDS)
    assert len(json.dumps(tag)) < 2000


def test_query_comment_is_unaffected_by_tag_fields():
    comment = query_comment(env=DBT_CLOUD_ENV)
    for key in ("node_id", "node_meta", "raw_code_hash", "dbt_cloud_job_id", "invocation_command"):
        assert key in comment


# --------------------------------------------------------------------------
# user-supplied tags
# --------------------------------------------------------------------------

def test_model_level_query_tag_config_is_merged():
    for dbt_vars in ({}, ALL_FIELDS):
        tag, _, _ = set_query_tag(
            session_tag=SESSION_TAG, dbt_vars=dbt_vars,
            model_config={"query_tag": {"cost_center": "FIN-42"}},
        )
        assert tag["cost_center"] == "FIN-42"


def test_env_vars_to_query_tag_list_is_merged():
    tag, _, _ = set_query_tag(
        session_tag=SESSION_TAG,
        dbt_vars={"env_vars_to_query_tag_list": ["MY_RUN_OWNER"]},
        env={"MY_RUN_OWNER": "finance"},
    )
    assert tag["my_run_owner"] == "finance"


def test_fusion_quoted_dict_config_is_parsed():
    quoted = '"' + json.dumps({"cost_center": "FIN-42"}) + '"'
    tag, _, _ = set_query_tag(session_tag=SESSION_TAG, model_config={"query_tag": quoted})
    assert tag["cost_center"] == "FIN-42"


def test_non_mapping_config_is_ignored_with_a_warning():
    tag, logs, _ = set_query_tag(session_tag=SESSION_TAG, model_config={"query_tag": "a_string"})
    assert "a_string" not in json.dumps(tag)
    assert any("not a mapping type" in message for message in logs)


# --------------------------------------------------------------------------
# the 2000-character budget
# --------------------------------------------------------------------------

def test_oversized_tag_drops_expendable_fields_and_keeps_identity():
    tag, logs, _ = set_query_tag(
        session_tag=SESSION_TAG, dbt_vars=ALL_FIELDS, node_meta={"desc": "x" * 1500},
    )
    assert "node_meta" not in tag
    assert all(key in tag for key in IDENTITY_KEYS)
    assert len(json.dumps(tag)) <= 2000
    assert any("dropped" in message for message in logs)


def test_user_supplied_keys_survive_trimming():
    tag, _, _ = set_query_tag(
        session_tag=SESSION_TAG,
        dbt_vars=ALL_FIELDS,
        node_meta={"desc": "x" * 2500},
        model_config={"query_tag": {"cost_center": "FIN-42"}},
    )
    assert tag["cost_center"] == "FIN-42"
    assert len(json.dumps(tag)) <= 2000


def test_user_key_named_like_a_generated_field_survives_trimming():
    """A user value keyed 'node_meta' or 'thread_id' is theirs, not ours to drop."""
    tag, logs, _ = set_query_tag(
        session_tag=SESSION_TAG,
        dbt_vars=ALL_FIELDS,
        node_tags=["t" * 1800],  # forces trimming without exhausting the budget
        model_config={"query_tag": {"node_meta": "keep-me", "thread_id": "keep-me-too"}},
    )
    assert any("dropped" in message for message in logs), "expected trimming to run"
    assert tag["node_meta"] == "keep-me"
    assert tag["thread_id"] == "keep-me-too"
    assert len(json.dumps(tag)) <= 2000


def test_unfittable_tag_falls_back_to_the_original_session_tag():
    tag, logs, _ = set_query_tag(
        session_tag=SESSION_TAG, dbt_vars=ALL_FIELDS,
        model_config={"query_tag": {"blob": "y" * 2600}},
    )
    assert tag == json.loads(SESSION_TAG)
    assert any("cannot be reduced" in message for message in logs)


def test_max_length_var_lowers_the_ceiling():
    tag, _, _ = set_query_tag(
        session_tag=SESSION_TAG,
        dbt_vars={"altimate_query_tag_fields": "all", "altimate_query_tag_max_length": 400},
    )
    assert len(json.dumps(tag)) <= 400


def test_max_length_cannot_exceed_snowflakes_hard_limit():
    """The var may lower Snowflake's ceiling, never raise it."""
    tag, logs, _ = set_query_tag(
        session_tag=SESSION_TAG,
        dbt_vars={"altimate_query_tag_fields": "all", "altimate_query_tag_max_length": 3000},
        node_meta={"desc": "x" * 2500},
    )
    assert len(json.dumps(tag)) <= 2000
    assert any("hard limit" in message for message in logs)


def test_max_length_accepts_a_quoted_yaml_value():
    """A YAML value of "400" is a string; comparing it to a length must not raise."""
    tag, _, _ = set_query_tag(
        session_tag=SESSION_TAG,
        dbt_vars={"altimate_query_tag_fields": "all", "altimate_query_tag_max_length": "400"},
    )
    assert len(json.dumps(tag)) <= 400


def test_max_length_rejects_a_non_numeric_value():
    tag, logs, _ = set_query_tag(
        session_tag=SESSION_TAG,
        dbt_vars={"altimate_query_tag_fields": "all", "altimate_query_tag_max_length": "not a number"},
    )
    assert len(json.dumps(tag)) <= 2000
    assert any("hard limit" in message for message in logs)


def test_boundary_at_the_configured_limit():
    """A tag exactly at the limit is kept; one character over is trimmed."""
    tag, _, _ = set_query_tag(session_tag=SESSION_TAG, dbt_vars=ALL_FIELDS)
    exact = len(json.dumps(tag))

    kept, logs, _ = set_query_tag(
        session_tag=SESSION_TAG,
        dbt_vars={"altimate_query_tag_fields": "all", "altimate_query_tag_max_length": exact},
    )
    assert len(json.dumps(kept)) == exact and logs == []

    trimmed, logs, _ = set_query_tag(
        session_tag=SESSION_TAG,
        dbt_vars={"altimate_query_tag_fields": "all", "altimate_query_tag_max_length": exact - 1},
    )
    assert len(json.dumps(trimmed)) < exact
    assert any("dropped" in message for message in logs)


def test_exclude_var_removes_keys():
    tag, _, _ = set_query_tag(
        session_tag=SESSION_TAG,
        dbt_vars={
            "altimate_query_tag_fields": "all",
            "altimate_query_tag_exclude": ["raw_code_hash", "node_meta"],
        },
    )
    assert "raw_code_hash" not in tag and "node_meta" not in tag


# --------------------------------------------------------------------------
# input handling
# --------------------------------------------------------------------------

def test_unknown_value_warns_and_falls_back_to_the_default():
    tag, logs, _ = set_query_tag(
        session_tag=SESSION_TAG, dbt_vars={"altimate_query_tag_fields": "EVERYTHING"}
    )
    assert set(tag) == SESSION_LEVEL_KEYS
    assert any("is not recognised" in message for message in logs)


def test_values_are_trimmed_and_case_insensitive():
    for value in ("ALL", " all ", "Session", " session"):
        tag, logs, _ = set_query_tag(
            session_tag=SESSION_TAG, dbt_vars={"altimate_query_tag_fields": value}
        )
        assert logs == [], "%r should be accepted, got %r" % (value, logs)
        assert ("node_id" in tag) is (value.strip().lower() == "all")


def test_missing_or_invalid_session_tag_is_tolerated():
    for session_tag in (None, "not json at all"):
        tag, _, _ = set_query_tag(session_tag=session_tag, dbt_vars=ALL_FIELDS)
        assert tag["node_id"] == "model.jaffle.my_model"


def test_non_model_nodes():
    for resource_type in ("seed", "test", "snapshot"):
        tag, _, _ = set_query_tag(
            session_tag=SESSION_TAG, dbt_vars=ALL_FIELDS, resource_type=resource_type
        )
        assert "is_incremental" not in tag
        assert tag["node_resource_type"] == resource_type


def test_seeds_omit_node_refs():
    tag, _, _ = set_query_tag(session_tag=SESSION_TAG, dbt_vars=ALL_FIELDS, resource_type="seed")
    assert "node_refs" not in tag


def test_single_quotes_are_escaped_in_the_alter_session_statement():
    tag, _, statement = set_query_tag(
        session_tag=SESSION_TAG, model_config={"query_tag": {"note": "O'Brien"}}
    )
    assert "O''Brien" in statement
    assert tag["note"] == "O'Brien"


def test_model_without_refs():
    tag, _, _ = set_query_tag(session_tag=SESSION_TAG, dbt_vars=ALL_FIELDS, refs=[])
    assert tag["node_id"] == "model.jaffle.my_model"


if __name__ == "__main__":
    failures = 0
    for name, function in sorted(globals().items()):
        if name.startswith("test_") and callable(function):
            try:
                function()
                print("PASS  " + name)
            except AssertionError as error:
                failures += 1
                print("FAIL  %s: %s" % (name, error))
    print("\n%d failed" % failures if failures else "\nall tests passed")
    sys.exit(1 if failures else 0)
