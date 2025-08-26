{% macro default__set_query_tag(extra = {}) -%}
    {# Get session level query tag #}
    {% set original_query_tag = get_current_query_tag() %}
    {% set original_query_tag_parsed = {} %}
    {% if original_query_tag %}
        {% if fromjson(original_query_tag) is mapping %}
            {% set original_query_tag_parsed = fromjson(original_query_tag) %}
        {% endif %}
    {% endif %}
    
    {# The env_vars_to_query_tag_list should contain an environment variables list to construct query tag dict #}
    {% set env_var_query_tags = {} %}
    {% if var('env_vars_to_query_tag_list', '') %} {# Get a list of env vars from env_vars_to_query_tag_list variable to add additional query tags #}
        {% for k in var('env_vars_to_query_tag_list') %}
            {% set v = env_var(k, '') %}
            {% do env_var_query_tags.update({k.lower(): v}) if v %}
        {% endfor %}
    {% endif %}
    
    {# Start with any model-configured dict #}
    {% set query_tag = config.get('query_tag', default={}) %}
    {% if query_tag is not mapping %}
    {% do log("altimate-query-tag-warning: the query_tag config value of '{}' is not a mapping type, so is being ignored. If you'd like to add additional query tag information, use a mapping type instead, or remove it to avoid this message.".format(query_tag), True) %}
    {% set query_tag = {} %} {# If the user has set the query tag config as a non mapping type, start fresh #}
    {% endif %}
    
    {# Define session-level keys that should be preserved from original query tag #}
    {% set session_level_keys = ['dbt_integration_id', 'dbt_integration_environment'] %}
    
    {# Extract only session-level information from original query tag #}
    {% set session_query_tags = {} %}
    {% for key in session_level_keys %}
        {% if key in original_query_tag_parsed %}
            {% do session_query_tags.update({key: original_query_tag_parsed[key]}) %}
        {% endif %}
    {% endfor %}
    
    {# Add session-level tags first #}
    {% do query_tag.update(session_query_tags) %}
    {% do query_tag.update(env_var_query_tags) %}
    
    {# Add node information if available - this will override any node-specific info from session #}
    {% if model %}
        {% do query_tag.update(
            node_name=model.name,
            node_alias=model.alias,
            node_package_name=model.package_name,
            node_database=model.database,
            node_schema=model.schema,
            node_id=model.unique_id,
            node_resource_type=model.resource_type,
            node_meta=model.config.meta,
            node_tags=model.tags
        ) %}
        
        {% if model.resource_type == 'model' %}
            {% do query_tag.update(
                materialized=model.config.materialized
            ) %}
        {% endif %}
            {% endif %}
    
    {# Add extra parameters passed to the macro #}
    {% do query_tag.update(extra) %}
    
    {# Add standard dbt information #}
    {% do query_tag.update(
        app='dbt',
        dbt_snowflake_query_tags_version='1.0.2',
        dbt_version=dbt_version,
        project_name=project_name,
        target_name=target.name,
        target_database=target.database,
        target_schema=target.schema,
        invocation_id=invocation_id,
        run_started_at=run_started_at.astimezone(modules.pytz.utc).isoformat(),
        full_refresh=flags.FULL_REFRESH
    ) %}
    
    {# Add additional Cloud information if available #}
    {% if env_var('DBT_CLOUD_PROJECT_ID', False) %}
        {% do query_tag.update(
            dbt_cloud_project_id=env_var('DBT_CLOUD_PROJECT_ID')
        ) %}
    {% endif %}
    {% if env_var('DBT_CLOUD_JOB_ID', False) %}
        {% do query_tag.update(
            dbt_cloud_job_id=env_var('DBT_CLOUD_JOB_ID')
        ) %}
    {% endif %}
    {% if env_var('DBT_CLOUD_RUN_ID', False) %}
        {% do query_tag.update(
            dbt_cloud_run_id=env_var('DBT_CLOUD_RUN_ID')
        ) %}
    {% endif %}
    
    {% if thread_id %}
        {% do query_tag.update(
            thread_id=thread_id
        ) %}
    {% endif %}
    
    {# We have to bring is_incremental through here because its not available in the comment context #}
    {% if model.resource_type == 'model' %}
        {% do query_tag.update(
            is_incremental=is_incremental()
        ) %}
    {% endif %}
    
    {% set query_tag_json = tojson(query_tag) %}
    {% do run_query("alter session set query_tag = '{}'".format(query_tag_json)) %}
    {{ return(original_query_tag)}}
{% endmacro %}