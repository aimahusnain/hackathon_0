"""
AI Employee Vault Update Skill

A skill for updating and managing .md files in the Obsidian vault.
Provides comprehensive operations for modifying vault content.

Usage:
    from skills.vault_update import VaultUpdater

    updater = VaultUpdater(vault_path="./AI_Employee_Vault")
    updater.update_task_status("EMAIL_abc123.md", "completed")
    updater.add_note("EMAIL_abc123.md", "Processed this email")
    updater.move_to_folder("EMAIL_abc123.md", "Done")
"""

import os
import re
import json
import shutil
import logging
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, List, Any, Union


class VaultUpdater:
    """
    A comprehensive skill for updating .md files in the Obsidian vault.

    Features:
    - Update frontmatter fields
    - Modify task status
    - Add notes and comments
    - Append/replace content
    - Move files between folders
    - Batch operations
    """

    def __init__(self, vault_path: str = None):
        """Initialize the vault updater.

        Args:
            vault_path: Path to the Obsidian vault. Defaults to ./AI_Employee_Vault
        """
        if vault_path is None:
            vault_path = Path(__file__).parent.parent / 'AI_Employee_Vault'

        self._vault_path = Path(vault_path)
        self._needs_action = self._vault_path / 'Needs_Action'
        self._done = self._vault_path / 'Done'
        self._inbox = self._vault_path / 'Inbox'
        self._approved = self._vault_path / 'Approved'
        self._rejected = self._vault_path / 'Rejected'
        self._plans = self._vault_path / 'Plans'
        self._logs = self._vault_path / 'Logs'
        self._logger = logging.getLogger('VaultUpdater')

        # Ensure folders exist
        for folder in [self._needs_action, self._done, self._inbox, self._approved, self._rejected, self._plans, self._logs]:
            folder.mkdir(parents=True, exist_ok=True)

    @property
    def vault_path(self) -> Path:
        """Get vault path (read-only)."""
        return self._vault_path

    @property
    def needs_action(self) -> Path:
        """Get Needs_Action folder path (read-only)."""
        return self._needs_action

    @property
    def done(self) -> Path:
        """Get Done folder path (read-only)."""
        return self._done

    @property
    def inbox(self) -> Path:
        """Get Inbox folder path (read-only)."""
        return self._inbox

    @property
    def approved(self) -> Path:
        """Get Approved folder path (read-only)."""
        return self._approved

    @property
    def rejected(self) -> Path:
        """Get Rejected folder path (read-only)."""
        return self._rejected

    @property
    def plans(self) -> Path:
        """Get Plans folder path (read-only)."""
        return self._plans

    @property
    def logs(self) -> Path:
        """Get Logs folder path (read-only)."""
        return self._logs

    def find_file(self, filename: str) -> Optional[Path]:
        """Find a file anywhere in the vault by name.

        Args:
            filename: Name of the file to find (can include partial name)

        Returns:
            Path to the file if found, None otherwise
        """
        # Try exact match first
        for folder in [self._needs_action, self._done, self._inbox, self._approved, self._rejected, self._plans]:
            path = folder / filename
            if path.exists():
                return path

        # Try partial match (search by pattern)
        for folder in [self._needs_action, self._done, self._inbox, self._approved, self._rejected, self._plans]:
            matches = list(folder.glob(f'*{filename}*'))
            if matches:
                return matches[0]

        return None

    def read_file(self, file_path: str) -> str:
        """Read the content of a markdown file.

        Args:
            file_path: Path or filename of the file to read

        Returns:
            File content as string
        """
        path = self._resolve_path(file_path)
        if not path or not path.exists():
            raise FileNotFoundError(f'File not found: {file_path}')
        return path.read_text(encoding='utf-8')

    def write_file(self, file_path: str, content: str) -> Path:
        """Write content to a markdown file.

        Args:
            file_path: Path where to write the file
            content: Content to write

        Returns:
            Path to the written file
        """
        path = self._resolve_path(file_path)
        if path is None:
            # Check if file_path includes a folder (e.g., "Plans/file.md")
            path_obj = Path(file_path)
            if len(path_obj.parts) > 1:
                # Has folder, use full path relative to vault
                path = self._vault_path / file_path
            else:
                # No folder specified, create in Needs_Action by default
                path = self._needs_action / path_obj.name

        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding='utf-8')
        return path

    def update_frontmatter(self, file_path: str, updates: Dict[str, Any]) -> bool:
        """Update frontmatter fields in a markdown file.

        Args:
            file_path: Path or filename of the file
            updates: Dictionary of field names and values to update

        Returns:
            True if successful, False otherwise

        Example:
            updater.update_frontmatter("EMAIL_abc123.md", {
                "status": "completed",
                "priority": "high",
                "completed_date": "2026-01-09T17:30:00"
            })
        """
        try:
            path = self._resolve_path(file_path)
            if not path or not path.exists():
                return False

            content = path.read_text(encoding='utf-8')

            # Extract and update frontmatter
            if content.startswith('---'):
                # Find end of frontmatter
                frontmatter_end = content.find('---', 3)
                if frontmatter_end == -1:
                    return False

                frontmatter = content[3:frontmatter_end]
                body = content[frontmatter_end + 3:]

                # Parse existing frontmatter
                frontmatter_dict = self._parse_frontmatter(frontmatter)

                # Update with new values
                frontmatter_dict.update(updates)

                # Rebuild frontmatter
                new_frontmatter = self._build_frontmatter(frontmatter_dict)
                new_content = f'---{new_frontmatter}---{body}'

                path.write_text(new_content, encoding='utf-8')
                return True
            else:
                # No frontmatter exists, add it
                frontmatter = self._build_frontmatter(updates)
                new_content = f'---{frontmatter}---{content}'
                path.write_text(new_content, encoding='utf-8')
                return True

        except Exception as e:
            self._logger.error(f'Error updating frontmatter: {e}')
            return False

    def _parse_frontmatter(self, frontmatter: str) -> Dict[str, Any]:
        """Parse YAML frontmatter into a dictionary."""
        result = {}
        for line in frontmatter.strip().split('\n'):
            if ':' in line:
                key, value = line.split(':', 1)
                result[key.strip()] = value.strip()
        return result

    def _build_frontmatter(self, data: Dict[str, Any]) -> str:
        """Build YAML frontmatter from a dictionary."""
        lines = []
        for key, value in data.items():
            lines.append(f'{key}: {value}')
        return '\n' + '\n'.join(lines) + '\n'

    def update_status(self, file_path: str, status: str) -> bool:
        """Update the status field in frontmatter.

        Args:
            file_path: Path or filename of the file
            status: New status (pending, in_progress, completed, etc.)

        Returns:
            True if successful, False otherwise
        """
        return self.update_frontmatter(file_path, {'status': status})

    def set_priority(self, file_path: str, priority: str) -> bool:
        """Update the priority field in frontmatter.

        Args:
            file_path: Path or filename of the file
            priority: New priority (low, normal, high, critical)

        Returns:
            True if successful, False otherwise
        """
        return self.update_frontmatter(file_path, {'priority': priority})

    def add_note(self, file_path: str, note: str, section: str = 'Processing Notes') -> bool:
        """Add a note to a specific section in the file.

        Args:
            file_path: Path or filename of the file
            note: Note text to add
            section: Section name to add note to (default: "Processing Notes")

        Returns:
            True if successful, False otherwise
        """
        try:
            path = self._resolve_path(file_path)
            if not path or not path.exists():
                return False

            content = path.read_text(encoding='utf-8')
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M')

            # Check if section exists
            section_pattern = f'## {section}'
            if section_pattern in content:
                # Append to existing section
                # Find the section and add note after it
                section_index = content.find(section_pattern)
                # Find the next section or end of file
                next_section = content.find('\n## ', section_index + len(section_pattern))

                if next_section == -1:
                    # No next section, append to end
                    new_content = content + f'\n- **{timestamp}**: {note}\n'
                else:
                    # Insert before next section
                    new_content = (
                        content[:next_section] +
                        f'\n- **{timestamp}**: {note}\n' +
                        content[next_section:]
                    )
            else:
                # Create new section at the end
                new_content = content + f'\n\n## {section}\n- **{timestamp}**: {note}\n'

            path.write_text(new_content, encoding='utf-8')
            return True

        except Exception as e:
            self._logger.error(f'Error adding note: {e}')
            return False

    def append_content(self, file_path: str, content: str) -> bool:
        """Append content to the end of a file.

        Args:
            file_path: Path or filename of the file
            content: Content to append

        Returns:
            True if successful, False otherwise
        """
        try:
            path = self._resolve_path(file_path)
            if not path or not path.exists():
                return False

            existing_content = path.read_text(encoding='utf-8')
            new_content = existing_content.rstrip() + '\n\n' + content + '\n'
            path.write_text(new_content, encoding='utf-8')
            return True

        except Exception as e:
            self._logger.error(f'Error appending content: {e}')
            return False

    def replace_section(self, file_path: str, section_title: str, new_content: str) -> bool:
        """Replace a section's content in a markdown file.

        Args:
            file_path: Path or filename of the file
            section_title: Title of the section to replace (without ##)
            new_content: New content for the section

        Returns:
            True if successful, False otherwise
        """
        try:
            path = self._resolve_path(file_path)
            if not path or not path.exists():
                return False

            content = path.read_text(encoding='utf-8')
            section_pattern = f'## {section_title}'

            if section_pattern not in content:
                return False

            # Find section start and end
            section_start = content.find(section_pattern)
            next_section = content.find('\n## ', section_start + len(section_pattern))

            if next_section == -1:
                # Section goes to end of file
                before_section = content[:section_start]
                new_file_content = before_section + f'## {section_title}\n{new_content}\n'
            else:
                before_section = content[:section_start]
                after_section = content[next_section:]
                new_file_content = before_section + f'## {section_title}\n{new_content}\n' + after_section

            path.write_text(new_file_content, encoding='utf-8')
            return True

        except Exception as e:
            self._logger.error(f'Error replacing section: {e}')
            return False

    def move_to_folder(self, file_path: str, target_folder: str) -> Optional[Path]:
        """Move a file to a different folder in the vault.

        Args:
            file_path: Path or filename of the file to move
            target_folder: Name of target folder (Done, Inbox, Plans, etc.)

        Returns:
            New path if successful, None otherwise
        """
        try:
            source_path = self._resolve_path(file_path)
            if not source_path or not source_path.exists():
                return None

            # Resolve target folder
            target_folder_path = self._vault_path / target_folder
            if not target_folder_path.exists():
                target_folder_path.mkdir(parents=True, exist_ok=True)

            # Move file
            dest_path = target_folder_path / source_path.name
            shutil.move(str(source_path), str(dest_path))
            return dest_path

        except Exception as e:
            self._logger.error(f'Error moving file: {e}')
            return None

    def mark_completed(self, file_path: str, add_completion_note: bool = True) -> bool:
        """Mark a task/email as completed and move to Done folder.

        Args:
            file_path: Path or filename of the file
            add_completion_note: Whether to add a completion timestamp note

        Returns:
            True if successful, False otherwise
        """
        try:
            # Update status
            self.update_status(file_path, 'completed')
            self.update_frontmatter(file_path, {
                'completed_date': datetime.now().isoformat()
            })

            if add_completion_note:
                self.add_note(
                    file_path,
                    f'Marked as completed',
                    'Completion Notes'
                )

            # Move to Done folder
            result = self.move_to_folder(file_path, 'Done')
            return result is not None

        except Exception as e:
            self._logger.error(f'Error marking completed: {e}')
            return False

    def add_tag(self, file_path: str, tag: str) -> bool:
        """Add a tag to a file (adds to frontmatter and content).

        Args:
            file_path: Path or filename of the file
            tag: Tag to add (with or without #)

        Returns:
            True if successful, False otherwise
        """
        try:
            # Ensure tag starts with #
            if not tag.startswith('#'):
                tag = f'#{tag}'

            path = self._resolve_path(file_path)
            if not path or not path.exists():
                return False

            content = path.read_text(encoding='utf-8')

            # Add tag to content (at the end before frontmatter ends or in body)
            if content.startswith('---'):
                # Add to frontmatter
                frontmatter_end = content.find('---', 3)
                if frontmatter_end != -1:
                    # Check if tags field exists
                    frontmatter = content[3:frontmatter_end]
                    if 'tags:' in frontmatter:
                        # Append to existing tags
                        frontmatter = re.sub(
                            r'(tags:\s*[^\n]*)',
                            rf'\1 {tag}',
                            frontmatter
                        )
                        new_content = (
                            '---' + frontmatter + '---' +
                            content[frontmatter_end + 3:]
                        )
                    else:
                        # Add new tags field
                        new_content = (
                            '---' + frontmatter +
                            f'\ntags: {tag}\n' +
                            '---' + content[frontmatter_end + 3:]
                        )
                    path.write_text(new_content, encoding='utf-8')
                    return True

            # Add to body if no frontmatter
            new_content = content.rstrip() + f'\n\n{tag}\n'
            path.write_text(new_content, encoding='utf-8')
            return True

        except Exception as e:
            self._logger.error(f'Error adding tag: {e}')
            return False

    def search_files(self, query: str, folder: str = None) -> List[Dict[str, Any]]:
        """Search for files matching a query.

        Args:
            query: Search query (searches in filename and content)
            folder: Specific folder to search (optional)

        Returns:
            List of matching files with metadata
        """
        results = []
        query_lower = query.lower()

        # Determine search path
        if folder:
            search_paths = [self._vault_path / folder]
        else:
            search_paths = [
                self._needs_action,
                self._done,
                self._inbox,
                self._pending_approval,
                self._plans
            ]

        for search_path in search_paths:
            if not search_path.exists():
                continue

            for md_file in search_path.glob('*.md'):
                try:
                    content = md_file.read_text(encoding='utf-8')

                    # Search in filename and content
                    if query_lower in md_file.stem.lower() or query_lower in content.lower():
                        # Extract metadata
                        metadata = self._extract_metadata(content)

                        results.append({
                            'path': str(md_file.relative_to(self._vault_path)),
                            'name': md_file.stem,
                            'folder': md_file.parent.name,
                            'metadata': metadata,
                            'snippet': content[:200] + '...' if len(content) > 200 else content
                        })

                except Exception:
                    continue

        return results

    def _extract_metadata(self, content: str) -> Dict[str, Any]:
        """Extract metadata from file content."""
        metadata = {}

        if content.startswith('---'):
            frontmatter_end = content.find('---', 3)
            if frontmatter_end != -1:
                frontmatter = content[3:frontmatter_end]
                metadata = self._parse_frontmatter(frontmatter)

        return metadata

    def _resolve_path(self, file_path: str) -> Optional[Path]:
        """Resolve a file path or filename to a full vault path."""
        path = Path(file_path)

        if path.is_absolute():
            return path if path.exists() else None

        # If path includes a folder, use it directly
        if len(path.parts) > 1:
            full_path = self._vault_path / path
            return full_path if full_path.exists() else None

        # Search in common folders
        for folder in [self._needs_action, self._done, self._inbox, self._pending_approval, self._plans]:
            potential = folder / path
            if potential.exists():
                return potential

        return None

    def batch_update(self, file_paths: List[str], updates: Dict[str, Any]) -> Dict[str, bool]:
        """Apply the same updates to multiple files.

        Args:
            file_paths: List of file paths or names
            updates: Dictionary of updates to apply (e.g., {'status': 'completed'})

        Returns:
            Dictionary mapping file paths to success status
        """
        results = {}
        for file_path in file_paths:
            if 'status' in updates:
                results[file_path] = self.update_status(file_path, updates['status'])
            elif 'priority' in updates:
                results[file_path] = self.set_priority(file_path, updates['priority'])
            else:
                results[file_path] = self.update_frontmatter(file_path, updates)
        return results

    def list_files(self, folder: str = None, status: str = None) -> List[Dict[str, Any]]:
        """List files in the vault with optional filtering.

        Args:
            folder: Specific folder to list (optional)
            status: Filter by status field in frontmatter (optional)

        Returns:
            List of files with metadata
        """
        results = []

        # Determine search path
        if folder:
            search_paths = [self._vault_path / folder]
        else:
            search_paths = [
                self._needs_action,
                self._done,
                self._inbox,
                self._pending_approval,
                self._plans
            ]

        for search_path in search_paths:
            if not search_path.exists():
                continue

            for md_file in search_path.glob('*.md'):
                try:
                    content = md_file.read_text(encoding='utf-8')
                    metadata = self._extract_metadata(content)

                    # Filter by status if specified
                    if status and metadata.get('status') != status:
                        continue

                    results.append({
                        'path': str(md_file.relative_to(self._vault_path)),
                        'name': md_file.stem,
                        'folder': md_file.parent.name,
                        'metadata': metadata
                    })

                except Exception:
                    continue

        return results

    def get_stats(self) -> Dict[str, Any]:
        """Get statistics about the vault.

        Returns:
            Dictionary with vault statistics
        """
        stats = {
            'total_files': 0,
            'folders': {},
            'by_status': {},
            'by_priority': {}
        }

        for folder_name in ['Needs_Action', 'Done', 'Inbox', 'Approved', 'Rejected', 'Plans', 'Logs']:
            folder_path = self._vault_path / folder_name
            if folder_path.exists():
                files = list(folder_path.glob('*.md'))
                stats['folders'][folder_name] = len(files)
                stats['total_files'] += len(files)

                # Count by status and priority
                for md_file in files:
                    try:
                        content = md_file.read_text(encoding='utf-8')
                        metadata = self._extract_metadata(content)

                        status = metadata.get('status', 'unknown')
                        priority = metadata.get('priority', 'unknown')

                        stats['by_status'][status] = stats['by_status'].get(status, 0) + 1
                        stats['by_priority'][priority] = stats['by_priority'].get(priority, 0) + 1
                    except Exception:
                        continue

        return stats


# CLI interface for standalone usage
def main():
    """Command-line interface for vault operations."""
    import argparse

    parser = argparse.ArgumentParser(description='AI Employee Vault Update Skill')
    parser.add_argument('command', choices=[
        'update-status', 'set-priority', 'add-note', 'move',
        'mark-completed', 'add-tag', 'search', 'list', 'stats'
    ], help='Command to execute')
    parser.add_argument('--vault', help='Path to vault')
    parser.add_argument('--file', help='File path or name')
    parser.add_argument('--folder', help='Target folder')
    parser.add_argument('--status', help='New status')
    parser.add_argument('--priority', help='New priority')
    parser.add_argument('--note', help='Note to add')
    parser.add_argument('--tag', help='Tag to add')
    parser.add_argument('--query', help='Search query')

    args = parser.parse_args()

    updater = VaultUpdater(args.vault)

    if args.command == 'update-status':
        if not args.file or not args.status:
            print('Error: --file and --status required')
            return
        result = updater.update_status(args.file, args.status)
        print(f'Status update: {"Success" if result else "Failed"}')

    elif args.command == 'set-priority':
        if not args.file or not args.priority:
            print('Error: --file and --priority required')
            return
        result = updater.set_priority(args.file, args.priority)
        print(f'Priority update: {"Success" if result else "Failed"}')

    elif args.command == 'add-note':
        if not args.file or not args.note:
            print('Error: --file and --note required')
            return
        result = updater.add_note(args.file, args.note)
        print(f'Note added: {"Success" if result else "Failed"}')

    elif args.command == 'move':
        if not args.file or not args.folder:
            print('Error: --file and --folder required')
            return
        result = updater.move_to_folder(args.file, args.folder)
        print(f'Moved to: {result}' if result else 'Failed')

    elif args.command == 'mark-completed':
        if not args.file:
            print('Error: --file required')
            return
        result = updater.mark_completed(args.file)
        print(f'Marked completed: {"Success" if result else "Failed"}')

    elif args.command == 'add-tag':
        if not args.file or not args.tag:
            print('Error: --file and --tag required')
            return
        result = updater.add_tag(args.file, args.tag)
        print(f'Tag added: {"Success" if result else "Failed"}')

    elif args.command == 'search':
        results = updater.search_files(args.query or '', args.folder)
        print(f'Found {len(results)} results:')
        for r in results:
            print(f"  - {r['folder']}/{r['name']}")

    elif args.command == 'list':
        results = updater.list_files(folder=args.folder)
        print(f'Total files: {len(results)}')
        for r in results:
            status = r['metadata'].get('status', 'N/A')
            print(f"  - [{status}] {r['folder']}/{r['name']}")

    elif args.command == 'stats':
        stats = updater.get_stats()
        print(json.dumps(stats, indent=2))


if __name__ == '__main__':
    main()