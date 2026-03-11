{% macro default__set_query_tag(extra = {}) -%}
    {# Get session level query tag set via profiles.yml #}
    {% set original_query_tag = get_current_query_tag() %}
    {% set original_query_tag_parsed = {} %}
    {% if original_query_tag %}
        {% if fromjson(original_query_tag) is mapping %}
            {% set original_query_tag_parsed = fromjson(original_query_tag) %}
        {% endif %}
    {% endif %}

    {# Start with session-level query tag (preserves dbt_integration_id, dbt_integration_environment, etc.) #}
    {% set query_tag = original_query_tag_parsed %}

    {# is_incremental is only available at execution time, not in the query comment context #}
    {# Guard with execute to prevent dbt parser from flagging seed hooks as node dependencies #}
    {% if execute and model is not none and model.resource_type == 'model' %}
        {% do query_tag.update(is_incremental=is_incremental()) %}
    {% endif %}

    {% set query_tag_json = tojson(query_tag) %}

    {# Validate against Snowflake's 2000-character query tag limit #}
    {% if query_tag_json and query_tag_json|length > 2000 %}
        {% do log("altimate-query-tag-warning: The constructed query tag is too long ({} characters). Snowflake limits query tags to 2000 characters, so the original query tag will be preserved instead.".format(query_tag_json|length), True) %}
        {% if original_query_tag %}
            {% do run_query("alter session set query_tag = '{}'".format(original_query_tag)) %}
        {% else %}
            {% do run_query("alter session set query_tag = ''") %}
        {% endif %}
    {% else %}
        {% do run_query("alter session set query_tag = '{}'".format(query_tag_json)) %}
    {% endif %}

    {{ return(original_query_tag) }}
{% endmacro %}
