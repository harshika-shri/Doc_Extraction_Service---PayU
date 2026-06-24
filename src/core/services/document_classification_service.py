from src.config.llm_config import (
    CLASSIFICATION_TEXT_LIMIT,
    GROQ_MODEL_CLASSIFY,
)
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
    extract_classification_snippet,
    parse_llm_model,
)


class DocumentClassificationService:
    def classify_from_raw(
        self,
        raw_extraction: str,
    ) -> DocumentClassificationSchema:
        snippet = extract_classification_snippet(
            raw_extraction,
            max_chars=CLASSIFICATION_TEXT_LIMIT,
        )

        response_text = call_groq_llm(
            f"{CLASSIFICATION_PROMPT}\n{snippet}",
            model=GROQ_MODEL_CLASSIFY,
            max_tokens=512,
        )

        classification = parse_llm_model(
            response_text,
            DocumentClassificationSchema,
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
