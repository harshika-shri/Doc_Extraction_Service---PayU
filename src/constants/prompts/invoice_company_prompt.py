INVOICE_COMPANY_PROMPT = """Read the invoice image.

Buyer company is under Bill To.

For every extracted field return:

{
  "value": extracted_value,
  "confidence": confidence_score
}

IMPORTANT:

If a field is not present in the document:

Return:

null

DO NOT assign confidence.

Missing fields are not low-confidence fields.

Confidence should only be assigned when a value is actually extracted.

Use low confidence only when text is blurry, partially visible, occluded, distorted, ambiguous, or difficult to read.

Return JSON only.

{
  "buyer_company_name": {},
  "buyer_company_gstin": {},
  "buyer_company_address": {}
}"""
