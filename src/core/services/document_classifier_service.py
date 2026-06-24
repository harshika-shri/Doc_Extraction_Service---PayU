from __future__ import annotations

from pathlib import Path

from src.config.llm_config import (
    GROQ_MODEL_CLASSIFY,
)
from src.constants.document_type import (
    DocumentType,
)
from src.constants.prompts.document_classifier_prompt import (
    DOCUMENT_CLASSIFIER_PROMPT,
)
from src.core.services.base_vision_extraction_service import (
    BaseVisionExtractionService,
)
from src.schemas.document_classification_schema import (
    DocumentClassificationSchema,
)


class DocumentClassifierService(
    BaseVisionExtractionService,
):
    def classify_document(
        self,
        file_path: Path,
    ) -> DocumentClassificationSchema:
        payload = self._extract_payload(
            file_path,
            DOCUMENT_CLASSIFIER_PROMPT,
            model=GROQ_MODEL_CLASSIFY,
            max_tokens=512,
        )

        classification = (
            DocumentClassificationSchema.model_validate(
                payload,
            )
        )

        print("\n" + "=" * 80)
        print("DOCUMENT CLASSIFICATION")
        print("=" * 80)
        print(
            f"Type: {classification.document_type}",
        )

        if classification.reason:
            print(
                f"Reason: {classification.reason}",
            )

        return classification

    @staticmethod
    def is_supported_document_type(
        document_type: DocumentType,
    ) -> bool:
        return document_type in {
            DocumentType.INVOICE,
            DocumentType.PURCHASE_ORDER,
        }
