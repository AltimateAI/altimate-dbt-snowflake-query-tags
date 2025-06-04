# Altimate dbt Query Tags

This guide will help you set up query tags to identify your dbt workloads in both **dbt Core** and **dbt Cloud** environments.

---

## 🔧 Step 1: Initial Setup

### Create dbt Integration and Environment

1. Navigate to **Settings** → **Integrations** in the UI
2. Click **"Create New Integration"** and select **dbt Integration**
3. Create a new **dbt Environment** for your project

---

## 🧩 dbt Core Setup

Follow these steps to configure query tags in your dbt Core project:

### 1. Add Query Tag to `profiles.yml`

Add the query tag configuration to your `profiles.yml` file (typically located in `~/.dbt/profiles.yml`). Replace the values with your actual integration ID and environment name:

```yaml
# Example profiles.yml configuration
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
# ... other connection parameters
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

Your `dbt_project.yml` should reference this profile:

```yaml
name: 'my_project'
version: '1.0.0'
profile: 'my_profile'  # This should match the profile name in profiles.yml

models:
  my_project:
    # Your model configurations here
```

> ⚠️ Important: Make sure the query_tag which is set in the project is in valid JSON format.

### 2. Update `packages.yml`

Create or update your `packages.yml` file to include the Altimate query tags package:

```yaml
packages:
  - git: "https://github.com/AltimateAI/altimate-dbt-query-tags.git"

  # Your other packages
  - package: dbt-labs/dbt_utils
    version: 1.1.1
```

### 3. Configure Dispatch in `dbt_project.yml`

Add the dispatch configuration to ensure the query tag macros are properly loaded:

```yaml
dispatch:
  - macro_namespace: dbt
    search_order:
      - YOUR_PROJECT_NAME  # Replace with your actual project name
      - altimate_snowflake_query_tags
      - dbt
```

> 📝 Note: Replace YOUR_PROJECT_NAME with the actual name of your dbt project (the name field in your dbt_project.yml).

## ☁️ dbt Cloud Setup

For dbt Cloud users, follow these steps:

### 1. Configure Cloud Profile

1. Navigate to your **dbt Cloud Project Settings**
2. Go to **Connection** → **Extended Attributes**

### 2. Update `packages.yml`

Add the query tags package to your dbt Cloud project:

```yaml
packages:
  - git: "https://github.com/AltimateAI/altimate-dbt-query-tags.git"
```

### 3. Configure `dbt_project.yml`

Update your dispatch configuration:

```yaml
dispatch:
  - macro_namespace: dbt
    search_order:
      - YOUR_PROJECT_NAME  # Your dbt Cloud project name
      - altimate_snowflake_query_tags
      - dbt
```
