# Luminetiq Potential Features

This document tracks potential future features and capabilities beyond the MVP. Features are organized by category for planning purposes.

---

## Data Quality & Observability

- **Schema change detection alerts** - Notify when table structures change
- **Data freshness monitoring** - Track when tables were last updated
- **Row count anomaly detection** - Alert on unexpected volume changes
- **Null value trend tracking** - Monitor data completeness over time
- **Data profiling reports** - Automated statistical summaries of columns

---

## Governance & Compliance

- **Data classification** - Automatic PII detection and tagging
- **Column sensitivity tagging** - Mark sensitive data types (SSN, email, etc.)
- **Access audit logging** - Track who viewed what metadata
- **Business glossary** - Define standard terms and link to technical assets
- **Data ownership assignment** - Assign stewards to tables/sources

---

## Collaboration

- **Comments on tables/columns** - Team discussion threads
- **@mentions for team members** - Notify specific users
- **Slack/Teams notifications** - Alerts via messaging platforms
- **Shared insight collections** - Curated sets of insights
- **Data documentation wiki** - Rich text documentation for sources

---

## Advanced Intelligence

- **Natural language to SQL** - Generate queries from questions
- **Query explanation** - SQL to English translation
- **Automated data relationship discovery** - Detect foreign keys and joins
- **Cross-account benchmarking** - Compare patterns across organizations
- **Usage recommendation engine** - Suggest relevant tables for use cases

---

## Additional Connectors

### Databases
- SQL Server
- Oracle
- MongoDB
- DynamoDB
- Redshift
- Databricks

### SaaS/APIs
- Salesforce
- Stripe
- Shopify
- Zendesk
- Intercom
- Mixpanel
- Amplitude
- Segment
- Airtable
- Notion databases

### File/Storage
- S3/GCS (CSV, Parquet, JSON files)
- Google Sheets
- Excel files

### ETL/Pipelines
- dbt (model metadata)
- Airflow (DAG metadata)
- Fivetran/Airbyte (sync status)

---

## Integrations

- **dbt model sync** - Import dbt model definitions and docs
- **Airflow DAG metadata** - Track pipeline dependencies
- **Fivetran/Airbyte sync status** - Monitor ETL health
- **BI tool metadata** - Looker, Tableau, Metabase integration
- **GitHub/GitLab** - Version tracking for schema changes

---

## Developer Experience

- **CLI tool** - Local database inspection from terminal
- **VS Code extension** - Schema lookup in editor
- **API webhooks** - Push notifications for events
- **Terraform provider** - Infrastructure-as-code for sources
- **SDK for custom integrations** - Python/JavaScript libraries

---

## Visualization

- **ERD diagram generation** - Mermaid/D3 relationship diagrams
- **Data lineage visualization** - Upstream/downstream dependencies
- **Schema diff viewer** - Compare versions side-by-side
- **Interactive query builder** - Visual SQL construction

---

## Enterprise Features

- **SSO/SAML authentication** - Enterprise identity providers
- **Role-based access control** - Granular permissions
- **Audit logs** - Compliance-ready activity tracking
- **Multi-region deployment** - Data residency options
- **White-labeling** - Custom branding for agencies

---

## Notes

Features should be prioritized based on:
1. User feedback and demand
2. Technical complexity
3. Value delivered vs. effort required
4. Strategic alignment with product vision

This list is not a roadmap - it's a backlog of possibilities to consider as the product evolves.
