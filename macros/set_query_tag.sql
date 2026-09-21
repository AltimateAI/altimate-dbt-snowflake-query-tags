{% macro default__set_query_tag(extra = {}) -%}
    {#
        Sets Snowflake's native QUERY_TAG session parameter before each
        materialization. dbt-snowflake calls this with no arguments, so `extra`
        is only populated by custom materializations that pass it.

        Controlled by the `altimate_query_tag_fields` var:
          all (default) - everything the query comment carries, trimmed to fit
                          Snowflake's 2000-character limit. Downstream consumers
                          that read QUERY_TAG rather than parsing query comments
                          need this.
          session       - only the keys set in profiles.yml, plus user-supplied
                          tags, thread_id and is_incremental. Keeps the tag
                          small; all other metadata is still in the query
                          comment.
    #}
    {% set original_query_tag = get_current_query_tag() %}
    {% set original_query_tag_parsed = {} %}
    {% if original_query_tag %}
        {% if fromjson(original_query_tag) is mapping %}
            {% set original_query_tag_parsed = fromjson(original_query_tag) %}
        {% endif %}
    {% endif %}

    {% set query_tag = {} %}

    {% set tag_fields = var('altimate_query_tag_fields', 'all') | string | trim | lower %}
    {% if tag_fields not in ['session', 'all'] %}
        {% do log("altimate-query-tag-warning: altimate_query_tag_fields '{}' is not recognised, falling back to 'all'. Valid values are 'session' and 'all'.".format(tag_fields), True) %}
        {% set tag_fields = 'all' %}
    {% endif %}

    {# With 'all', the query tag carries the same metadata as the query comment #}
    {% if tag_fields == 'all' %}
        {% set node = model if model is defined else none %}
        {% do query_tag.update(altimate_snowflake_query_tags.altimate_build_metadata(node)) %}
    {% endif %}

    {# Session-level keys set in profiles.yml (dbt_integration_id, dbt_integration_environment, ...) #}
    {% do query_tag.update(original_query_tag_parsed) %}

    {# Environment variables named in env_vars_to_query_tag_list #}
    {% if var('env_vars_to_query_tag_list', []) %}
        {% for k in var('env_vars_to_query_tag_list') %}
            {% set v = env_var(k, '') %}
            {% do query_tag.update({k.lower(): v}) if v %}
        {% endfor %}
    {% endif %}

    {# Model-level query_tag config, matching dbt's native snowflake__set_query_tag #}
    {% set config_query_tag = config.get('query_tag', default={}) %}
    {# Fusion passes the dict quoted as a string #}
    {% if config_query_tag is string and fromjson(config_query_tag[1:-1]) is mapping %}
        {% set config_query_tag = fromjson(config_query_tag[1:-1]) %}
    {% endif %}
    {% if config_query_tag is mapping %}
        {% do query_tag.update(config_query_tag) %}
    {% elif config_query_tag %}
        {% do log("altimate-query-tag-warning: the query_tag config value of '{}' is not a mapping type, so is being ignored. Use a mapping type instead, or remove it to avoid this message.".format(config_query_tag), True) %}
    {% endif %}

    {% if extra is mapping %}
        {% do query_tag.update(extra) %}
    {% endif %}

    {# Add thread_id for debugging concurrent runs #}
    {% if thread_id is defined and thread_id %}
        {% do query_tag.update(thread_id=thread_id) %}
    {% endif %}

    {# is_incremental is only available at execution time, not in the query comment context #}
    {# Guard with execute and defined checks for seed/run-operation compatibility #}
    {% if execute and model is defined and model is not none and model.resource_type == 'model' %}
        {% do query_tag.update(is_incremental=is_incremental()) %}
    {% endif %}

    {# Shrink to Snowflake's 2000-character limit; none means even the identity keys do not fit #}
    {% set query_tag = altimate_snowflake_query_tags.altimate_fit_query_tag(query_tag) %}

    {% if query_tag is none %}
        {% if original_query_tag %}
            {% set safe_tag = original_query_tag | replace("'", "''") %}
            {% do run_query("alter session set query_tag = '{}'".format(safe_tag)) %}
        {% else %}
            {% do run_query("alter session set query_tag = ''") %}
        {% endif %}
    {% else %}
        {% set safe_tag = tojson(query_tag) | replace("'", "''") %}
        {% do run_query("alter session set query_tag = '{}'".format(safe_tag)) %}
    {% endif %}

    {{ return(original_query_tag) }}
{% endmacro %}
