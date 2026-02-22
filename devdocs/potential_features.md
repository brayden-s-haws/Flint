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

- **Natural language to SQL** - Generate queries from questions using LLMs with schema context injection; built natively (no third-party dependency); see `devdocs/appdocs/post_mvp.md` for the detailed approach
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
- **Amundsen integration** - Open source data catalog (Linux Foundation) used by many data teams. Luminetiq can use the `amundsen-databuilder` Python library to supplement its own connector extraction, and optionally push LLM-generated descriptions back to Amundsen deployments via REST API. Positions Luminetiq as the AI intelligence layer on top of an existing catalog. See `devdocs/appdocs/post_mvp.md` for the detailed approach.

---

## Business Ontology Layer

A semantic mapping layer that sits between raw database schema and business users/AI agents. Maps physical tables and columns to named business entities (e.g., `tbl_cust_master` → **Customer**, `contact_email_addr` → **Email Address**) and defines typed relationships between them (Customer *has many* Orders). LLMs can suggest object type names, property labels, and relationships from catalog metadata; humans review and accept. See `devdocs/appdocs/post_mvp.md` for the detailed approach.

---

## Feature Management

- **Bitmath feature flags** - Use bitwise operations to control feature toggles. Store a single integer per account/user where each bit position represents a feature (e.g., bit 0 = dark mode, bit 1 = beta insights, bit 2 = advanced connectors). Check flags with bitwise AND (`flags & FEATURE_BIT`), enable with OR (`flags | FEATURE_BIT`), disable with AND + NOT (`flags & ~FEATURE_BIT`). Keeps the database lean (one integer column vs. a join table), is extremely fast to evaluate, and doubles as a learning exercise in bit manipulation. Consider a `FeatureFlag` enum or constants file mapping bit positions to human-readable names.

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

## Shared / Default Metadata

- **Standard metadata templates** - Pre-built descriptions for common SaaS sources (e.g., HubSpot Contacts, Stripe Charges). Provide default table/column descriptions that work out of the box without LLM generation, saving cost and setup time.
- **Tenant-overridable defaults** - Tenants inherit shared descriptions by default but can customize them. Custom descriptions take priority over shared ones.
- **Standard insight templates** - Pre-generated insights for well-known table structures. If a HubSpot "Contacts" table looks the same across tenants, reuse the insight rather than generating a new one per tenant.
- **Custom-only mode for standalone databases** - Sources like standalone PostgreSQL databases have no shared templates. All metadata and insights are generated per-tenant.
- **Community-contributed templates** (future) - Allow users to contribute and share metadata templates for common tools.

This reduces LLM costs, speeds up onboarding for common sources, and still supports fully custom metadata for unique database schemas.

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
