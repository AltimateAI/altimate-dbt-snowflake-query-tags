{% macro get_query_comment(node, extra = {}) %}
    {#
        Comprehensive metadata appended to every SQL statement. Query comments
        have no character limit, so the full metadata set is always emitted.
    #}
    {%- set comment_dict = altimate_snowflake_query_tags.altimate_build_metadata(node, extra) -%}

    {# Sanitize: */ breaks SQL block comments, null bytes cause driver errors #}
    {{ return(tojson(comment_dict) | replace("*/", "* /") | replace("\x00", "")) }}
{% endmacro %}
