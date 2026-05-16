from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
import atexit
import logging

logger = logging.getLogger(__name__)

def init_scheduler(app):
    """Initialize and start the background scheduler with the app context."""
    if not app.config.get('SCHEDULER_ENABLED', True):
        logger.info("Scheduler is disabled.")
        return None

    scheduler = BackgroundScheduler()
    scheduler.api_enabled = False

    # ----- Inner job functions (capture app) -----
    def run_pii_redaction():
        from dashboard.utils.pii_redactor import redact_old_reports
        with app.app_context():
            count = redact_old_reports()
            app.logger.info(f"PII redaction completed on {count} reports")

    def sync_conversations():
        from dashboard.utils.data_sync import sync_conversations_from_gateway
        with app.app_context():
            count = sync_conversations_from_gateway()
            app.logger.info(f"Synced {count} conversations")

    def check_recurrence():
        from dashboard.utils.recurrence_monitor import check_gap_recurrence
        with app.app_context():
            reopened = check_gap_recurrence()
            app.logger.info(f"Recurrence check: {reopened} gaps reopened")

    def archive_expired_docs():
        from dashboard.utils.rag_client import rag_archive_expired
        with app.app_context():
            result = rag_archive_expired()
            app.logger.info(f"Expired document archiving: {result}")

    def check_unresolved_conflicts():
        from dashboard.models.conflict import Conflict, ProvisionalResolution
        from dashboard.utils.notifications import send_notification
        from datetime import datetime, timedelta
        from dashboard.extensions import db
        with app.app_context():
            now = datetime.utcnow()
            two_days_ago = now - timedelta(hours=48)
            five_days_ago = now - timedelta(days=5)
            fourteen_days_ago = now - timedelta(days=14)

            old_conflicts = Conflict.query.filter(
                Conflict.status == 'unresolved',
                Conflict.created_at <= two_days_ago,
                Conflict.created_at > five_days_ago
            ).all()
            for c in old_conflicts:
                send_notification(
                    role_flag='manage_knowledge',
                    title='Conflict Unresolved for >48h',
                    message=f'Conflict between {c.doc1.document_id} and {c.doc2.document_id} has been unresolved for over 48 hours.',
                    link=f'/documents/conflicts?id={c.id}'
                )
                c.last_notified = now
                db.session.add(c)
            db.session.commit()

            very_old = Conflict.query.filter(
                Conflict.status == 'unresolved',
                Conflict.created_at <= five_days_ago,
                Conflict.created_at > fourteen_days_ago
            ).all()
            for c in very_old:
                send_notification(
                    role_flag='both',
                    title='Conflict Unresolved for >5 Days',
                    message=f'Conflict between {c.doc1.document_id} and {c.doc2.document_id} has been unresolved for over 5 days.',
                    link=f'/documents/conflicts?id={c.id}'
                )
                c.last_notified = now
                db.session.add(c)
            db.session.commit()

            to_auto = Conflict.query.filter(
                Conflict.status == 'unresolved',
                Conflict.created_at <= fourteen_days_ago
            ).all()
            for c in to_auto:
                selected_doc_id = c.doc1_id  # simplified; use precedence logic
                prov = ProvisionalResolution(
                    conflict_id=c.id,
                    selected_doc_id=selected_doc_id,
                    justification="Auto-resolved after 14 days"
                )
                c.status = 'provisionally_resolved'
                c.provisional_at = now
                db.session.add(prov)
                db.session.commit()
                app.logger.info(f"Conflict {c.id} auto-resolved provisionally")
                send_notification(
                    role_flag='manage_knowledge',
                    title='Conflict Auto-Resolved (Provisional)',
                    message=f'Conflict {c.id} has been auto-resolved provisionally. Please review.',
                    link=f'/documents/conflicts?provisional={prov.id}'
                )

    def check_gap_governance():
        from dashboard.models.knowledge_gap import KnowledgeGap
        from dashboard.utils.notifications import send_notification
        from datetime import datetime, timedelta
        from dashboard.extensions import db
        with app.app_context():
            now = datetime.utcnow()
            thirty_days_ago = now - timedelta(days=30)
            recurring_gaps = KnowledgeGap.query.filter(
                KnowledgeGap.status == 'open',
                KnowledgeGap.recurrence_count >= 5,
                KnowledgeGap.last_asked >= thirty_days_ago
            ).all()
            for gap in recurring_gaps:
                if gap.priority_score < 80:
                    gap.priority_score = max(gap.priority_score, 80)
                    gap.impact = 'HIGH'
                    db.session.add(gap)
                send_notification(
                    role_flag='manage_knowledge',
                    title='High Priority Knowledge Gap',
                    message=f'Gap "{gap.question[:50]}..." has recurred {gap.recurrence_count} times in 30 days.',
                    link=f'/knowledge-gaps?id={gap.id}'
                )
            db.session.commit()

            fourteen_days_ago = now - timedelta(days=14)
            old_gaps = KnowledgeGap.query.filter(
                KnowledgeGap.status == 'open',
                KnowledgeGap.first_asked <= fourteen_days_ago
            ).all()
            for gap in old_gaps:
                send_notification(
                    role_flag='both',
                    title='Knowledge Gap Unresolved for >14 Days',
                    message=f'Gap "{gap.question[:50]}..." has been open for over 14 days.',
                    link=f'/knowledge-gaps?id={gap.id}'
                )

    def check_gap_rate():
        from dashboard.models.knowledge_gap import KnowledgeGap
        from dashboard.models.conversation import Conversation
        from dashboard.utils.notifications import send_notification
        from datetime import datetime, timedelta
        from dashboard.extensions import db
        with app.app_context():
            one_day_ago = datetime.utcnow() - timedelta(days=1)
            total_queries = Conversation.query.filter(
                Conversation.timestamp >= one_day_ago
            ).count()
            if total_queries == 0:
                return
            new_gaps = KnowledgeGap.query.filter(
                KnowledgeGap.first_asked >= one_day_ago
            ).count()
            gap_rate = (new_gaps / total_queries) * 100
            if gap_rate > 8:
                send_notification(
                    role_flag='both',
                    title='High System Gap Rate Alert',
                    message=f'System-wide knowledge gap rate is {gap_rate:.1f}% (>8%) in the last 24 hours.',
                    link='/knowledge-gaps'
                )

    # ----- Schedule jobs -----
    scheduler.add_job(
        func=run_pii_redaction,
        trigger=CronTrigger(hour=2, minute=0),
        id='pii_redaction',
        replace_existing=True
    )
    scheduler.add_job(
        func=sync_conversations,
        trigger='interval',
        hours=1,
        id='sync_conversations',
        replace_existing=True
    )
    scheduler.add_job(
        func=check_recurrence,
        trigger=CronTrigger(hour=3, minute=0),
        id='recurrence_check',
        replace_existing=True
    )
    scheduler.add_job(
        func=archive_expired_docs,
        trigger=CronTrigger(hour=4, minute=0),
        id='archive_expired',
        replace_existing=True
    )
    scheduler.add_job(
        func=check_unresolved_conflicts,
        trigger='interval',
        hours=6,
        id='conflict_escalation',
        replace_existing=True
    )
    scheduler.add_job(
        func=check_gap_governance,
        trigger=CronTrigger(hour=5, minute=0),
        id='gap_governance',
        replace_existing=True
    )
    scheduler.add_job(
        func=check_gap_rate,
        trigger='interval',
        hours=6,
        id='gap_rate_monitor',
        replace_existing=True
    )

    scheduler.start()
    atexit.register(lambda: scheduler.shutdown())
    app.logger.info("Background scheduler started")
    return scheduler