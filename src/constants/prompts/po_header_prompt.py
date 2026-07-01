PO_HEADER_PROMPT = """Extract purchase order header fields from the image.

For each field, return {"value": <extracted>, "confidence": <0-100>} if present, or null if absent.
Confidence: 100=clear, lower only when text is blurry/ambiguous/partial. Missing fields are NOT low-confidence.

Return JSON only:
{"po_number": {}, "po_date": {}, "subtotal_amount": {}, "tax_amount": {}, "total_amount": {}}"""
