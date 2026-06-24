INVOICE_VENDOR_PROMPT = """Read the invoice image.

Vendor company is the invoice issuer.

Bank details belong to vendor.

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
  "vendor_name": {},
  "vendor_gstin": {},
  "vendor_address": {},
  "vendor_email": {},
  "vendor_phone": {},
  "bank_account_number": {},
  "bank_name": {},
  "ifsc_code": {},
  "account_holder_name": {}
}"""
