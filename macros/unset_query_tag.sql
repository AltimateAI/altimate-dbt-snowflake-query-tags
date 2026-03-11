{% macro default__unset_query_tag(original_query_tag) -%}
    {% if original_query_tag %}
        {% set safe_tag = original_query_tag | replace("'", "''") %}
        {% do run_query("alter session set query_tag = '{}'".format(safe_tag)) %}
    {% else %}
        {% do run_query("alter session unset query_tag") %}
    {% endif %}
{% endmacro %}
