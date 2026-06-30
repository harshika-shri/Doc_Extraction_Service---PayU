from src.constants.prompts.po_company_prompt import (
    PO_COMPANY_PROMPT,
)
from src.constants.prompts.po_header_prompt import (
    PO_HEADER_PROMPT,
)
from src.constants.prompts.po_line_item_prompt import (
    PO_LINE_ITEM_PROMPT,
)
from src.constants.prompts.po_vendor_prompt import (
    PO_VENDOR_PROMPT,
)

PO_GEMINI_EXTRACTION_PROMPT = f"""
Extract all purchase order data from the attached document in one response.

Apply the same field rules from each section below and return a single JSON object
with every key from all sections at the top level (do not nest sections).

Section 1 — Header:
{PO_HEADER_PROMPT}

Section 2 — Buyer company:
{PO_COMPANY_PROMPT}

Section 3 — Vendor and bank:
{PO_VENDOR_PROMPT}

Section 4 — Line items:
{PO_LINE_ITEM_PROMPT}
""".strip()
