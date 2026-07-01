DOCUMENT_CLASSIFIER_PROMPT = """Classify this document as one of: invoice, purchase_order, other.

INVOICE: Issued by seller/vendor to request payment. Contains invoice number, invoice date, bill-to, line items billed, tax, total, bank/payment details. Business intent = requesting payment.

PURCHASE_ORDER: Issued by buyer to order goods/services. Contains PO number, ordered items, quantities, delivery info. Business intent = placing an order.

OTHER: Anything that is not an actual transactional invoice or purchase order document (e.g. flowcharts, screenshots, presentations, documents that discuss or describe invoices/POs rather than being one).

When document_type is invoice or purchase_order, also classify document_format:
- digital: native electronic document with selectable/copyable text (born-digital PDF, Word/exported PDF with a real text layer)
- scanned: photograph or scan of paper, or image-based PDF where content is visible as pixels rather than selectable text

RULES:
- Classify based on what the document IS, not what it mentions.
- A document must contain the actual business-transaction structure (identifiers, parties, amounts/items) to qualify as invoice or purchase_order.
- When uncertain about document_type, classify as other.
- When uncertain about document_format for invoice/purchase_order, prefer scanned.
- Set document_format to null when document_type is other.

Return JSON only:
{"document_type": "invoice|purchase_order|other", "document_format": "digital|scanned|null", "reason": "brief explanation"}"""
