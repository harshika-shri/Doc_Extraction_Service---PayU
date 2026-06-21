PURCHASE_ORDER_LINE_ITEM_SCHEMA: dict[str, object] = {
    "type": "object",
    "properties": {
        "line_number": {
            "type": "integer",
            "description": (
                "Sequential line number for the purchase order row."
            ),
        },
        "item_code": {
            "type": "string",
            "description": (
                "Product or SKU code for the line item, if shown."
            ),
        },
        "item_description": {
            "type": "string",
            "description": (
                "Description of the ordered item or service."
            ),
        },
        "uom": {
            "type": "string",
            "description": (
                "Unit of measure such as PCS, KG, NOS, BOX, or HRS."
            ),
        },
        "quantity_ordered": {
            "type": "number",
            "description": (
                "Ordered quantity for the line item."
            ),
        },
        "unit_price": {
            "type": "number",
            "description": (
                "Unit price before tax and discounts."
            ),
        },
        "discount_amount": {
            "type": "number",
            "description": (
                "Discount amount applied to the line item."
            ),
        },
        "tax_details": {
            "type": "array",
            "description": (
                "Tax breakdown for the line item such as CGST, SGST, "
                "IGST, or VAT."
            ),
            "items": {
                "type": "object",
                "properties": {
                    "tax_name": {
                        "type": "string",
                        "description": (
                            "Tax label such as CGST, SGST, IGST, or VAT."
                        ),
                    },
                    "tax_value": {
                        "type": "string",
                        "description": (
                            "Tax amount or rate for the line item."
                        ),
                    },
                },
            },
        },
        "line_total": {
            "type": "number",
            "description": (
                "Total amount for the line item after discounts and tax."
            ),
        },
    },
}

PURCHASE_ORDER_EXTRACTION_SCHEMA: dict[str, object] = {
    "type": "object",
    "properties": {
        "po_number": {
            "type": "string",
            "description": (
                "Unique purchase order number. May appear as PO No, "
                "PO Number, Purchase Order #, or Order ID."
            ),
        },
        "company_name": {
            "type": "string",
            "description": (
                "Buyer company name shown on the purchase order."
            ),
        },
        "company_gstin": {
            "type": "string",
            "description": (
                "Buyer GSTIN or tax identification number."
            ),
        },
        "vendor_name": {
            "type": "string",
            "description": (
                "Supplier or vendor name issuing or receiving the PO."
            ),
        },
        "vendor_gstin": {
            "type": "string",
            "description": (
                "Supplier GSTIN or tax identification number."
            ),
        },
        "delivery_address": {
            "type": "string",
            "description": (
                "Ship-to or delivery address for the purchase order."
            ),
        },
        "currency": {
            "type": "string",
            "description": (
                "Currency code such as INR, USD, or EUR."
            ),
        },
        "payment_terms": {
            "type": "string",
            "description": (
                "Payment terms such as Net 30, Due on Receipt, "
                "or Advance Payment."
            ),
        },
        "po_date": {
            "type": "string",
            "description": (
                "Purchase order date in YYYY-MM-DD when possible."
            ),
        },
        "valid_until": {
            "type": "string",
            "description": (
                "PO validity or expiry date in YYYY-MM-DD when possible."
            ),
        },
        "subtotal_amount": {
            "type": "number",
            "description": (
                "Subtotal before tax and after line discounts."
            ),
        },
        "discount_amount": {
            "type": "number",
            "description": (
                "Overall discount amount applied to the purchase order."
            ),
        },
        "tax_amount": {
            "type": "number",
            "description": (
                "Total tax amount for the purchase order."
            ),
        },
        "total_amount": {
            "type": "number",
            "description": """
            Final payable amount of the purchase order.
            May appear as Total Amount, Grand Total,
            Total Price, Amount Payable, Net Amount,
            or Total INR.
            """,
        },
        "line_items": {
            "type": "array",
            "description": (
                "All purchase order line items from the document table."
            ),
            "items": PURCHASE_ORDER_LINE_ITEM_SCHEMA,
        },
    },
}

INVOICE_LINE_ITEM_SCHEMA: dict[str, object] = {
    "type": "object",
    "properties": {
        "line_number": {
            "type": "integer",
            "description": (
                "Sequential line number for the invoice row."
            ),
        },
        "item_code": {
            "type": "string",
            "description": (
                "Product or SKU code for the line item, if shown."
            ),
        },
        "item_description": {
            "type": "string",
            "description": (
                "Description of the billed item or service."
            ),
        },
        "uom": {
            "type": "string",
            "description": (
                "Unit of measure such as PCS, KG, NOS, BOX, or HRS."
            ),
        },
        "quantity_billed": {
            "type": "number",
            "description": (
                "Billed quantity for the line item."
            ),
        },
        "unit_price": {
            "type": "number",
            "description": (
                "Unit price before tax and discounts."
            ),
        },
        "discount_amount": {
            "type": "number",
            "description": (
                "Discount amount applied to the line item."
            ),
        },
        "tax_details": {
            "type": "array",
            "description": (
                "Tax breakdown for the line item such as CGST, SGST, "
                "IGST, or VAT."
            ),
            "items": {
                "type": "object",
                "properties": {
                    "tax_name": {
                        "type": "string",
                        "description": (
                            "Tax label such as CGST, SGST, IGST, or VAT."
                        ),
                    },
                    "tax_value": {
                        "type": "string",
                        "description": (
                            "Tax amount or rate for the line item."
                        ),
                    },
                },
            },
        },
        "hsn_sac_code": {
            "type": "string",
            "description": (
                "HSN or SAC code for the line item, if shown."
            ),
        },
        "line_total": {
            "type": "number",
            "description": (
                "Total amount for the line item after discounts and tax."
            ),
        },
    },
}

INVOICE_EXTRACTION_SCHEMA: dict[str, object] = {
    "type": "object",
    "properties": {
        "invoice_number": {
            "type": "string",
            "description": (
                "Invoice number. May appear as Invoice No, "
                "Invoice Number, or Invoice #."
            ),
        },
        "invoice_date": {
            "type": "string",
            "description": (
                "Invoice date in YYYY-MM-DD when possible."
            ),
        },
        "po_numbers_extracted": {
            "type": "array",
            "description": (
                "Purchase order numbers referenced on the invoice."
            ),
            "items": {
                "type": "string",
            },
        },
        "due_date": {
            "type": "string",
            "description": (
                "Payment due date in YYYY-MM-DD when possible."
            ),
        },
        "currency": {
            "type": "string",
            "description": (
                "Currency code such as INR, USD, or EUR."
            ),
        },
        "payment_terms": {
            "type": "string",
            "description": (
                "Payment terms such as Net 30 or Due on Receipt."
            ),
        },
        "subtotal_amount": {
            "type": "number",
            "description": (
                "Subtotal before tax and after line discounts."
            ),
        },
        "discount_amount": {
            "type": "number",
            "description": (
                "Overall discount amount on the invoice."
            ),
        },
        "tax_amount": {
            "type": "number",
            "description": (
                "Total tax amount on the invoice."
            ),
        },
        "total_amount": {
            "type": "number",
            "description": (
                "Final payable invoice amount."
            ),
        },
        "notes": {
            "type": "string",
            "description": (
                "Notes or amount in words shown on the invoice."
            ),
        },
        "company_name": {
            "type": "string",
            "description": (
                "Buyer or bill-to company name on the invoice."
            ),
        },
        "company_gstin": {
            "type": "string",
            "description": (
                "Buyer GSTIN or tax identification number."
            ),
        },
        "company_address": {
            "type": "string",
            "description": (
                "Buyer or bill-to address on the invoice."
            ),
        },
        "vendor_name": {
            "type": "string",
            "description": (
                "Supplier or vendor name on the invoice."
            ),
        },
        "vendor_gstin": {
            "type": "string",
            "description": (
                "Supplier GSTIN or tax identification number."
            ),
        },
        "vendor_address": {
            "type": "string",
            "description": (
                "Supplier address on the invoice."
            ),
        },
        "vendor_email": {
            "type": "string",
            "description": (
                "Supplier email address, if shown."
            ),
        },
        "vendor_phone": {
            "type": "string",
            "description": (
                "Supplier phone number, if shown."
            ),
        },
        "bank_account_number": {
            "type": "string",
            "description": (
                "Supplier bank account number for payment."
            ),
        },
        "bank_name": {
            "type": "string",
            "description": (
                "Supplier bank name for payment."
            ),
        },
        "ifsc_code": {
            "type": "string",
            "description": (
                "Supplier bank IFSC code."
            ),
        },
        "account_holder_name": {
            "type": "string",
            "description": (
                "Supplier bank account holder name."
            ),
        },
        "line_items": {
            "type": "array",
            "description": (
                "All invoice line items from the document table."
            ),
            "items": INVOICE_LINE_ITEM_SCHEMA,
        },
    },
}

INVOICE_RAW_EXTRACTION_SCHEMA: dict[str, object] = {
    "type": "object",
    "properties": {
        "full_document_text": {
            "type": "string",
            "description": (
                "Complete text from the document including headers, "
                "tables, totals, addresses, tax details, and footers."
            ),
        },
        "labeled_fields": {
            "type": "array",
            "description": (
                "Visible labeled fields from the document as key-value "
                "pairs without forcing them into a fixed schema."
            ),
            "items": {
                "type": "object",
                "properties": {
                    "field_name": {
                        "type": "string",
                        "description": (
                            "Label or field name shown on the document."
                        ),
                    },
                    "field_value": {
                        "type": "string",
                        "description": (
                            "Value associated with the labeled field."
                        ),
                    },
                },
            },
        },
        "tables": {
            "type": "array",
            "description": (
                "Structured table data such as line items, tax rows, "
                "and totals."
            ),
            "items": {
                "type": "object",
                "properties": {
                    "table_name": {
                        "type": "string",
                        "description": (
                            "Table heading or context if visible."
                        ),
                    },
                    "rows": {
                        "type": "array",
                        "description": (
                            "Each row serialized as a JSON string."
                        ),
                        "items": {
                            "type": "string",
                        },
                    },
                },
            },
        },
        "payment_and_bank_details": {
            "type": "array",
            "description": (
                "Bank account, IFSC, payment instructions, and related "
                "payment details visible on the document."
            ),
            "items": {
                "type": "object",
                "properties": {
                    "field_name": {
                        "type": "string",
                        "description": (
                            "Payment or bank detail label."
                        ),
                    },
                    "field_value": {
                        "type": "string",
                        "description": (
                            "Payment or bank detail value."
                        ),
                    },
                },
            },
        },
    },
    "required": [
        "full_document_text",
    ],
}
