"""
Automatic knowledge gap detection from conversations – Module 5
"""
import logging
from typing import List, Dict
from datetime import datetime, timedelta
from collections import Counter
from dashboard.models import SessionLocal, Conversation, KnowledgeGap

logger = logging.getLogger(__name__)

class KnowledgeGapDetector:
    """Detects knowledge gaps from conversation patterns"""

    def __init__(self):
        self.similarity_threshold = 0.7
        self.min_frequency = 3

    def analyze_conversations(self, days: int = 7) -> List[Dict]:
        """Analyze recent conversations to find knowledge gaps"""
        db = SessionLocal()
        try:
            # Get conversations from last N days with no/poor responses
            cutoff_date = datetime.now() - timedelta(days=days)

            conversations = db.query(Conversation).filter(
                Conversation.timestamp >= cutoff_date,
                (Conversation.chatbot_response == None) |
                (Conversation.confidence < 0.5)
            ).all()

            if not conversations:
                return []

            # Group similar questions
            question_groups = self._group_similar_questions(conversations)

            # Create knowledge gaps for frequent questions
            gaps = []

            for question, similar_convos in question_groups.items():
                frequency = len(similar_convos)

                if frequency >= self.min_frequency:
                    # Calculate priority score
                    priority_score = self._calculate_priority(similar_convos)

                    # Determine department/service
                    dept_counts = Counter([c.department for c in similar_convos if c.department])
                    service = dept_counts.most_common(1)[0][0] if dept_counts else 'other'

                    # Determine service risk (simplified)
                    service_risk = self._get_service_risk(service)

                    gaps.append({
                        'question': question,
                        'service': service,
                        'service_risk': service_risk,
                        'frequency': frequency,
                        'priority_score': priority_score,
                        'impact': self._calculate_impact(priority_score, service_risk, 0),
                        'first_asked': min(c.timestamp for c in similar_convos),
                        'last_asked': max(c.timestamp for c in similar_convos),
                        'sample_conversations': [c.id for c in similar_convos[:5]]
                    })

            # Sort by priority
            gaps.sort(key=lambda x: x['priority_score'], reverse=True)

            return gaps
        finally:
            db.close()

    def _group_similar_questions(self, conversations: List[Conversation]) -> Dict:
        """Group similar questions together (simple word overlap)"""
        question_groups = {}

        for convo in conversations:
            question = convo.user_message.strip().lower()

            # Find similar existing question
            found_match = False
            for existing_q in list(question_groups.keys()):
                if self._are_similar(question, existing_q):
                    question_groups[existing_q].append(convo)
                    found_match = True
                    break

            if not found_match:
                question_groups[question] = [convo]

        return question_groups

    def _are_similar(self, q1: str, q2: str) -> bool:
        """Check if two questions are similar based on word overlap"""
        words1 = set(q1.split())
        words2 = set(q2.split())

        if not words1 or not words2:
            return False

        overlap = len(words1 & words2)
        similarity = overlap / max(len(words1), len(words2))
        return similarity >= self.similarity_threshold

    def _calculate_priority(self, conversations: List[Conversation]) -> int:
        """Calculate priority score for a knowledge gap"""
        frequency = len(conversations)
        unique_users = len(set(c.user_id for c in conversations))
        recency = (datetime.now() - max(c.timestamp for c in conversations)).days
        recency_factor = max(0, 30 - recency) / 30

        priority = int(
            (frequency * 10) +
            (unique_users * 5) +
            (recency_factor * 20)
        )
        return min(100, priority)

    def _get_service_risk(self, service: str) -> str:
        """Get risk level for a service (simplified)"""
        high_risk_services = ['health', 'emergency', 'water']
        medium_risk_services = ['transport', 'waste', 'revenue']
        if service in high_risk_services:
            return 'high'
        if service in medium_risk_services:
            return 'medium'
        return 'low'

    def _calculate_impact(self, priority: int, service_risk: str, recurrence: int) -> str:
        """Determine impact label with minimum floors"""
        if priority >= 80:
            base = 'HIGH'
        elif priority >= 50:
            base = 'MEDIUM'
        else:
            base = 'LOW'

        # Apply minimum floors
        if service_risk == 'critical' and base == 'LOW':
            return 'MEDIUM'
        if service_risk == 'high' and base == 'LOW':
            return 'MEDIUM'
        if recurrence >= 1 and base == 'LOW':
            return 'MEDIUM'
        return base

    def create_knowledge_gaps(self, gaps: List[Dict]) -> int:
        """Create knowledge gap records in database"""
        db = SessionLocal()
        created = 0

        try:
            for gap_data in gaps:
                # Check if gap already exists (similar question, not resolved)
                existing = db.query(KnowledgeGap).filter(
                    KnowledgeGap.question == gap_data['question'],
                    KnowledgeGap.status != 'completed'
                ).first()

                if existing:
                    # Update existing gap
                    existing.frequency = gap_data['frequency']
                    existing.last_asked = gap_data['last_asked']
                    existing.priority_score = gap_data['priority_score']
                    existing.impact = gap_data['impact']
                else:
                    # Create new gap
                    gap = KnowledgeGap(
                        question=gap_data['question'],
                        service=gap_data['service'],
                        service_risk=gap_data['service_risk'],
                        first_asked=gap_data['first_asked'],
                        last_asked=gap_data['last_asked'],
                        frequency=gap_data['frequency'],
                        priority_score=gap_data['priority_score'],
                        impact=gap_data['impact'],
                        status='open'
                    )
                    db.add(gap)
                    created += 1

            db.commit()
            logger.info(f"Created {created} new knowledge gaps")
            return created

        except Exception as e:
            logger.error(f"Error creating knowledge gaps: {e}")
            db.rollback()
            return 0
        finally:
            db.close()

    def check_recurrence(self) -> List[Dict]:
        """Check for gaps that have recurred after being marked completed"""
        db = SessionLocal()
        try:
            # Find gaps completed in last 30 days
            thirty_days_ago = datetime.now() - timedelta(days=30)
            completed_gaps = db.query(KnowledgeGap).filter(
                KnowledgeGap.status == 'completed',
                KnowledgeGap.resolved_at >= thirty_days_ago
            ).all()

            recurred = []
            for gap in completed_gaps:
                # Look for new open gaps with similar question
                similar = db.query(KnowledgeGap).filter(
                    KnowledgeGap.question.contains(gap.question[:30]),  # crude match
                    KnowledgeGap.status == 'open',
                    KnowledgeGap.created_at > gap.resolved_at
                ).first()
                if similar:
                    # Increment recurrence count on original
                    gap.recurrence_count += 1
                    gap.resolution_quality_score = max(0, gap.resolution_quality_score - 20)
                    # Optionally reopen original? For now just mark
                    recurred.append({
                        'original_id': gap.id,
                        'new_id': similar.id,
                        'question': gap.question
                    })

            db.commit()
            return recurred
        finally:
            db.close()

# Create singleton instance
gap_detector = KnowledgeGapDetector()