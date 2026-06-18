from src.constants.document_type import (
    DocumentType,
)
from src.constants.llm_prompt_constants import (
    CLASSIFICATION_PROMPT,
)
from src.schemas.document_classification_schema import (
    DocumentClassificationSchema,
)
from src.utils.llm_response_utils import (
    call_groq_llm,
    trim_raw_extraction_for_llm,
)


class DocumentClassificationService:
    def classify_from_raw(
        self,
        raw_extraction: str,
    ) -> DocumentClassificationSchema:
        response_text = call_groq_llm(
            f"{CLASSIFICATION_PROMPT}\n"
            f"{trim_raw_extraction_for_llm(raw_extraction)}",
        )

        classification = (
            DocumentClassificationSchema.model_validate_json(
                response_text,
            )
        )

        print("\n" + "=" * 80)
        print("DOCUMENT CLASSIFICATION")
        print("=" * 80)
        print(
            f"Type: "
            f"{classification.document_type}",
        )

        if (
            classification.confidence
            is not None
        ):
            print(
                f"Confidence: "
                f"{classification.confidence}",
            )

        if classification.reason:
            print(
                f"Reason: "
                f"{classification.reason}",
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
