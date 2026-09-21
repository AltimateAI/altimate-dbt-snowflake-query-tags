# Tests

Renders the package macros with a stubbed dbt context so the tag-building logic
can be tested without a Snowflake account. The `alter session set query_tag`
statement is captured and asserted on rather than executed.

```bash
pip install jinja2 pytest
pytest tests/          # or: python tests/test_query_tags.py
```

Not covered: that Snowflake accepts the emitted statement, and dbt Cloud
behaviour. Both need a live run.
