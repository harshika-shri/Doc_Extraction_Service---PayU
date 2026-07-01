INVOICE_COMPANY_PROMPT = """Extract buyer (customer / Bill To) company details.

Source locations ONLY:
- The "Bill To" boxed section
- The "Ship To" section when Bill To is absent

Do NOT use the top header, logo, letterhead, signature block, or bank details for buyer fields.

For each field, return {"value": <extracted>, "confidence": <0-100>} if present, or null if absent.
Confidence: 100=clear, lower only when text is blurry/ambiguous/partial. Missing fields are NOT low-confidence.

Return JSON only:
{"buyer_company_name": {}, "buyer_company_gstin": {}, "buyer_company_address": {}}"""
