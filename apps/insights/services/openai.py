from __future__ import annotations

# TODO(stub): Import the openai package — install it first if not already in requirements:
#   pip install openai
#   then: from openai import OpenAI
# TODO(stub): Import Table from apps.catalog.models
# TODO(stub): Import BaseService from .base


# TODO(stub): Define OpenAIService(BaseService)
# - Call super().__init__(api_key) in __init__ to store the key
# - Instantiate the OpenAI client using the api_key:
#     self.client = OpenAI(api_key=self.api_key)
#   Do this in __init__ so the client is created once per service instance, not per call.
#
# - Implement generate_table_description(self, table: Table) -> str:
#   This method should:
#   1. Build a prompt string describing the table. Include:
#      - table.name
#      - table.schema.name and table.schema.source.name (use select_related in the view when
#        fetching the table, or access via the FK traversal here — it will query lazily)
#      - A list of columns: iterate table.column_set.all() and include each column's
#        name, data_type, nullable, and primary_key fields
#      Keep the prompt focused: "Describe what this database table likely contains and
#      how it might be used, based on its name and columns."
#
#   2. Call the OpenAI chat completions API:
#      response = self.client.chat.completions.create(
#          model=...,      # use "gpt-5.4-mini " for MVP (cheap, fast, capable)
#          messages=[...], # list of dicts with "role" and "content" keys
#          max_tokens=..., # 300-500 is plenty for a table description
#      )
#      The messages list should have at least:
#        - {"role": "system", "content": "You are a data analyst..."}
#        - {"role": "user", "content": <your prompt>}
#
#   3. Extract and return the text:
#      The response content is at: response.choices[0].message.content
#      Strip whitespace before returning.
#
#   Type hint: def generate_table_description(self, table: Table) -> str
class OpenAIService:
    pass
