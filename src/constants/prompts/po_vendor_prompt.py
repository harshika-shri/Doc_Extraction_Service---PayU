PO_VENDOR_PROMPT = """Extract vendor (supplier / seller) details from the purchase order.

Source locations ONLY:
- Top header, logo, and letterhead block
- Supplier company block above the PO title

Do NOT use Bill To, Ship To, or buyer sections for any vendor_* field.

For each field, return {"value": <extracted>, "confidence": <0-100>} if present, or null if absent.
Confidence: 100=clear, lower only when text is blurry/ambiguous/partial. Missing fields are NOT low-confidence.

Return JSON only:
{"vendor_code": {}, "vendor_name": {}, "vendor_gstin": {}, "pan_number": {}, "vendor_email": {}, "vendor_phone": {}, "address_line_1": {}, "address_line_2": {}, "city": {}, "state": {}, "bank_name": {}, "bank_account_number": {}, "ifsc_code": {}, "account_holder_name": {}}"""
