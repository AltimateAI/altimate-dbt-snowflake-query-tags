{% macro altimate_fit_query_tag(query_tag, protected_keys = []) %}
    {#
        Snowflake rejects a QUERY_TAG longer than 2000 characters, which fails
        the model. Shrink the tag to fit by dropping the least useful fields
        first, rather than discarding the metadata wholesale.

        Returns the dict to set, or none when it still does not fit (the caller
        then restores the original session tag).

        Never dropped: the keys that identify the run (node_id, node_name,
        node_alias, project_name, invocation_id, target_database,
        target_schema, dbt_integration_*) and `protected_keys`, which the
        caller populates with every user-supplied key.
    #}
    {%- set snowflake_limit = 2000 -%}
    {%- set configured = var('altimate_query_tag_max_length', snowflake_limit) -%}

    {# The var can only lower Snowflake's ceiling; coerce so a quoted YAML value
       ("2000") does not fail the comparison below. #}
    {%- set requested = configured | int(0) -%}
    {%- if requested <= 0 or requested > snowflake_limit -%}
        {%- do log("altimate-query-tag-warning: altimate_query_tag_max_length '{}' is not a positive integer of at most {}, which is Snowflake's hard limit. Using {}.".format(configured, snowflake_limit, snowflake_limit), True) -%}
        {%- set max_length = snowflake_limit -%}
    {%- else -%}
        {%- set max_length = requested -%}
    {%- endif -%}

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
        {# A user value that happens to share a generated key's name is theirs, not ours #}
        {%- if tojson(query_tag) | length > max_length and key in query_tag and key not in protected_keys -%}
            {%- do query_tag.pop(key) -%}
            {%- do dropped.append(key) -%}
        {%- endif -%}
    {%- endfor -%}

    {%- if tojson(query_tag) | length <= max_length -%}
        {%- do log("altimate-query-tag: query tag exceeded {} characters, dropped {} to fit.".format(max_length, dropped | join(', '))) -%}
        {{ return(query_tag) }}
    {%- endif -%}

    {%- do log("altimate-query-tag-warning: query tag is {} characters and cannot be reduced below {}. The original session query tag will be preserved instead. Consider shortening user-supplied query tag values.".format(tojson(query_tag) | length, max_length), True) -%}
    {{ return(none) }}
{% endmacro %}
