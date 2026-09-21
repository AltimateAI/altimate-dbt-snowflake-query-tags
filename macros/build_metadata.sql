{% macro altimate_build_metadata(node, extra = {}) %}
    {#
        Shared metadata builder for query comments and query tags.

        Returns a dict so callers can serialize, filter, or trim it. Keeping a
        single builder means the query comment and the native QUERY_TAG always
        describe the same run.

        `node` is the query-comment context's node in the comment path and
        `model` in the query-tag path; both expose the same attributes.
    #}
    {%- set metadata = {} -%}
    {%- if extra is mapping -%}
        {%- do metadata.update(extra) -%}
    {%- endif -%}

    {# Standard dbt information #}
    {# run_started_at is already UTC-aware in dbt, no explicit timezone conversion needed #}
    {%- do metadata.update(
        app='dbt',
        dbt_snowflake_query_tags_version=var('dbt_snowflake_query_tags_version', '3.0.0'),
        dbt_version=dbt_version,
        project_name=project_name,
        target_name=target.name,
        target_database=target.database,
        target_schema=target.schema,
        invocation_id=invocation_id,
        run_started_at=run_started_at.isoformat(),
        full_refresh=flags.FULL_REFRESH,
        which=flags.WHICH
    ) -%}

    {%- if flags.INVOCATION_COMMAND is defined and flags.INVOCATION_COMMAND -%}
        {%- do metadata.update(invocation_command=flags.INVOCATION_COMMAND) -%}
    {%- endif -%}

    {# Node-specific information #}
    {%- if node is not none -%}
        {%- do metadata.update(
            node_name=node.name,
            node_alias=node.alias,
            node_package_name=node.package_name,
            node_original_file_path=node.original_file_path,
            node_database=node.database,
            node_schema=node.schema,
            node_id=node.unique_id,
            node_resource_type=node.resource_type,
            node_tags=node.tags
        ) -%}

        {%- if node.config is defined and node.config.meta is defined -%}
            {%- do metadata.update(node_meta=node.config.meta) -%}
        {%- endif -%}

        {%- if node.resource_type == 'model' and node.config is defined -%}
            {%- do metadata.update(materialized=node.config.materialized) -%}
        {%- endif -%}

        {# Add node references — skip for seeds to avoid dbt dependency detection #}
        {%- if node.resource_type != 'seed' and node.refs is defined -%}
            {% set refs = [] %}
            {% for ref in node.refs %}
                {%- if ref.name is defined -%}
                    {%- do refs.append(ref.name) -%}
                {%- elif ref is iterable and ref is not string -%}
                    {# ref[-1] handles two-part refs like ref('package', 'model') #}
                    {%- do refs.append(ref[-1]) -%}
                {%- else -%}
                    {%- do refs.append(ref | string) -%}
                {%- endif -%}
            {% endfor %}
            {%- do metadata.update(node_refs=refs | unique | list) -%}
        {%- endif -%}

        {# Add raw code hash for change detection #}
        {%- if node.raw_code is not none and local_md5 is defined -%}
            {%- do metadata.update(raw_code_hash=local_md5(node.raw_code)) -%}
        {%- endif -%}
    {%- endif -%}

    {# dbt Cloud information #}
    {%- if env_var('DBT_CLOUD_PROJECT_ID', '') -%}
        {%- do metadata.update(dbt_cloud_project_id=env_var('DBT_CLOUD_PROJECT_ID')) -%}
    {%- endif -%}
    {%- if env_var('DBT_CLOUD_JOB_ID', '') -%}
        {%- do metadata.update(dbt_cloud_job_id=env_var('DBT_CLOUD_JOB_ID')) -%}
    {%- endif -%}
    {%- if env_var('DBT_CLOUD_RUN_ID', '') -%}
        {%- do metadata.update(dbt_cloud_run_id=env_var('DBT_CLOUD_RUN_ID')) -%}
    {%- endif -%}
    {%- if env_var('DBT_CLOUD_RUN_REASON_CATEGORY', '') -%}
        {%- do metadata.update(dbt_cloud_run_reason_category=env_var('DBT_CLOUD_RUN_REASON_CATEGORY')) -%}
    {%- endif -%}
    {%- if env_var('DBT_CLOUD_RUN_REASON', '') -%}
        {%- do metadata.update(dbt_cloud_run_reason=env_var('DBT_CLOUD_RUN_REASON')) -%}
    {%- endif -%}

    {{ return(metadata) }}
{% endmacro %}
