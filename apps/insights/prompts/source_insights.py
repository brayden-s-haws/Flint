from __future__ import annotations

from apps.sources.models import Source


SOURCE_OVERVIEW_SYSTEM_MESSAGE: str = ("You are an expert in database architecture, SaaS application data, and data warehousing. Your job is to produce clear, concise descriptions of data sources "
                                       "for a technical business audience. Write in clear, direct prose for a technical business audience. Do not reference specific personas or job titles. Use "
                                       "markdown formatting including bold text to make descriptions scannable and useful.")

OPENAI_SOURCE_OVERVIEW_MODEL: str = "gpt-5.4-mini"
ANTHROPIC_SOURCE_OVERVIEW_MODEL: str = "claude-haiku-4-5"
SOURCE_OVERVIEW_MAX_TOKENS: int = 1000

def build_source_overview_prompt(source: Source) -> str:
    source_details = f"""
    Source: {source.name}
    Type: {source.source_type}
    Tables: {', '.join([table.name for schema in source.schema_set.all() for table in schema.table_set.all()])}
    """
    source_details += """
    Based on the above, write a description of this data source using markdown formatting.
    Write 2 short paragraphs.
    First paragraph: describe what this source contains and its role — infer from the source type and table names.
    Second paragraph: describe how this data could be used — for analysis, product features, operational workflows, or business intelligence. Be specific to the tables present.
    Use bold to highlight key table names or concepts where useful.
    Do not include a title or heading. Do not mention specific personas or reference who uses the data.

    Example (proprietary app database):
    Contains the core transactional data for an e-commerce platform, including **orders**, **products**, **customers**, and **inventory**. \
Covers the full purchase lifecycle from cart to fulfillment, along with supporting data for catalog management and customer accounts.

    Supports revenue reporting, customer segmentation, and inventory analysis. \
Can be used to track conversion rates, identify high-value customers, monitor stock levels, and power operational dashboards for fulfillment teams.

    Example (SaaS source):
    Contains customer relationship and marketing data from HubSpot, including **contacts**, **companies**, **deals**, and **engagement activity**. \
Represents the full sales pipeline and marketing touchpoint history for the organization.

    Useful for pipeline reporting, lead conversion analysis, and campaign attribution. \
Can be combined with product or financial data to build a complete view of the customer journey from first touch to closed revenue.
    """
    return source_details