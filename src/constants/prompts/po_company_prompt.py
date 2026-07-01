PO_COMPANY_PROMPT = """Extract buyer (customer / Bill To) company details from the purchase order.

Source locations ONLY:
- The "Bill To" boxed section
- The "Ship To" section when Bill To is absent

The buyer is the company placing the order (e.g. PayU Payments Pvt Ltd in Bill To).
Do NOT use the top header, logo, or letterhead for buyer fields — that is the supplier.

For each field, return {"value": <extracted>, "confidence": <0-100>} if present, or null if absent.
Confidence: 100=clear, lower only when text is blurry/ambiguous/partial. Missing fields are NOT low-confidence.

Return JSON only:
{"buyer_company_name": {}, "buyer_company_gstin": {}, "buyer_company_address": {}}"""
