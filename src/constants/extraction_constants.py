PROCESSABLE_ATTACHMENT_EXTENSIONS = {
    ".pdf",
    ".png",
    ".jpg",
    ".jpeg",
    ".tif",
    ".tiff",
    ".doc",
    ".docx",
}

INVOICE_HEADER_FIELDS = (
    "invoice_number",
    "invoice_date",
    "po_numbers_extracted",
    "due_date",
    "currency",
    "payment_terms",
    "subtotal_amount",
    "discount_amount",
    "tax_amount",
    "total_amount",
    "notes",
    "company_name",
    "company_gstin",
    "company_address",
)

INVOICE_VENDOR_FIELDS = (
    "vendor_name",
    "vendor_gstin",
    "vendor_address",
    "vendor_email",
    "vendor_phone",
    "bank_account_number",
    "bank_name",
    "ifsc_code",
    "account_holder_name",
)

INVOICE_LINE_ITEM_FIELDS = (
    "line_number",
    "item_code",
    "item_description",
    "uom",
    "quantity_billed",
    "unit_price",
    "discount_amount",
    "tax_details",
    "hsn_sac_code",
    "line_total",
)

INVOICE_LINE_ITEM_REQUIRED_FIELDS = (
    "quantity_billed",
    "unit_price",
    "line_total",
)
