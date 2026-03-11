# Altimate dbt Query Tags

This package enriches your Snowflake dbt workloads with comprehensive metadata using **two complementary mechanisms**:

- **Query Comments**: Rich metadata appended to every SQL statement (no character limit)
- **Query Tags**: Lean session-level tags for quick identification (respects Snowflake's 2000-character limit)

This dual approach solves the common problem of query tags exceeding Snowflake's 2000-character limit while preserving all metadata in query comments.

---

## Step 1: Initial Setup

### Create dbt Integration and Environment

1. Navigate to **Settings** > **Integrations** in the UI
2. Click **"Create New Integration"** and select **dbt Integration**
3. Create a new **dbt Environment** for your project

---

## dbt Core Setup

### 1. Add Query Tag to `profiles.yml`

Add the query tag configuration to your `profiles.yml` file (typically located in `~/.dbt/profiles.yml`). Replace the values with your actual integration ID and environment name from the SaaS UI under Settings -> Integrations:

```yaml
my_profile:
  outputs:
    prod:
      query_tag: '{"dbt_integration_id": 1, "dbt_integration_environment": "PROD"}'
      type: snowflake
      account: your_account
      database: your_database
      warehouse: your_warehouse
      schema: your_schema
      user: your_username
      password: your_password
    dev:
      query_tag: '{"dbt_integration_id": 1, "dbt_integration_environment": "DEV"}'
      type: snowflake
      account: your_account
      database: your_database
      warehouse: your_warehouse
      schema: your_dev_schema
      user: your_username
      password: your_password
  target: prod
```

> **Important:** The `query_tag` must be valid JSON.

### 2. Update `packages.yml`

Create or update your `packages.yml` file to include the Altimate query tags package:

```yaml
packages:
  - git: "https://github.com/AltimateAI/altimate-dbt-snowflake-query-tags.git"
    revision: main

  # Your other packages
  - package: dbt-labs/dbt_utils
    version: 1.1.1
```

### 3. Configure `dbt_project.yml`

Add the dispatch and query-comment configurations:

```yaml
# Enable query comments — comprehensive metadata appended to every SQL statement
query-comment:
  comment: '{{ altimate_snowflake_query_tags.get_query_comment(node) }}'
  append: true

# Enable query tags — lean session-level tags via dispatch
dispatch:
  - macro_namespace: dbt
    search_order:
      - YOUR_PROJECT_NAME  # Replace with your actual project name
      - altimate_snowflake_query_tags
      - dbt
```

> **Note:** `append: true` is required because Snowflake strips leading SQL comments. Appending ensures the comment is preserved.

### 4. Run `dbt deps`

Install the package:

```bash
dbt deps
```

---

## dbt Cloud Setup

### 1. Configure Cloud Profile

1. Navigate to your **dbt Cloud Project Settings**
2. Go to **Connection** > **Extended Attributes**
3. Add the `query_tag` JSON with your integration ID and environment

### 2. Update `packages.yml`

```yaml
packages:
  - git: "https://github.com/AltimateAI/altimate-dbt-snowflake-query-tags.git"
    revision: main
```

### 3. Configure `dbt_project.yml`

```yaml
query-comment:
  comment: '{{ altimate_snowflake_query_tags.get_query_comment(node) }}'
  append: true

dispatch:
  - macro_namespace: dbt
    search_order:
      - YOUR_PROJECT_NAME
      - altimate_snowflake_query_tags
      - dbt
```

---

## What Gets Captured

### Query Comment (appended to SQL)

The query comment contains comprehensive metadata with no character limit:

| Field | Description |
|---|---|
| `app` | Always `"dbt"` |
| `dbt_snowflake_query_tags_version` | Package version |
| `dbt_version` | dbt version |
| `project_name` | dbt project name |
| `target_name` | Target environment name |
| `target_database` | Target database |
| `target_schema` | Target schema |
| `invocation_id` | Unique run identifier |
| `run_started_at` | Run start timestamp (UTC ISO format) |
| `full_refresh` | Whether this is a full refresh run |
| `node_name` | Model/test/seed name |
| `node_alias` | Node alias |
| `node_package_name` | Package the node belongs to |
| `node_original_file_path` | Source file path |
| `node_database` | Node's target database |
| `node_schema` | Node's target schema |
| `node_id` | Unique node identifier |
| `node_resource_type` | Type (model, test, seed, etc.) |
| `node_meta` | Custom metadata from schema.yml |
| `node_tags` | Tags assigned to the node |
| `node_refs` | Referenced models |
| `materialized` | Materialization strategy (models only) |
| `raw_code_hash` | MD5 hash of model code |
| `dbt_cloud_*` | dbt Cloud metadata (when available) |

### Query Tag (session-level)

The query tag is kept lean to stay within Snowflake's 2000-character limit:

| Field | Description |
|---|---|
| `dbt_integration_id` | Altimate integration identifier (from `profiles.yml`) |
| `dbt_integration_environment` | Environment (PROD, DEV, etc.) (from `profiles.yml`) |
| `is_incremental` | Whether running incrementally (models only) |

The query tag preserves all session-level keys set in `profiles.yml` and adds only `is_incremental` — which is only available at execution time and cannot be captured in query comments.

---

## Customization

### Add Custom Fields to Query Comments

```yaml
# dbt_project.yml
query-comment:
  comment: >
    {{ altimate_snowflake_query_tags.get_query_comment(
      node,
      extra={'team': 'data-platform', 'slack_channel': '#data-alerts'}
    ) }}
  append: true
```

---

## Upgrading from v1.x

Version 2.0 introduces query comments as the primary metadata carrier. Breaking changes:

1. **Add `query-comment` to your `dbt_project.yml`** (new requirement — this is where all metadata now lives)
2. **Query tags are now lean** — only session-level keys (`dbt_integration_id`, `dbt_integration_environment`) plus `is_incremental` remain in the query tag. All other metadata moved to query comments.
3. **`unset_query_tag` macro added** — properly restores session state after model execution
4. **`extra` parameter removed from `set_query_tag`** — if you were passing custom fields via `set_query_tag(extra={...})`, move them to `get_query_comment(node, extra={...})` in your `query-comment` config instead.
5. **`env_vars_to_query_tag_list` variable removed** — environment variables are no longer added to query tags. They can be added to query comments via the `extra` parameter.
6. **`thread_id` removed from query tags** — thread information is no longer included. If needed, add it via `extra` in `get_query_comment`.

The `dbt_integration_id` and `dbt_integration_environment` fields remain in the query tag for backward compatibility with Altimate extractors.

> **Note on query comment size:** While query comments have no enforced character limit, Snowflake's `QUERY_TEXT` column has a 100KB limit. Keep `node_meta` and `node_tags` reasonable to avoid truncation in query history.

---

## Verifying in Snowflake

After running `dbt run`, verify both mechanisms:

```sql
-- Check via query tag
SELECT
    query_id,
    query_text,
    query_tag
FROM snowflake.account_usage.query_history
WHERE query_tag LIKE '%dbt_integration_id%'
ORDER BY start_time DESC
LIMIT 10;

-- Check via query comment content
SELECT
    query_id,
    query_text,
    query_tag
FROM snowflake.account_usage.query_history
WHERE query_text LIKE '%dbt_snowflake_query_tags_version%'
ORDER BY start_time DESC
LIMIT 10;
```

The query comment appears appended to the SQL statement. The query tag appears in the `QUERY_TAG` column.
