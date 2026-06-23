INVOICE_HEADER_PROMPT = """Read the invoice image.

Buyer company is under Bill To.

Vendor company is the invoice issuer.

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
  "invoice_number": {},
  "invoice_date": {},
  "po_number": {},
  "subtotal_amount": {},
  "tax_amount": {},
  "total_amount": {}
}"""
