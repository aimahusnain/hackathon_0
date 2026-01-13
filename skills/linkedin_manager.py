"""
LinkedIn Manager Skill - Generate and post LinkedIn content

This skill provides functionality to:
- Generate LinkedIn posts from content
- Create post templates
- Schedule posts
- Log posts to vault

Usage:
    from skills.linkedin_manager import LinkedInManager

    manager = LinkedInManager(vault_path="./AI_Employee_Vault")
    manager.generate_post("We just launched a new feature!")
"""

import re
import json
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field

from skills.vault_update import VaultUpdater


@dataclass
class LinkedInPost:
    """A LinkedIn post."""
    post_id: str
    content: str
    post_type: str  # text, image, article, job, celebration
    hashtags: List[str]
    scheduled_time: Optional[str] = None
    status: str = "pending"  # pending, approved, posted, scheduled
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())


class LinkedInManager:
    """
    LinkedIn content manager and poster.

    Features:
    - Generate posts from templates
    - Create engaging content
    - Schedule posts
    - Log all posts to vault
    - Track performance
    """

    # Post templates
    TEMPLATES = {
        'announcement': """🚀 {headline}

{description}

Key Highlights:
{highlights}

{cta}

#{hashtags}""",

        'milestone': """🎉 Exciting News!

We're thrilled to share that {achievement}!

This milestone represents {significance}.

Thank you to everyone who made this possible!

Here's to the next chapter! 🥂

#{hashtags}""",

        'insight': """💡 {topic} - Key Insights

{insight_1}
{insight_2}
{insight_3}

What's your take on this? I'd love to hear your thoughts in the comments! 👇

#{hashtags}""",

        'job_opening': """🚀 We're Hiring!

Position: {role}
Location: {location}

We're looking for someone who is:
{requirements}

Why join us?
{benefits}

Interested? Apply here: {link}

#hiring #{role_type} #{hashtags}""",

        'project_launch': """🎯 New Project Launch!

{project_name} is now LIVE!

📊 What it does:
{description}

🎯 Who it's for:
{target_audience}

💡 Key features:
{features}

Check it out and let us know what you think!

#{hashtags}""",

        'event': """📅 Upcoming Event: {event_name}

📅 Date: {date}
📍 Location: {location}
🎯 Topic: {topic}

What you'll learn:
{takeaways}

{cta}

Register now: {link}

#{hashtags}""",

        'testimonial': """🗣️ Client Success Story

"{quote}" - {client_name}

{context}

Results:
{results}

Honored to have played a part in their success! 🙌

#{hashtags}"""
    }

    # Business-focused hashtags
    HASHTAG_SETS = {
        'general': ['#Business', '#Entrepreneurship', '#Innovation', '#Growth', '#Success'],
        'tech': ['#Technology', '#AI', '#MachineLearning', '#DigitalTransformation', '#TechTrends'],
        'startup': ['#Startup', '#Founders', '#VentureCapital', '#EntrepreneurLife', '#StartupLife'],
        'marketing': ['#Marketing', '#DigitalMarketing', '#SocialMedia', '#ContentMarketing', '#Branding'],
        'leadership': ['#Leadership', '#Management', '#TeamBuilding', '#OrganizationalCulture', '#GrowthMindset'],
        'productivity': ['#Productivity', '#TimeManagement', '#WorkSmarter', '#Efficiency', '#Goals']
    }

    def __init__(self, vault_path: str = None):
        """Initialize the LinkedIn manager.

        Args:
            vault_path: Path to the Obsidian vault
        """
        self._vault_path = Path(vault_path) if vault_path else Path("./AI_Employee_Vault")
        self._updater = VaultUpdater(str(self._vault_path))

        # LinkedIn posts folder
        self._posts_folder = self._vault_path / 'LinkedIn_Posts'
        self._posts_folder.mkdir(parents=True, exist_ok=True)

        # Analytics folder
        self._analytics_folder = self._vault_path / 'Logs' / 'LinkedIn_Analytics'
        self._analytics_folder.mkdir(parents=True, exist_ok=True)

    def generate_post(
        self,
        template_type: str,
        **kwargs
    ) -> LinkedInPost:
        """Generate a LinkedIn post from template.

        Args:
            template_type: Type of post (announcement, milestone, etc.)
            **kwargs: Template variables

        Returns:
            LinkedInPost object
        """
        if template_type not in self.TEMPLATES:
            raise ValueError(f"Unknown template type: {template_type}")

        # Get template
        template = self.TEMPLATES[template_type]

        # Build content
        content = template.format(**kwargs)

        # Add hashtags if not included
        if 'hashtags' not in kwargs:
            hashtags = self._get_default_hashtags(template_type)
            content += '\n' + ' '.join(hashtags)

        # Extract hashtags from content
        hashtags = re.findall(r'#(\w+)', content)

        post = LinkedInPost(
            post_id=f"LI_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            content=content,
            post_type=template_type,
            hashtags=hashtags
        )

        return post

    def _get_default_hashtags(self, post_type: str) -> List[str]:
        """Get default hashtags for post type."""
        mapping = {
            'announcement': self.HASHTAG_SETS['general'],
            'milestone': self.HASHTAG_SETS['general'],
            'insight': self.HASHTAG_SETS['general'],
            'job_opening': ['#Hiring', '#Career', '#JobOpening'],
            'project_launch': self.HASHTAG_SETS['tech'],
            'event': ['#Events', '#Networking'],
            'testimonial': ['#CustomerSuccess', '#ClientLove']
        }
        return mapping.get(post_type, self.HASHTAG_SETS['general'])

    def create_post_from_email(self, email_content: str, metadata: Dict) -> LinkedInPost:
        """Generate a LinkedIn post from email content.

        Args:
            email_content: Email body
            metadata: Email metadata

        Returns:
            LinkedInPost object
        """
        subject = metadata.get('subject', '').lower()
        content_lower = email_content.lower()

        # Detect post type
        if any(kw in subject for kw in ['launched', 'release', 'new feature']):
            post_type = 'announcement'
            kwargs = self._extract_announcement_details(email_content)
        elif any(kw in subject for kw in ['milestone', 'achieved', 'reached']):
            post_type = 'milestone'
            kwargs = self._extract_milestone_details(email_content)
        elif any(kw in subject for kw in ['hiring', 'job opening', 'we are hiring']):
            post_type = 'job_opening'
            kwargs = self._extract_job_details(email_content)
        else:
            post_type = 'insight'
            kwargs = self._extract_insight_details(email_content)

        return self.generate_post(post_type, **kwargs)

    def _extract_announcement_details(self, content: str) -> Dict[str, str]:
        """Extract details for announcement post."""
        lines = content.split('\n')
        headline = lines[0] if lines else "Exciting News!"
        description = '\n'.join(lines[1:4]) if len(lines) > 1 else "We have something special to share."

        # Extract bullet points as highlights
        highlights = []
        for line in lines:
            stripped = line.strip()
            if stripped.startswith('•') or stripped.startswith('-'):
                highlights.append(stripped)

        if not highlights:
            highlights = ["• Stay tuned for more details"]

        return {
            'headline': headline,
            'description': description,
            'highlights': '\n'.join(highlights[:5]),
            'cta': 'Learn more on our website!',
            'hashtags': ' '.join(self.HASHTAG_SETS['general'] + ['#Announcement'])
        }

    def _extract_milestone_details(self, content: str) -> Dict[str, str]:
        """Extract details for milestone post."""
        return {
            'achievement': 'We reached a significant milestone!',
            'significance': 'hard work, dedication, and teamwork',
            'hashtags': ' '.join(self.HASHTAG_SETS['general'] + ['#Milestone', '#Achievement'])
        }

    def _extract_job_details(self, content: str) -> Dict[str, str]:
        """Extract details for job opening post."""
        return {
            'role': 'Software Engineer',
            'location': 'Remote',
            'requirements': '• Passion for coding\n• Team player\n• Problem solver',
            'benefits': '• Competitive salary\n• Flexible hours\n• Growth opportunities',
            'link': 'https://example.com/apply',
            'role_type': 'TechJobs',
            'hashtags': 'Hiring Remote TechJobs'
        }

    def _extract_insight_details(self, content: str) -> Dict[str, str]:
        """Extract details for insight post."""
        lines = content.split('\n')

        # Get first meaningful line as topic
        topic = "Industry Insights"
        for line in lines:
            if len(line) > 20:
                topic = line[:50]
                break

        return {
            'topic': topic,
            'insight_1': '• Innovation drives growth',
            'insight_2': '• Customer focus is key',
            'insight_3': '• Continuous learning matters',
            'hashtags': ' '.join(self.HASHTAG_SETS['general'])
        }

    def save_post(self, post: LinkedInPost) -> str:
        """Save post to vault.

        Args:
            post: LinkedInPost object

        Returns:
            Relative path to saved post
        """
        filename = f"{post.post_id}.md"
        filepath = self._posts_folder / filename

        content = f"""---
type: linkedin_post
post_id: {post.post_id}
post_type: {post.post_type}
status: {post.status}
created: {post.created_at}
scheduled: {post.scheduled_time or 'N/A'}
hashtags: {', '.join(post.hashtags)}
---

# LinkedIn Post: {post.post_type.replace('_', ' ').title()}

**Status:** {post.status.upper()}
**Created:** {datetime.fromisoformat(post.created_at).strftime('%Y-%m-%d %H:%M')}
**Type:** {post.post_type}

---

## Post Content

{post.content}

---

## Hashtags

{', '.join(post.hashtags)}

---

## Actions

- [ ] Review post
- [ ] Edit if needed
- [ ] Move to `/Approved` to schedule/post
- [ ] Move to `/Posted` after posting

---

## Approval Workflow

To approve this post for LinkedIn:
1. Review content above
2. Make any edits
3. Move this file to: `AI_Employee_Vault/Approved/LinkedIn_{post.post_id}.md`
4. The poster will pick it up and post to LinkedIn

---

*Generated by AI Employee LinkedIn Manager*
"""

        filepath.write_text(content, encoding='utf-8')

        # Also save as draft in Updater
        self._updater.write_file(f"LinkedIn_Posts/{filename}", content)

        return str(filepath.relative_to(self._vault_path))

    def generate_and_save_post(
        self,
        template_type: str,
        **kwargs
    ) -> str:
        """Generate and save a post in one step.

        Args:
            template_type: Type of post
            **kwargs: Template variables

        Returns:
            Path to saved post
        """
        post = self.generate_post(template_type, **kwargs)
        return self.save_post(post)

    def list_posts(self, status: str = None) -> List[Dict[str, Any]]:
        """List LinkedIn posts.

        Args:
            status: Filter by status (optional)

        Returns:
            List of post metadata
        """
        posts = []

        for post_file in self._posts_folder.glob('LI_*.md'):
            try:
                content = post_file.read_text(encoding='utf-8')

                # Extract frontmatter
                metadata = {}
                if content.startswith('---'):
                    frontmatter_end = content.find('---', 3)
                    if frontmatter_end != -1:
                        frontmatter = content[3:frontmatter_end]
                        for line in frontmatter.strip().split('\n'):
                            if ':' in line:
                                key, value = line.split(':', 1)
                                metadata[key.strip()] = value.strip()

                # Apply status filter
                if status and metadata.get('status') != status:
                    continue

                posts.append({
                    'file': post_file.name,
                    'metadata': metadata
                })
            except Exception:
                continue

        return posts

    def get_post_templates(self) -> Dict[str, str]:
        """Get available post templates."""
        return self.TEMPLATES.copy()


# ============ SKILL FUNCTIONS ============

def create_linkedin_post(
    template_type: str,
    **kwargs
) -> str:
    """Skill function: Create a LinkedIn post from template.

    Args:
        template_type: Type of post (announcement, milestone, insight, etc.)
        **kwargs: Template variables

    Returns:
        Path to saved post
    """
    manager = LinkedInManager()
    path = manager.generate_and_save_post(template_type, **kwargs)
    return f"✅ LinkedIn post created: {path}"


def post_from_email(email_file: str = None) -> str:
    """Skill function: Generate LinkedIn post from recent email.

    Args:
        email_file: Specific email file (optional, uses most recent if not provided)

    Returns:
        Summary of created post
    """
    manager = LinkedInManager()
    vault_path = Path("./AI_Employee_Vault")
    needs_action = vault_path / 'Needs_Action'

    # Find recent email
    if email_file:
        email_path = needs_action / email_file
    else:
        emails = list(needs_action.glob('EMAIL_*.md'))
        if not emails:
            return "❌ No emails found in Needs_Action"
        email_path = sorted(emails, key=lambda x: x.stat().st_mtime, reverse=True)[0]

    try:
        content = email_path.read_text(encoding='utf-8')

        # Extract metadata
        metadata = {}
        if content.startswith('---'):
            frontmatter_end = content.find('---', 3)
            if frontmatter_end != -1:
                frontmatter = content[3:frontmatter_end]
                for line in frontmatter.strip().split('\n'):
                    if ':' in line:
                        key, value = line.split(':', 1)
                        metadata[key.strip()] = value.strip()

        # Generate post
        post = manager.create_post_from_email(content, metadata)
        path = manager.save_post(post)

        return f"✅ LinkedIn post generated from email: {path}\nType: {post.post_type}"

    except Exception as e:
        return f"❌ Error: {e}"


def list_linkedin_posts(status: str = None) -> str:
    """Skill function: List LinkedIn posts.

    Args:
        status: Filter by status (pending, approved, posted)

    Returns:
        Formatted list of posts
    """
    manager = LinkedInManager()
    posts = manager.list_posts(status)

    if not posts:
        return f"📝 No LinkedIn posts found (status: {status or 'all'})"

    output = f"📝 LinkedIn Posts ({len(posts)})\n\n"

    for post in posts:
        metadata = post['metadata']
        status = metadata.get('status', 'unknown').upper()
        post_type = metadata.get('post_type', 'unknown')
        created = metadata.get('created', 'Unknown')

        output += f"- **{post['file']}**\n"
        output += f"  Type: {post_type}\n"
        output += f"  Status: {status}\n"
        output += f"  Created: {created}\n\n"

    return output


def show_post_templates() -> str:
    """Skill function: Show available LinkedIn post templates."""
    manager = LinkedInManager()
    templates = manager.get_post_templates()

    output = "📋 Available LinkedIn Post Templates\n\n"

    for name, template in templates.items():
        output += f"## {name.replace('_', ' ').title()}\n"
        output += f"```\n{template[:200]}...\n```\n\n"

    return output


__all__ = [
    'LinkedInManager',
    'create_linkedin_post',
    'post_from_email',
    'list_linkedin_posts',
    'show_post_templates'
]
