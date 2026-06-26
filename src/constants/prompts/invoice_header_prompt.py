INVOICE_HEADER_PROMPT = """Extract invoice header fields from the image. Vendor is the issuer; buyer is under Bill To.

For each field, return {"value": <extracted>, "confidence": <0-100>} if present, or null if absent.
Confidence: 100=clear, lower only when text is blurry/ambiguous/partial. Missing fields are NOT low-confidence.

Return JSON only:
{"invoice_number": {}, "invoice_date": {}, "po_number": {}, "subtotal_amount": {}, "tax_amount": {}, "total_amount": {}}"""
