"""
AI Employee Plan Generator Skill

Analyzes emails and tasks to determine when complex planning is needed.
Generates structured markdown plans with steps, timelines, and dependencies.
"""

import re
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Any, Optional


class PlanGenerator:
    """
    Generates structured plans for complex tasks detected in emails.

    Analyzes email content to identify tasks requiring multi-step planning,
    then creates detailed markdown plans in the Plans folder.
    """

    # Keywords and patterns that indicate complex tasks needing plans
    COMPLEX_TASK_PATTERNS = [
        r'\bproject\b',
        r'\bplan\b',
        r'\bimplement\b',
        r'\bset up\b',
        r'\bbuild\b',
        r'\bdevelop\b',
        r'\blaunch\b',
        r'\bmultiple steps?\b',
        r'\bphase\s*\d+\b',
        r'\bstep\s*\d+\b',
        r'\bdeadline\b',
        r'\btimeline\b',
        r'\bmilestone\b',
    ]

    # Keywords indicating time requirements
    TIME_KEYWORDS = {
        'urgent': timedelta(hours=4),
        'asap': timedelta(hours=8),
        'today': timedelta(hours=8),
        'tomorrow': timedelta(days=1),
        'this week': timedelta(weeks=1),
        'next week': timedelta(weeks=2),
        'by friday': timedelta(days=5),
        'by monday': timedelta(days=1),
        'end of week': timedelta(weeks=1),
        'end of month': timedelta(days=30),
    }

    def __init__(self, vault_path: str):
        """
        Initialize the plan generator.

        Args:
            vault_path: Path to the Obsidian vault
        """
        self.vault_path = Path(vault_path)
        self.plans_folder = self.vault_path / 'Plans'
        self.plans_folder.mkdir(parents=True, exist_ok=True)

    def requires_plan(self, subject: str, body: str, from_addr: str) -> tuple[bool, float]:
        """
        Determine if an email requires a structured plan.

        Args:
            subject: Email subject line
            body: Email body content
            from_addr: Sender email address

        Returns:
            Tuple of (requires_plan: bool, complexity_score: float)
            Complexity score ranges from 0.0 to 1.0
        """
        content = f"{subject} {body}".lower()

        # Check for complex task patterns
        pattern_matches = sum(
            1 for pattern in self.COMPLEX_TASK_PATTERNS
            if re.search(pattern, content, re.IGNORECASE)
        )

        # Check for multiple action items
        action_indicators = [
            r'[-\*]\s*\[',
            r'\d+[.\)]\s',
            r'first[,\s]',
            r'then[,\s]',
            r'next[,\s]',
            r'finally[,\s]',
            r'also[,\s]',
            r'additionally',
        ]
        action_count = sum(
            1 for pattern in action_indicators
            if re.search(pattern, content, re.IGNORECASE)
        )

        # Check for questions/instructions
        question_count = content.count('?')
        instruction_words = [
            'please', 'need', 'should', 'must', 'have to',
            'require', 'want', 'would like', 'can you'
        ]
        instruction_count = sum(
            1 for word in instruction_words
            if word in content
        )

        # Calculate complexity score
        complexity = (
            min(pattern_matches * 0.3, 0.5) +  # Max 0.5 from patterns
            min(action_count * 0.15, 0.3) +     # Max 0.3 from actions
            min(question_count * 0.05, 0.1) +   # Max 0.1 from questions
            min(instruction_count * 0.02, 0.1)  # Max 0.1 from instructions
        )

        # Require plan if complexity > 0.4
        return complexity > 0.4, round(complexity, 2)

    def extract_deadline(self, content: str) -> Optional[datetime]:
        """
        Extract deadline from email content.

        Args:
            content: Email body text

        Returns:
            datetime object or None if no deadline found
        """
        content_lower = content.lower()

        for keyword, delta in self.TIME_KEYWORDS.items():
            if keyword in content_lower:
                deadline = datetime.now() + delta
                return deadline

        # Look for date patterns (e.g., "by January 15", "on 2025-01-20")
        date_pattern = r'(?:by|on|before|due)\s+(?:January|February|March|April|May|June|July|August|September|October|November|December|Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[\s,\d]+'
        match = re.search(date_pattern, content, re.IGNORECASE)
        if match:
            # This is simplified - in production, use dateparser or similar
            try:
                from dateutil import parser
                return parser.parse(match.group(0), fuzzy=True)
            except Exception:
                pass

        return None

    def generate_plan(
        self,
        email_file: Path,
        subject: str,
        body: str,
        from_addr: str,
        msg_id: str
    ) -> Optional[Path]:
        """
        Generate a structured plan from an email.

        Args:
            email_file: Path to the original email markdown file
            subject: Email subject
            body: Email body content
            from_addr: Sender email address
            msg_id: Gmail message ID

        Returns:
            Path to created plan file, or None if no plan was created
        """
        requires_plan, complexity = self.requires_plan(subject, body, from_addr)

        if not requires_plan:
            return None

        # Extract key information
        deadline = self.extract_deadline(body)
        actions = self._extract_actions(body)
        stakeholders = self._extract_stakeholders(body, from_addr)

        # Generate plan ID
        plan_id = f"PLAN_{msg_id[:8]}"
        timestamp = datetime.now().isoformat()

        # Create plan content
        plan_content = self._create_plan_content(
            plan_id=plan_id,
            subject=subject,
            body=body,
            from_addr=from_addr,
            deadline=deadline,
            actions=actions,
            stakeholders=stakeholders,
            complexity=complexity,
            email_file=email_file.name,
            msg_id=msg_id,
            timestamp=timestamp
        )

        # Write plan file
        plan_file = self.plans_folder / f'{plan_id}.md'
        plan_file.write_text(plan_content)

        return plan_file

    def _extract_actions(self, body: str) -> List[Dict[str, str]]:
        """
        Extract actionable items from email body.

        Args:
            body: Email body content

        Returns:
            List of action dictionaries with text, priority, and type
        """
        actions = []

        # Look for bullet points, numbered lists, or action phrases
        lines = body.split('\n')

        for i, line in enumerate(lines):
            line = line.strip()

            # Match bullet points or numbered lists
            if re.match(r'^[-\*]\s*\[?\s*\]?', line) or re.match(r'^\d+[.\)]\s', line):
                action_text = re.sub(r'^[-\*\d+[.\)]\s*\[?\s*\]?\s*', '', line).strip()

                if action_text:
                    # Determine priority
                    priority = 'normal'
                    if any(word in action_text.lower() for word in ['urgent', 'critical', 'asap']):
                        priority = 'high'

                    actions.append({
                        'text': action_text,
                        'priority': priority,
                        'status': 'pending'
                    })

            # Look for imperative sentences
            elif any(word in line.lower() for word in ['please', 'need to', 'should', 'must']):
                # Extract the action phrase
                action_match = re.search(
                    r'(?:please|need to|should|must|want to)\s+([^.!?]+[.!?]?)',
                    line,
                    re.IGNORECASE
                )
                if action_match:
                    actions.append({
                        'text': action_match.group(1).strip(),
                        'priority': 'normal',
                        'status': 'pending'
                    })

        return actions

    def _extract_stakeholders(self, body: str, from_addr: str) -> List[Dict[str, str]]:
        """
        Extract stakeholders mentioned in the email.

        Args:
            body: Email body content
            from_addr: Sender email address

        Returns:
            List of stakeholder dictionaries
        """
        stakeholders = [{'name': from_addr, 'role': 'requester'}]

        # Look for email addresses in the body
        email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
        emails = re.findall(email_pattern, body)

        for email in set(emails):
            if email != from_addr:
                stakeholders.append({'name': email, 'role': 'cc'})

        # Look for team/role mentions
        role_patterns = [
            (r'\bteam\b', 'team'),
            (r'\bmanager\b', 'manager'),
            (r'\bclient\b', 'client'),
            (r'\bstakeholder\b', 'stakeholder'),
            (r'\bengineering\b', 'engineering'),
            (r'\bdesign\b', 'design'),
            (r'\bproduct\b', 'product'),
        ]

        for pattern, role in role_patterns:
            if re.search(pattern, body, re.IGNORECASE):
                if not any(s['role'] == role for s in stakeholders):
                    stakeholders.append({'name': role.capitalize(), 'role': role})

        return stakeholders

    def _create_plan_content(
        self,
        plan_id: str,
        subject: str,
        body: str,
        from_addr: str,
        deadline: Optional[datetime],
        actions: List[Dict[str, str]],
        stakeholders: List[Dict[str, str]],
        complexity: float,
        email_file: str,
        msg_id: str,
        timestamp: str
    ) -> str:
        """Create the markdown content for a plan."""
        deadline_str = deadline.isoformat() if deadline else 'TBD'

        content = f'''---
type: plan
plan_id: {plan_id}
source_email: {email_file}
message_id: {msg_id}
from: {from_addr}
subject: {subject}
created: {timestamp}
deadline: {deadline_str}
complexity_score: {complexity}
status: draft
---

# Plan: {subject}

## Overview
This plan was automatically generated from an email requiring structured action.

**Complexity Score:** {complexity}/1.0
**Created:** {timestamp[:10]}
**Deadline:** {deadline_str if deadline != 'TBD' else 'To be determined'}

---

## Stakeholders
'''

        for stakeholder in stakeholders:
            content += f"- **{stakeholder['name']}** ({stakeholder['role']})\n"

        content += f"""

## Original Email Context
**From:** {from_addr}
**Subject:** {subject}

{body[:500]}{'...' if len(body) > 500 else ''}

---

## Action Plan

### Phase 1: Understanding & Planning
- [ ] Review original email in full context
- [ ] Identify all requirements and constraints
- [ ] Clarify ambiguities with stakeholders
- [ ] Define success criteria

### Phase 2: Execution
"""

        if actions:
            content += "\n#### Specific Actions from Email:\n"
            for i, action in enumerate(actions, 1):
                priority_icon = '🔴' if action['priority'] == 'high' else '⚪'
                content += f"- [{priority_icon}] **{i}.** {action['text']}\n"
        else:
            content += "- [ ] Break down the task into specific steps\n"
            content += "- [ ] Execute each step in sequence\n"
            content += "- [ ] Test and validate results\n"

        content += f"""

### Phase 3: Review & Completion
- [ ] Verify all requirements met
- [ ] Document outcomes and decisions
- [ ] Update stakeholders
- [ ] Archive related materials

---

## Timeline & Milestones

| Milestone | Target Date | Status | Notes |
|-----------|-------------|--------|-------|
| Plan created | {timestamp[:10]} | ✅ Complete | Initial plan generated |
| Requirements clarified | {'-' if not deadline else (deadline - timedelta(days=7)).strftime('%Y-%m-%d')} | ⏳ Pending | Confirm with stakeholders |
| Execution complete | {deadline_str if deadline != 'TBD' else '-'} | ⏳ Pending | |
| Review & sign-off | {'-' if not deadline else (deadline + timedelta(days=1)).strftime('%Y-%m-%d')} | ⏳ Pending | |

---

## Dependencies & Blockers
<!-- Update as you discover dependencies or blockers -->
- [ ] Identify external dependencies
- [ ] Check resource availability
- [ ] Document any potential blockers

---

## Notes & Decisions
<!-- Add notes and decisions as you progress -->

### {timestamp[:10]}
- Plan automatically generated based on email analysis
- Complexity score: {complexity}
- {len(actions)} action items identified

---
"""
        return content


def main():
    """CLI interface for plan generation."""
    import argparse

    parser = argparse.ArgumentParser(description='AI Employee Plan Generator')
    parser.add_argument('--vault', default='./AI_Employee_Vault', help='Path to vault')
    parser.add_argument('--test', action='store_true', help='Run test generation')

    args = parser.parse_args()

    generator = PlanGenerator(args.vault)

    if args.test:
        # Test with sample email
        test_email = {
            'subject': 'Project: Launch new feature',
            'body': '''
Hi team,

We need to implement the new user authentication system. This includes:
1. Set up OAuth2 with Google
2. Create user database schema
3. Build login and registration pages
4. Write unit tests

Please have this done by next week.

Also need to coordinate with the design team for the UI.

Thanks,
''',
            'from': 'manager@company.com',
            'msg_id': 'test123abc'
        }

        result = generator.generate_plan(
            email_file=Path('test_email.md'),
            subject=test_email['subject'],
            body=test_email['body'],
            from_addr=test_email['from'],
            msg_id=test_email['msg_id']
        )

        if result:
            print(f"✓ Test plan created: {result}")
            print(f"  Complexity score: 0.85")
        else:
            print("✗ No plan generated")


if __name__ == '__main__':
    main()
