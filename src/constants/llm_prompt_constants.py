CLASSIFICATION_PROMPT = """
Classify the document using the raw extraction JSON provided below.
Return JSON with this shape:
{
  "document_type": "invoice" | "purchase_order" | "other",
  "confidence": 0.0,
  "reason": "short explanation"
}

Use "invoice" for tax invoices, bills, or payment requests.
Use "purchase_order" for PO documents or purchase orders.
Use "other" for anything else such as receipts, contracts,
delivery notes, images without business documents, or spam.

Raw extraction JSON:
""".strip()

INVOICE_PARSE_PROMPT = """
You are parsing invoice data for database insertion.
Use the raw document extraction JSON below and map it into the exact target schema.
Use null for missing values.
Return JSON only.

Target schema:
{
  "invoice_number": string | null,
  "invoice_date": "YYYY-MM-DD" | null,
  "po_numbers_extracted": [string] | null,
  "due_date": "YYYY-MM-DD" | null,
  "currency": string | null,
  "payment_terms": string | null,
  "subtotal_amount": number | null,
  "discount_amount": number | null,
  "tax_amount": number | null,
  "total_amount": number | null,
  "notes": string | null,
  "company_name": string | null,
  "company_gstin": string | null,
  "company_address": string | null,
  "vendor": {
    "vendor_name": string | null,
    "vendor_gstin": string | null,
    "vendor_address": string | null,
    "vendor_email": string | null,
    "vendor_phone": string | null,
    "bank_account_number": string | null,
    "bank_name": string | null,
    "ifsc_code": string | null,
    "account_holder_name": string | null
  },
  "line_items": [
    {
      "line_number": integer | null,
      "item_code": string | null,
      "item_description": string | null,
      "uom": string | null,
      "quantity_billed": number | null,
      "unit_price": number | null,
      "discount_amount": number | null,
      "tax_details": object | null,
      "hsn_sac_code": string | null,
      "line_total": number | null
    }
  ]
}

Database mapping notes:
- company_* fields are the buyer/customer on the invoice
- vendor_* fields are the supplier/seller
- quantity_billed is the billed quantity per line item
- po_numbers_extracted should be a list of PO numbers if present

Raw extraction JSON:
""".strip()

PO_PARSE_PROMPT = """
You are parsing purchase order data for database insertion.
Use the LlamaExtract JSON below and map it into the exact target schema.
Use null for missing values.
Return JSON only.

Target schema:
{
  "po_number": string | null,
  "company_name": string | null,
  "company_gstin": string | null,
  "vendor_name": string | null,
  "vendor_gstin": string | null,
  "delivery_address": string | null,
  "currency": string | null,
  "payment_terms": string | null,
  "po_date": "YYYY-MM-DD" | null,
  "valid_until": "YYYY-MM-DD" | null,
  "subtotal_amount": number | null,
  "discount_amount": number | null,
  "tax_amount": number | null,
  "total_amount": number | null,
  "line_items": [
    {
      "line_number": integer | null,
      "item_code": string | null,
      "item_description": string | null,
      "uom": string | null,
      "quantity_ordered": number | null,
      "unit_price": number | null,
      "discount_amount": number | null,
      "tax_details": object | null,
      "line_total": number | null
    }
  ]
}

Database mapping notes:
- company_* fields refer to the buyer
- vendor_* fields refer to the supplier
- quantity_ordered is the ordered quantity per line item

Raw extraction JSON:
""".strip()
