PARTY_ASSIGNMENT_RULES = """
CRITICAL — vendor vs buyer (never swap these roles):

VENDOR / SUPPLIER / SELLER (maps to vendor_* fields):
- The company that issued the document, sells the goods/services, and receives payment.
- Extract ONLY from: top header/logo/letterhead, company block above the title, signature line
  ("For ___" / "Authorized Signatory for ___"), and bank beneficiary / account holder name.
- Examples: Camlin Kokuyo Products Ltd., Reynolds Pens India Pvt. Ltd.

BUYER / CUSTOMER / BILL TO (maps to buyer_company_* / company_* fields):
- The company being billed or placing the purchase order.
- Extract ONLY from the boxed "Bill To" and/or "Ship To" sections.
- Example: PayU Payments Pvt Ltd.

NEVER put Bill To / Ship To details into vendor_* fields.
NEVER put header/letterhead/logo company into buyer_company_* fields.
If PayU appears in Bill To, PayU belongs in buyer fields only — not vendor.
""".strip()
