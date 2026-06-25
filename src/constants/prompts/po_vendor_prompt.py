PO_VENDOR_PROMPT = """Read the purchase order image.

Vendor company is the supplier or seller on the purchase order.

Bank details belong to the vendor.

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
  "vendor_code": {},
  "vendor_name": {},
  "vendor_gstin": {},
  "pan_number": {},
  "vendor_email": {},
  "vendor_phone": {},
  "address_line_1": {},
  "address_line_2": {},
  "city": {},
  "state": {},
  "bank_name": {},
  "bank_account_number": {},
  "ifsc_code": {},
  "account_holder_name": {}
}"""
