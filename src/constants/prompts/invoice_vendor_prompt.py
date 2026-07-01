INVOICE_VENDOR_PROMPT = """Extract vendor (invoice issuer / seller / supplier) and bank details.

Source locations ONLY:
- Top header, logo, and letterhead block
- Signature area ("For ___", "Authorized Signatory for ___")
- Bank details beneficiary / account holder name

Do NOT use Bill To, Ship To, or buyer sections for any vendor_* field.

For each field, return {"value": <extracted>, "confidence": <0-100>} if present, or null if absent.
Confidence: 100=clear, lower only when text is blurry/ambiguous/partial. Missing fields are NOT low-confidence.

Return JSON only:
{"vendor_name": {}, "vendor_gstin": {}, "vendor_address": {}, "vendor_email": {}, "vendor_phone": {}, "bank_account_number": {}, "bank_name": {}, "ifsc_code": {}, "account_holder_name": {}}"""
