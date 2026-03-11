{% macro get_query_comment(node, extra = {}) %}
    {%- set comment_dict = extra -%}

    {# Add standard dbt information #}
    {%- do comment_dict.update(
        app='dbt',
        dbt_snowflake_query_tags_version='2.0.0',
        dbt_version=dbt_version,
        project_name=project_name,
        target_name=target.name,
        target_database=target.database,
        target_schema=target.schema,
        invocation_id=invocation_id,
        run_started_at=run_started_at.astimezone(modules.pytz.utc).isoformat(),
        full_refresh=flags.FULL_REFRESH
    ) -%}

    {# Add node-specific information if available #}
    {%- if node is not none -%}
        {%- do comment_dict.update(
            node_name=node.name,
            node_alias=node.alias,
            node_package_name=node.package_name,
            node_original_file_path=node.original_file_path,
            node_database=node.database,
            node_schema=node.schema,
            node_id=node.unique_id,
            node_resource_type=node.resource_type,
            node_meta=node.config.meta,
            node_tags=node.tags
        ) -%}

        {%- if node.resource_type == 'model' -%}
            {%- do comment_dict.update(materialized=node.config.materialized) -%}
        {%- endif -%}

        {# Add node references — skip for seeds to avoid dbt dependency detection #}
        {%- if node.resource_type != 'seed' and node.refs is defined -%}
            {% set refs = [] %}
            {% for ref in node.refs %}
                {%- if ref is mapping -%}
                    {%- do refs.append(ref.name) -%}
                {%- elif ref is iterable and ref is not string -%}
                    {%- do refs.append(ref[0]) -%}
                {%- endif -%}
            {% endfor %}
            {%- do comment_dict.update(node_refs=refs | unique | list) -%}
        {%- endif -%}

        {# Add raw code hash for change detection #}
        {%- if node.raw_code is not none and local_md5 -%}
            {%- do comment_dict.update(raw_code_hash=local_md5(node.raw_code)) -%}
        {%- endif -%}
    {%- endif -%}

    {# Add dbt Cloud information if available #}
    {%- if env_var('DBT_CLOUD_PROJECT_ID', False) -%}
        {%- do comment_dict.update(dbt_cloud_project_id=env_var('DBT_CLOUD_PROJECT_ID')) -%}
    {%- endif -%}
    {%- if env_var('DBT_CLOUD_JOB_ID', False) -%}
        {%- do comment_dict.update(dbt_cloud_job_id=env_var('DBT_CLOUD_JOB_ID')) -%}
    {%- endif -%}
    {%- if env_var('DBT_CLOUD_RUN_ID', False) -%}
        {%- do comment_dict.update(dbt_cloud_run_id=env_var('DBT_CLOUD_RUN_ID')) -%}
    {%- endif -%}
    {%- if env_var('DBT_CLOUD_RUN_REASON_CATEGORY', False) -%}
        {%- do comment_dict.update(dbt_cloud_run_reason_category=env_var('DBT_CLOUD_RUN_REASON_CATEGORY')) -%}
    {%- endif -%}
    {%- if env_var('DBT_CLOUD_RUN_REASON', False) -%}
        {%- do comment_dict.update(dbt_cloud_run_reason=env_var('DBT_CLOUD_RUN_REASON')) -%}
    {%- endif -%}

    {{ return(tojson(comment_dict)) }}
{% endmacro %}
