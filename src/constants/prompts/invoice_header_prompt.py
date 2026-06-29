INVOICE_HEADER_PROMPT = """Extract invoice header fields from the image. Vendor is the issuer; buyer is under Bill To.

For each field, return {"value": <extracted>, "confidence": <0-100>} if present, or null if absent.
Confidence: 100=clear, lower only when text is blurry/ambiguous/partial. Missing fields are NOT low-confidence.

For due_date: find the payment due date even when it is not labeled exactly "Due Date". It may appear as:
- "Payment due by", "Pay by", "Due on", "Net 30", "Terms: 30 days"
- A bullet point or sentence such as "Please pay within 15 days of invoice date"
- A standalone date near payment terms or bank details
Return the resolved calendar date in YYYY-MM-DD. If only relative terms are given (e.g. Net 30) and invoice_date is known, compute the due date from invoice_date. If it cannot be determined, return null.

Return JSON only:
{"invoice_number": {}, "invoice_date": {}, "due_date": {}, "po_number": {}, "subtotal_amount": {}, "tax_amount": {}, "total_amount": {}}"""
