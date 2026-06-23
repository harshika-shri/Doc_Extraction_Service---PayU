INVOICE_LINE_ITEM_PROMPT = """Read the invoice image.

Extract all invoice line items.

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
  "line_items": [
    {
      "line_number": {},
      "item_code": {},
      "item_description": {},
      "uom": {},
      "quantity_billed": {},
      "unit_price": {},
      "discount_amount": {},
      "hsn_sac_code": {},
      "tax_details": {},
      "line_total": {}
    }
  ]
}"""
