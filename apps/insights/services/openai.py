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
#   1. Build the prompt by importing from apps/insights/prompts/table_insights.py.
#      Do NOT write the prompt string inline here — prompts live in the prompts/ directory.
#      Import: from apps.insights.prompts.table_insights import build_table_description_prompt
#      Then call: prompt = build_table_description_prompt(table)
#      That function receives the Table object and returns the formatted prompt string.
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
