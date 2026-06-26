INVOICE_LINE_ITEM_PROMPT = """Extract all line items from the invoice image.

For each field, return {"value": <extracted>, "confidence": <0-100>} if present, or null if absent.
Confidence: 100=clear, lower only when text is blurry/ambiguous/partial. Missing fields are NOT low-confidence.

Return JSON only:
{"line_items": [{"line_number": {}, "item_code": {}, "item_description": {}, "uom": {}, "quantity_billed": {}, "unit_price": {}, "discount_amount": {}, "hsn_sac_code": {}, "tax_details": {}, "line_total": {}}]}"""
