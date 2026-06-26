INVOICE_COMPANY_PROMPT = """Extract buyer company details from the invoice image. Buyer is under Bill To.

For each field, return {"value": <extracted>, "confidence": <0-100>} if present, or null if absent.
Confidence: 100=clear, lower only when text is blurry/ambiguous/partial. Missing fields are NOT low-confidence.

Return JSON only:
{"buyer_company_name": {}, "buyer_company_gstin": {}, "buyer_company_address": {}}"""
