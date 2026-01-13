"""
Enhanced Keyword Analyzer for AI Employee System

Replaces GLM API dependency with sophisticated keyword-based analysis.
Provides intelligent email/message categorization, priority scoring, and risk assessment.

Features:
- Advanced priority scoring algorithm (1-5)
- Context-aware keyword matching
- Risk assessment with multiple factors
- Category detection
- Actionable item extraction
- Business term recognition
- Auto-approval logic
"""

import re
import logging
from typing import Dict, List, Optional, Tuple, Set
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


@dataclass
class KeywordAnalysis:
    """Result of keyword-based analysis."""
    needs_reply: bool
    reason: str
    priority: int  # 1-5 scale
    priority_label: str  # low, normal, high, critical, urgent
    category: str
    subcategory: Optional[str]
    suggested_reply: Optional[str]
    risk_level: str  # safe, low, medium, high, critical
    risk_score: int  # 0-100
    auto_approve: bool
    requires_human_review: bool
    risk_factors: List[str]
    action_items: List[str]
    business_terms: List[str]
    confidence: float  # 0.0-1.0


class KeywordAnalyzer:
    """Advanced keyword-based message analyzer."""

    # Priority keywords with weights
    PRIORITY_KEYWORDS = {
        # Urgent/Critical (5)
        'urgent': 5, 'emergency': 5, 'critical': 5, 'immediate': 5,
        'asap': 5, 'deadline today': 5, 'now': 5, 'right away': 5,

        # High Priority (4)
        'deadline': 4, 'important': 4, 'priority': 4, 'time sensitive': 4,
        'expiring': 4, 'expiring soon': 4, 'last chance': 4, 'final notice': 4,
        'overdue': 4, 'payment due': 4, 'contract': 4, 'agreement': 4,
        'legal': 4, 'compliance': 4, 'regulatory': 4, 'audit': 4,

        # Medium-High Priority (3)
        'meeting': 3, 'call': 3, 'schedule': 3, 'appointment': 3,
        'interview': 3, 'demo': 3, 'presentation': 3, 'review': 3,
        'invoice': 3, 'quote': 3, 'proposal': 3, 'estimate': 3,
        'project': 3, 'deliverable': 3, 'milestone': 3, 'release': 3,

        # Medium Priority (2)
        'update': 2, 'status': 2, 'progress': 2, 'report': 2,
        'question': 2, 'inquiry': 2, 'request': 2, 'help': 2,
        'support': 2, 'assistance': 2, 'guidance': 2, 'advice': 2,
        'feedback': 2, 'input': 2, 'thoughts': 2, 'opinion': 2,
        'discussion': 2, 'consult': 2, 'advise': 2, 'confirm': 2,

        # Standard/Low Priority (1)
        'information': 1, 'fyi': 1, 'for your information': 1,
        'newsletter': 1, 'announcement': 1, 'notification': 1,
        'marketing': 1, 'promotion': 1, 'offer': 1
    }

    # Risk assessment keywords
    RISK_KEYWORDS = {
        # Critical Risk (100)
        'lawsuit': 100, 'legal action': 100, 'court': 100, 'litigation': 100,
        'breach': 100, 'violation': 100, 'penalty': 100, 'fine': 100,

        # High Risk (75)
        'complaint': 75, 'dispute': 75, 'conflict': 75, 'escalation': 75,
        'unhappy': 75, 'dissatisfied': 75, 'cancel': 75, 'termination': 75,
        'refund': 75, 'chargeback': 75, 'money back': 75,

        # Medium Risk (50)
        'confidential': 50, 'secret': 50, 'proprietary': 50, 'sensitive': 50,
        'nda': 50, 'non-disclosure': 50, 'private': 50,
        'financial': 50, 'bank': 50, 'credit': 50, 'payment': 50,
        'salary': 50, 'compensation': 50, 'negotiate': 50, 'bargain': 50,

        # Low Risk (25)
        'contract': 25, 'agreement': 25, 'terms': 25, 'conditions': 25,
        'commit': 25, 'promise': 25, 'guarantee': 25, 'deadline': 25,
        'delivery': 25, 'shipment': 25, 'launch': 25, 'release': 25
    }

    # Business-critical terms that require human review
    BUSINESS_CRITICAL = {
        'pricing', 'price', 'cost', 'quote', 'estimate', 'proposal', 'bid',
        'contract', 'agreement', 'nda', 'sign', 'signature', 'execute',
        'commitment', 'deliverable', 'promise', 'guarantee', 'warranty',
        'payment', 'invoice', 'pay', 'refund', 'billing', 'charge',
        'legal', 'lawsuit', 'attorney', 'liability', 'indemnify',
        'project', 'service', 'product', 'feature', 'specification', 'scope',
        'attach', 'attachment', 'document', 'file', 'contract', 'agreement'
    }

    # Category detection patterns
    CATEGORIES = {
        'finance': ['invoice', 'payment', 'quote', 'pricing', 'cost', 'budget', 'financial', 'billing'],
        'legal': ['contract', 'agreement', 'legal', 'nda', 'lawsuit', 'attorney', 'compliance'],
        'hr': ['hiring', 'firing', 'recruit', 'interview', 'salary', 'employment', 'resume', 'candidate'],
        'project': ['project', 'deliverable', 'milestone', 'deadline', 'scope', 'timeline', 'release'],
        'meeting': ['meeting', 'call', 'schedule', 'appointment', 'calendar', 'zoom', 'teams'],
        'support': ['help', 'support', 'issue', 'problem', 'error', 'bug', 'fix', 'troubleshoot'],
        'sales': ['sales', 'lead', 'prospect', 'customer', 'client', 'opportunity', 'deal'],
        'marketing': ['marketing', 'campaign', 'promotion', 'advertisement', 'social media'],
        'operations': ['operations', 'process', 'workflow', 'procedure', 'logistics', 'inventory'],
        'technical': ['technical', 'development', 'engineering', 'api', 'integration', 'code'],
        'communication': ['update', 'announcement', 'newsletter', 'notification', 'fyi', 'information']
    }

    # Action item indicators
    ACTION_PATTERNS = [
        r'please\s+(\w+)',  # please [do something]
        r'can you\s+(\w+)',  # can you [do something]
        r'could you\s+(\w+)',  # could you [do something]
        r'would you\s+(\w+)',  # would you [do something]
        r'need you to\s+(\w+)',  # need you to [do something]
        r'require[s]?\s+(\w+)',  # require(s) [something]
        r'looking for\s+(\w+)',  # looking for [something]
        r'i want\s+(\w+)',  # i want [something]
        r'interested in\s+(\w+)'  # interested in [something]
    ]

    # Safe patterns that can be auto-approved
    SAFE_PATTERNS = [
        'thank you', 'thanks', 'appreciate', 'acknowledged', 'received',
        'got it', 'noted', 'understood', 'confirm receipt', 'well received'
    ]

    def __init__(self, company_handbook_path: Optional[str] = None):
        """Initialize keyword analyzer.

        Args:
            company_handbook_path: Optional path to company handbook for custom keywords
        """
        self.logger = logging.getLogger('KeywordAnalyzer')
        self.company_keywords: Set[str] = set()
        self.custom_priority_keywords: Dict[str, int] = {}

        # Load custom keywords from company handbook if available
        if company_handbook_path:
            self._load_company_keywords(company_handbook_path)

    def _load_company_keywords(self, handbook_path: str) -> None:
        """Load custom keywords from company handbook.

        Args:
            handbook_path: Path to company handbook markdown file
        """
        try:
            handbook = Path(handbook_path)
            if handbook.exists():
                content = handbook.read_text()

                # Extract custom keywords from handbook
                # Look for sections like "## Priority Keywords" or "## Important Terms"
                custom_section = re.search(
                    r'##\s*(Priority Keywords|Important Terms|Custom Keywords)(.*?)(?=##|\Z)',
                    content,
                    re.DOTALL | re.IGNORECASE
                )

                if custom_section:
                    keywords_text = custom_section.group(2)
                    # Extract bullet points or comma-separated keywords
                    keywords = re.findall(r'[-*]\s*([^,\n]+)|([^,\n]{3,})', keywords_text)
                    self.company_keywords.update({kw.strip().lower() for kw, _ in keywords if kw.strip()})

                    self.logger.info(f'Loaded {len(self.company_keywords)} custom keywords from handbook')

        except Exception as e:
            self.logger.warning(f'Failed to load company keywords: {e}')

    def analyze(
        self,
        sender: str,
        subject: str,
        body: str,
        conversation_history: Optional[List[Dict]] = None
    ) -> KeywordAnalysis:
        """Analyze message using advanced keyword matching.

        Args:
            sender: Message sender
            subject: Message subject
            body: Message body
            conversation_history: Optional previous messages

        Returns:
            KeywordAnalysis with detailed analysis
        """
        # Normalize text
        subject_lower = subject.lower().strip()
        body_lower = body.lower().strip()
        combined = f"{subject_lower} {body_lower}"

        # Extract components
        priority_info = self._calculate_priority(combined)
        category_info = self._detect_category(combined)
        risk_info = self._assess_risk(combined)
        action_items = self._extract_action_items(combined)
        business_terms = self._extract_business_terms(combined)

        # Determine if reply needed
        needs_reply = self._needs_reply(combined, action_items)

        # Auto-approval logic
        auto_approve, requires_human_review = self._determine_approval(
            combined, risk_info['score'], business_terms, action_items, conversation_history
        )

        # Generate suggested reply
        suggested_reply = self._generate_reply(
            sender, subject, category_info['category'], action_items, needs_reply
        )

        # Calculate confidence
        confidence = self._calculate_confidence(
            priority_info['score'], risk_info['score'], category_info['confidence']
        )

        # Determine reason
        reason_parts = []
        if priority_info['matched_keywords']:
            reason_parts.append(f"Priority: {priority_info['label']}")
        if category_info['category'] != 'general':
            reason_parts.append(f"Category: {category_info['category']}")
        if risk_info['factors']:
            reason_parts.append(f"{len(risk_info['factors'])} risk factors")
        if action_items:
            reason_parts.append(f"{len(action_items)} action items")

        reason = " | ".join(reason_parts) if reason_parts else "General message analysis"

        return KeywordAnalysis(
            needs_reply=needs_reply,
            reason=reason,
            priority=priority_info['score'],
            priority_label=priority_info['label'],
            category=category_info['category'],
            subcategory=category_info.get('subcategory'),
            suggested_reply=suggested_reply,
            risk_level=risk_info['level'],
            risk_score=risk_info['score'],
            auto_approve=auto_approve,
            requires_human_review=requires_human_review,
            risk_factors=risk_info['factors'],
            action_items=action_items,
            business_terms=business_terms,
            confidence=confidence
        )

    def _calculate_priority(self, text: str) -> Dict:
        """Calculate priority score (1-5).

        Args:
            text: Normalized message text

        Returns:
            Dict with score, label, and matched keywords
        """
        max_score = 0
        matched_keywords = []

        # Check all priority keywords
        for keyword, weight in self.PRIORITY_KEYWORDS.items():
            if keyword in text:
                if weight > max_score:
                    max_score = weight
                matched_keywords.append(keyword)

        # Check company keywords (default to priority 3)
        for company_kw in self.company_keywords:
            if company_kw in text:
                if max_score < 3:
                    max_score = 3
                matched_keywords.append(f"company: {company_kw}")

        # Map score to label
        label_map = {
            5: 'urgent',
            4: 'high',
            3: 'medium',
            2: 'normal',
            1: 'low'
        }

        # Check for urgency boosters
        if any(word in text for word in ['!', 'urgent', 'asap', 'immediately']):
            max_score = min(5, max_score + 1)

        # Minimum priority is 1
        max_score = max(1, max_score)

        return {
            'score': max_score,
            'label': label_map.get(max_score, 'normal'),
            'matched_keywords': matched_keywords
        }

    def _detect_category(self, text: str) -> Dict:
        """Detect message category.

        Args:
            text: Normalized message text

        Returns:
            Dict with category and confidence
        """
        scores = {}

        # Score each category
        for category, keywords in self.CATEGORIES.items():
            score = sum(1 for kw in keywords if kw in text)
            if score > 0:
                scores[category] = score

        if not scores:
            return {
                'category': 'general',
                'subcategory': None,
                'confidence': 0.5
            }

        # Get highest scoring category
        best_category = max(scores, key=scores.get)
        confidence = min(1.0, scores[best_category] * 0.3)

        return {
            'category': best_category,
            'subcategory': None,
            'confidence': confidence
        }

    def _assess_risk(self, text: str) -> Dict:
        """Assess risk level and factors.

        Args:
            text: Normalized message text

        Returns:
            Dict with risk level, score, and factors
        """
        total_score = 0
        factors = []

        # Check risk keywords
        for keyword, score in self.RISK_KEYWORDS.items():
            if keyword in text:
                total_score += score
                factors.append(f"'{keyword}' detected")

        # Check for business-critical terms
        for term in self.BUSINESS_CRITICAL:
            if term in text:
                total_score += 15
                factors.append(f"Business-critical: {term}")

        # Determine risk level
        if total_score >= 75:
            level = 'critical'
        elif total_score >= 50:
            level = 'high'
        elif total_score >= 25:
            level = 'medium'
        elif total_score >= 10:
            level = 'low'
        else:
            level = 'safe'

        # Cap score at 100
        total_score = min(100, total_score)

        return {
            'level': level,
            'score': total_score,
            'factors': factors
        }

    def _extract_action_items(self, text: str) -> List[str]:
        """Extract action items from text.

        Args:
            text: Normalized message text

        Returns:
            List of action items
        """
        action_items = []

        # Check action patterns
        for pattern in self.ACTION_PATTERNS:
            matches = re.finditer(pattern, text)
            for match in matches:
                action = match.group(0)
                if len(action) > 5:  # Filter short matches
                    action_items.append(action)

        # Look for sentences starting with action verbs
        action_verbs = ['please', 'can you', 'could you', 'would you', 'need to', 'should']
        sentences = re.split(r'[.!?]', text)
        for sentence in sentences:
            if any(verb in sentence for verb in action_verbs):
                sentence = sentence.strip()
                if len(sentence) > 10:
                    action_items.append(sentence)

        # Remove duplicates and limit
        action_items = list(set(action_items))[:5]

        return action_items

    def _extract_business_terms(self, text: str) -> List[str]:
        """Extract business-critical terms from text.

        Args:
            text: Normalized message text

        Returns:
            List of business terms found
        """
        found_terms = []

        for term in self.BUSINESS_CRITICAL:
            if term in text:
                found_terms.append(term)

        return list(set(found_terms))

    def _needs_reply(self, text: str, action_items: List[str]) -> bool:
        """Determine if message needs a reply.

        Args:
            text: Normalized message text
            action_items: Extracted action items

        Returns:
            True if reply needed
        """
        # Direct questions
        if '?' in text:
            return True

        # Action items present
        if action_items:
            return True

        # Request indicators
        request_indicators = ['please', 'can you', 'could you', 'would you', 'need', 'help']
        if any(indicator in text for indicator in request_indicators):
            return True

        # Forward/reply indicators
        if any(word in text for word in ['fw:', 'fwd:', 're:']):
            return True

        return False

    def _determine_approval(
        self,
        text: str,
        risk_score: int,
        business_terms: List[str],
        action_items: List[str],
        conversation_history: Optional[List[Dict]]
    ) -> Tuple[bool, bool]:
        """Determine if message can be auto-approved.

        Args:
            text: Normalized message text
            risk_score: Risk score (0-100)
            business_terms: Business-critical terms found
            action_items: Action items extracted
            conversation_history: Previous messages

        Returns:
            Tuple of (auto_approve, requires_human_review)
        """
        # Safe pattern detection
        is_safe_pattern = any(pattern in text for pattern in self.SAFE_PATTERNS)

        # High risk always requires review
        if risk_score >= 50:
            return False, True

        # Business-critical terms require review
        if business_terms:
            return False, True

        # Complex action items require review
        if len(action_items) > 2:
            return False, True

        # Long conversation threads require review
        if conversation_history and len(conversation_history) > 3:
            return False, True

        # Safe patterns with low risk can be auto-approved
        if is_safe_pattern and risk_score < 25:
            return True, False

        # Simple action items with low risk
        if len(action_items) <= 1 and risk_score < 25:
            return True, False

        # Default: requires review
        return False, True

    def _generate_reply(
        self,
        sender: str,
        subject: str,
        category: str,
        action_items: List[str],
        needs_reply: bool
    ) -> Optional[str]:
        """Generate suggested reply.

        Args:
            sender: Sender email/name
            subject: Message subject
            category: Message category
            action_items: Action items
            needs_reply: Whether reply is needed

        Returns:
            Suggested reply text or None
        """
        if not needs_reply:
            return None

        # Extract sender name
        sender_name = sender.split('<')[0].strip().capitalize() or "there"

        # Check for safe acknowledgment patterns
        combined = f"{subject.lower()} {' '.join(action_items).lower()}"
        if any(pattern in combined for pattern in self.SAFE_PATTERNS):
            return f"""Hi {sender_name},

Thank you for your message. I've received it and appreciate you reaching out.

Best regards"""

        # Category-specific replies
        category_replies = {
            'finance': f"""Hi {sender_name},

Thank you for your email regarding financial matters. I've received your message and will review the details shortly. I'll get back to you as soon as possible.

Best regards""",

            'legal': f"""Hi {sender_name},

I've received your message regarding legal matters. This requires careful review, and I'll get back to you shortly after I've had a chance to assess the details.

Best regards""",

            'hr': f"""Hi {sender_name},

Thank you for reaching out regarding HR matters. I've received your message and will review it promptly. I'll be in touch soon with any follow-up.

Best regards""",

            'project': f"""Hi {sender_name},

Thank you for the update regarding the project. I've received your message and will review the details. I'll follow up with you shortly if any action is needed on my part.

Best regards""",

            'meeting': f"""Hi {sender_name},

Thank you for reaching out. I'd be happy to schedule a meeting. Could you please share a few time slots that work well for you? I'll do my best to accommodate.

Best regards""",

            'support': f"""Hi {sender_name},

Thank you for reaching out for support. I've received your message and understand you need assistance with this matter. I'll look into it and get back to you shortly.

Best regards"""
        }

        if category in category_replies:
            return category_replies[category]

        # Default reply
        return f"""Hi {sender_name},

Thank you for your email. I've received your message and will review it shortly. I'll get back to you as soon as possible.

Best regards"""

    def _calculate_confidence(self, priority_score: int, risk_score: int, category_conf: float) -> float:
        """Calculate overall confidence in analysis.

        Args:
            priority_score: Priority score (1-5)
            risk_score: Risk score (0-100)
            category_conf: Category confidence (0.0-1.0)

        Returns:
            Overall confidence (0.0-1.0)
        """
        # Higher confidence with clear signals
        if priority_score >= 4 or risk_score >= 50:
            return min(1.0, category_conf + 0.3)

        if category_conf > 0.7:
            return 0.8

        return 0.6


# ============ SKILL FUNCTIONS ============

def analyze_message(
    sender: str,
    subject: str,
    body: str,
    company_handbook: Optional[str] = None
) -> str:
    """Skill function: Analyze message using keyword analyzer.

    Args:
        sender: Message sender
        subject: Message subject
        body: Message body
        company_handbook: Optional path to company handbook

    Returns:
        Analysis summary
    """
    analyzer = KeywordAnalyzer(company_handbook)
    analysis = analyzer.analyze(sender, subject, body)

    result = f"""📧 Message Analysis

Needs Reply: {'✅ Yes' if analysis.needs_reply else '❌ No'}
Priority: {analysis.priority_label.upper()} ({analysis.priority}/5)
Category: {analysis.category}
Risk Level: {analysis.risk_level.upper()} (Score: {analysis.risk_score}/100)
Auto-Approve: {'✅ Yes' if analysis.auto_approve else '❌ No (Human Review)'}
Confidence: {analysis.confidence:.1%}

Reason: {analysis.reason}
"""

    if analysis.business_terms:
        result += f"\n💼 Business Terms:\n"
        for term in analysis.business_terms:
            result += f"  - {term}\n"

    if analysis.risk_factors:
        result += f"\n⚠️ Risk Factors:\n"
        for factor in analysis.risk_factors:
            result += f"  - {factor}\n"

    if analysis.action_items:
        result += f"\n✅ Action Items:\n"
        for item in analysis.action_items:
            result += f"  - {item}\n"

    if analysis.suggested_reply:
        result += f"\n📝 Suggested Reply:\n{analysis.suggested_reply}\n"

    return result


__all__ = [
    'KeywordAnalyzer',
    'KeywordAnalysis',
    'analyze_message'
]
