PO_LINE_ITEM_PROMPT = """Extract all line items from the purchase order image. One object per line item row.

Rules: numeric amounts (no currency symbols), dates as YYYY-MM-DD, uom examples: EA NOS PCS KG HR, null for absent fields.

Return JSON only:
{"line_items": [{"line_number": 1, "item_code": "SKU-001", "item_description": "Item desc", "uom": "EA", "quantity_ordered": 10, "unit_price": 100.0, "discount_amount": 0, "tax_details": null, "line_total": 1000.0}]}"""
