{% macro altimate_fit_query_tag(query_tag) %}
    {#
        Snowflake rejects a QUERY_TAG longer than 2000 characters, which fails
        the model. Shrink the tag to fit by dropping the least useful fields
        first, rather than discarding the metadata wholesale.

        Returns the dict to set, or none when it still does not fit (the caller
        then restores the original session tag).

        Never dropped: the keys that identify the run (node_id, node_name,
        node_alias, project_name, invocation_id, target_database,
        target_schema, dbt_integration_*) and user-supplied keys from
        profiles.yml, the `query_tag` model config, and
        `env_vars_to_query_tag_list`. Downstream consumers depend on those.
    #}
    {%- set max_length = var('altimate_query_tag_max_length', 2000) -%}

    {%- for key in var('altimate_query_tag_exclude', []) -%}
        {%- do query_tag.pop(key, none) -%}
    {%- endfor -%}

    {%- if tojson(query_tag) | length <= max_length -%}
        {{ return(query_tag) }}
    {%- endif -%}

    {# Expendable fields, ordered most expendable first #}
    {%- set droppable = [
        'node_meta', 'node_tags', 'node_refs', 'raw_code_hash',
        'node_original_file_path', 'dbt_cloud_run_reason',
        'dbt_cloud_run_reason_category', 'invocation_command', 'which',
        'run_started_at', 'node_package_name', 'materialized',
        'node_database', 'node_schema', 'target_name', 'dbt_version',
        'full_refresh', 'dbt_snowflake_query_tags_version', 'thread_id',
        'dbt_cloud_run_id', 'dbt_cloud_job_id', 'dbt_cloud_project_id'
    ] -%}
    {%- set dropped = [] -%}
    {%- for key in droppable -%}
        {%- if tojson(query_tag) | length > max_length and key in query_tag -%}
            {%- do query_tag.pop(key) -%}
            {%- do dropped.append(key) -%}
        {%- endif -%}
    {%- endfor -%}

    {%- if tojson(query_tag) | length <= max_length -%}
        {%- do log("altimate-query-tag: query tag exceeded {} characters, dropped {} to fit.".format(max_length, dropped | join(', '))) -%}
        {{ return(query_tag) }}
    {%- endif -%}

    {%- do log("altimate-query-tag-warning: query tag is {} characters and cannot be reduced below {}. The original session query tag will be preserved instead. Consider shortening user-supplied query tag values or setting altimate_query_tag_level to 'lean'.".format(tojson(query_tag) | length, max_length), True) -%}
    {{ return(none) }}
{% endmacro %}
