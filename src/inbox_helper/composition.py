"""Application composition root and resource lifecycle."""

from collections.abc import Iterator
from contextlib import ExitStack, contextmanager
from dataclasses import dataclass

from inbox_helper.application.services.approved_reply_export_service import (
    ApprovedReplyExportService,
)
from inbox_helper.application.services.dashboard_service import DashboardService
from inbox_helper.application.services.email_classifier import EmailClassifier
from inbox_helper.application.services.email_ingestion import EmailIngestionService
from inbox_helper.application.services.email_processing_service import (
    EmailProcessingService,
)
from inbox_helper.application.services.email_query_service import EmailQueryService
from inbox_helper.application.services.provider_health_service import (
    ProviderHealthService,
)
from inbox_helper.application.services.reply_draft_service import ReplyDraftService
from inbox_helper.application.services.review_queue_service import ReviewQueueService
from inbox_helper.core.config import AppConfig, get_config
from inbox_helper.core.logging import configure_logging
from inbox_helper.infrastructure.csv.email_csv_reader import EmailCsvReader
from inbox_helper.infrastructure.csv.approved_reply_exporter import (
    ApprovedReplyCsvExporter,
)
from inbox_helper.infrastructure.llm.factory import (
    create_llm_health_check,
    create_llm_provider,
)
from inbox_helper.infrastructure.persistence.sqlite_email_repository import (
    SqliteEmailRepository,
)
from inbox_helper.infrastructure.persistence.sqlite_email_processing_repository import (
    SqliteEmailProcessingRepository,
)
from inbox_helper.infrastructure.persistence.sqlite_reply_draft_repository import (
    SqliteReplyDraftRepository,
)


@dataclass(frozen=True)
class UiApplicationServices:
    """Application services and configuration exposed to the UI boundary."""

    ingestion: EmailIngestionService
    email_query: EmailQueryService
    email_processing: EmailProcessingService
    classifier: EmailClassifier
    reply_drafts: ReplyDraftService
    review_queue: ReviewQueueService
    dashboard: DashboardService
    approved_export: ApprovedReplyExportService
    provider_health: ProviderHealthService
    demo_mode: bool
    llm_provider: str
    llm_model: str


def create_classification_service(
    config: AppConfig | None = None,
) -> EmailClassifier:
    """Build the classification service without creating ingestion resources."""
    active_config = config or get_config()
    return EmailClassifier(create_llm_provider(active_config))


def create_provider_health_service(
    config: AppConfig | None = None,
) -> ProviderHealthService:
    """Build the provider health service separately from completion retries."""
    active_config = config or get_config()
    return ProviderHealthService(create_llm_health_check(active_config))


@contextmanager
def create_ui_application(
    config: AppConfig | None = None,
) -> Iterator[UiApplicationServices]:
    """Build UI services together and close their SQLite resources reliably."""
    active_config = config or get_config()
    active_config.ensure_db_directory()
    configure_logging(active_config.log_level)
    with ExitStack() as stack:
        email_repository = stack.enter_context(
            SqliteEmailRepository(active_config.db_path)
        )
        draft_repository = stack.enter_context(
            SqliteReplyDraftRepository(active_config.db_path)
        )
        processing_repository = stack.enter_context(
            SqliteEmailProcessingRepository(active_config.db_path)
        )
        provider = create_llm_provider(active_config)
        ingestion = EmailIngestionService(EmailCsvReader(), email_repository)
        email_query = EmailQueryService(email_repository)
        classifier = EmailClassifier(provider)
        reply_drafts = ReplyDraftService(provider, draft_repository)
        services = UiApplicationServices(
            ingestion=ingestion,
            email_query=email_query,
            email_processing=EmailProcessingService(
                ingestion,
                email_query,
                classifier,
                reply_drafts,
                draft_repository,
                processing_repository,
            ),
            classifier=classifier,
            reply_drafts=reply_drafts,
            review_queue=ReviewQueueService(draft_repository),
            dashboard=DashboardService(email_repository, draft_repository),
            approved_export=ApprovedReplyExportService(
                draft_repository, ApprovedReplyCsvExporter()
            ),
            provider_health=create_provider_health_service(active_config),
            demo_mode=active_config.demo_mode,
            llm_provider=active_config.llm_provider,
            llm_model=active_config.llm_model,
        )
        yield services


@contextmanager
def create_review_queue_service(
    config: AppConfig | None = None,
) -> Iterator[ReviewQueueService]:
    """Build the pending-draft queue service with its repository lifecycle."""
    active_config = config or get_config()
    configure_logging(active_config.log_level)
    email_repository = SqliteEmailRepository(active_config.db_path)
    email_repository.close()
    repository = SqliteReplyDraftRepository(active_config.db_path)
    try:
        yield ReviewQueueService(repository)
    finally:
        repository.close()


@contextmanager
def create_approved_reply_export_service(
    config: AppConfig | None = None,
) -> Iterator[ApprovedReplyExportService]:
    """Build approved-only export with its repository and CSV writer."""
    active_config = config or get_config()
    configure_logging(active_config.log_level)
    email_repository = SqliteEmailRepository(active_config.db_path)
    email_repository.close()
    repository = SqliteReplyDraftRepository(active_config.db_path)
    try:
        yield ApprovedReplyExportService(repository, ApprovedReplyCsvExporter())
    finally:
        repository.close()


@contextmanager
def create_reply_draft_service(
    config: AppConfig | None = None,
) -> Iterator[ReplyDraftService]:
    """Build the reply-draft service and own its SQLite repository lifecycle."""
    active_config = config or get_config()
    configure_logging(active_config.log_level)
    email_repository = SqliteEmailRepository(active_config.db_path)
    email_repository.close()
    repository = SqliteReplyDraftRepository(active_config.db_path)
    try:
        service = ReplyDraftService(
            create_llm_provider(active_config),
            repository,
        )
        yield service
    finally:
        repository.close()


@contextmanager
def create_application(
    config: AppConfig | None = None,
) -> Iterator[EmailIngestionService]:
    """Build the Day 1 application and close its database resource on exit."""
    active_config = config or get_config()
    configure_logging(active_config.log_level)
    repository = SqliteEmailRepository(active_config.db_path)
    try:
        reader = EmailCsvReader()
        service = EmailIngestionService(reader, repository)
        yield service
    finally:
        repository.close()
