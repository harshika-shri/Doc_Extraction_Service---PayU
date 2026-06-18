from uuid import UUID

from src.data.models.postgres.enums import (
    IssueType,
    ValidationIssueStatus,
)
from src.data.models.postgres.invoice_validation_issues import (
    InvoiceValidationIssue,
)
from src.data.repositories.base_repo import BaseRepository
from src.schemas.extraction_persistence_schema import (
    ValidationIssuePayload,
)


class InvoiceValidationIssueRepository(BaseRepository):
    async def create(
        self,
        invoice_id: UUID,
        issue: ValidationIssuePayload,
    ) -> InvoiceValidationIssue:
        validation_issue = InvoiceValidationIssue(
            invoice_id=invoice_id,
            check_stage=issue.check_stage,
            check_name=issue.check_name,
            field_name=issue.field_name,
            field_path=issue.field_path,
            issue_type=IssueType(
                issue.issue_type,
            ),
            expected_value=issue.expected_value,
            actual_value=issue.actual_value,
            description=issue.description,
            status=ValidationIssueStatus(
                issue.status,
            ),
            issue_metadata=issue.metadata,
        )

        self.session.add(validation_issue)

        return validation_issue
