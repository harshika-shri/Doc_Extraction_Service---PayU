from src.constants.prompts.party_assignment_rules import (
    PARTY_ASSIGNMENT_RULES,
)
from src.constants.prompts.invoice_company_prompt import (
    INVOICE_COMPANY_PROMPT,
)
from src.constants.prompts.invoice_header_prompt import (
    INVOICE_HEADER_PROMPT,
)
from src.constants.prompts.invoice_line_item_prompt import (
    INVOICE_LINE_ITEM_PROMPT,
)
from src.constants.prompts.invoice_vendor_prompt import (
    INVOICE_VENDOR_PROMPT,
)

INVOICE_GEMINI_EXTRACTION_PROMPT = f"""
{PARTY_ASSIGNMENT_RULES}

Extract all invoice data from the attached document in one response.

Apply the same field rules from each section below and return a single JSON object
with every key from all sections at the top level (do not nest sections).

Section 1 — Header:
{INVOICE_HEADER_PROMPT}

Section 2 — Buyer company:
{INVOICE_COMPANY_PROMPT}

Section 3 — Vendor and bank:
{INVOICE_VENDOR_PROMPT}

Section 4 — Line items:
{INVOICE_LINE_ITEM_PROMPT}
""".strip()
