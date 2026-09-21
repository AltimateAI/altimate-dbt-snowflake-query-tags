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

FULL = {"altimate_query_tag_level": "full"}

# Every key the select package writes to QUERY_TAG, from the Altimate vs Select
# comparison. `full` mode is expected to match this set exactly, except for
# select's own dbt_query_tags_version.
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


def test_lean_is_the_default():
    tag, _, _ = set_query_tag(session_tag=SESSION_TAG)
    assert set(tag) == {
        "dbt_integration_id", "dbt_integration_environment", "thread_id", "is_incremental",
    }


def test_full_matches_the_select_package_key_set():
    tag, _, _ = set_query_tag(session_tag=SESSION_TAG, env=DBT_CLOUD_ENV, dbt_vars=FULL)
    assert [key for key in SELECT_PACKAGE_KEYS if key not in tag] == []
    assert [key for key in tag if key not in SELECT_PACKAGE_KEYS] == []


def test_full_fits_the_limit_for_a_typical_node():
    tag, _, _ = set_query_tag(session_tag=SESSION_TAG, env=DBT_CLOUD_ENV, dbt_vars=FULL)
    assert len(json.dumps(tag)) < 2000


def test_query_comment_is_unaffected_by_tag_level():
    comment = query_comment(env=DBT_CLOUD_ENV)
    for key in ("node_id", "node_meta", "raw_code_hash", "dbt_cloud_job_id", "invocation_command"):
        assert key in comment


def test_model_level_query_tag_config_is_merged():
    for dbt_vars in ({}, FULL):
        tag, _, _ = set_query_tag(
            session_tag=SESSION_TAG, dbt_vars=dbt_vars, model_config={"query_tag": {"cost_center": "FIN-42"}}
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


def test_oversized_tag_drops_expendable_fields_and_keeps_identity():
    tag, logs, _ = set_query_tag(
        session_tag=SESSION_TAG, dbt_vars=FULL, node_meta={"desc": "x" * 1500}
    )
    assert "node_meta" not in tag
    assert all(key in tag for key in IDENTITY_KEYS)
    assert len(json.dumps(tag)) <= 2000
    assert any("dropped" in message for message in logs)


def test_user_supplied_keys_survive_trimming():
    tag, _, _ = set_query_tag(
        session_tag=SESSION_TAG,
        dbt_vars=FULL,
        node_meta={"desc": "x" * 2500},
        model_config={"query_tag": {"cost_center": "FIN-42"}},
    )
    assert tag["cost_center"] == "FIN-42"
    assert len(json.dumps(tag)) <= 2000


def test_unfittable_tag_falls_back_to_the_original_session_tag():
    tag, logs, _ = set_query_tag(
        session_tag=SESSION_TAG, dbt_vars=FULL, model_config={"query_tag": {"blob": "y" * 2600}}
    )
    assert tag == json.loads(SESSION_TAG)
    assert any("cannot be reduced" in message for message in logs)


def test_max_length_var_is_respected():
    tag, _, _ = set_query_tag(
        session_tag=SESSION_TAG,
        dbt_vars={"altimate_query_tag_level": "full", "altimate_query_tag_max_length": 400},
    )
    assert len(json.dumps(tag)) <= 400


def test_exclude_var_removes_keys():
    tag, _, _ = set_query_tag(
        session_tag=SESSION_TAG,
        dbt_vars={
            "altimate_query_tag_level": "full",
            "altimate_query_tag_exclude": ["raw_code_hash", "node_meta"],
        },
    )
    assert "raw_code_hash" not in tag and "node_meta" not in tag


def test_unknown_level_warns_and_falls_back_to_lean():
    tag, logs, _ = set_query_tag(
        session_tag=SESSION_TAG, dbt_vars={"altimate_query_tag_level": "FULL_SEND"}
    )
    assert "node_id" not in tag
    assert any("is not recognised" in message for message in logs)


def test_missing_or_invalid_session_tag_is_tolerated():
    for session_tag in (None, "not json at all"):
        tag, _, _ = set_query_tag(session_tag=session_tag, dbt_vars=FULL)
        assert tag["node_id"] == "model.jaffle.my_model"


def test_non_model_nodes():
    for resource_type in ("seed", "test", "snapshot"):
        tag, _, _ = set_query_tag(
            session_tag=SESSION_TAG, dbt_vars=FULL, resource_type=resource_type
        )
        assert "is_incremental" not in tag
        assert tag["node_resource_type"] == resource_type


def test_seeds_omit_node_refs():
    tag, _, _ = set_query_tag(session_tag=SESSION_TAG, dbt_vars=FULL, resource_type="seed")
    assert "node_refs" not in tag


def test_single_quotes_are_escaped_in_the_alter_session_statement():
    tag, _, statement = set_query_tag(
        session_tag=SESSION_TAG, model_config={"query_tag": {"note": "O'Brien"}}
    )
    assert "O''Brien" in statement
    assert tag["note"] == "O'Brien"


def test_model_without_refs():
    tag, _, _ = set_query_tag(session_tag=SESSION_TAG, dbt_vars=FULL, refs=[])
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
