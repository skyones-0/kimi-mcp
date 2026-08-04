"""
Traceability Module for Kimi-PIMCP
Generates intelligent summaries of project activity without using LLM tokens.
Uses Git history, file analysis, and heuristics to create markdown reports.
"""

import os
import re
import json
import hashlib
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Optional, Set, Tuple, Any
from dataclasses import dataclass, asdict
from collections import defaultdict
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


@dataclass
class ChangeSummary:
    """Summary of a single change."""
    filepath: str
    change_type: str  # added, modified, deleted, renamed
    lines_added: int = 0
    lines_deleted: int = 0
    functions_changed: List[str] = None
    classes_changed: List[str] = None
    impact_score: float = 0.0  # 0-1 scale
    
    def __post_init__(self):
        if self.functions_changed is None:
            self.functions_changed = []
        if self.classes_changed is None:
            self.classes_changed = []


@dataclass
class SessionActivity:
    """Activity during a single session."""
    session_id: str
    start_time: datetime
    end_time: Optional[datetime] = None
    files_touched: Set[str] = None
    queries_made: List[str] = None
    changes: List[ChangeSummary] = None
    summary: str = ""
    
    def __post_init__(self):
        if self.files_touched is None:
            self.files_touched = set()
        if self.queries_made is None:
            self.queries_made = []
        if self.changes is None:
            self.changes = []


@dataclass
class DailyReport:
    """Report for a single day."""
    date: str
    commits: List[Dict] = None
    files_changed: List[str] = None
    additions: int = 0
    deletions: int = 0
    new_files: List[str] = None
    deleted_files: List[str] = None
    modified_files: List[str] = None
    key_changes: List[str] = None
    summary: str = ""
    
    def __post_init__(self):
        if self.commits is None:
            self.commits = []
        if self.files_changed is None:
            self.files_changed = []
        if self.new_files is None:
            self.new_files = []
        if self.deleted_files is None:
            self.deleted_files = []
        if self.modified_files is None:
            self.modified_files = []
        if self.key_changes is None:
            self.key_changes = []


class TraceabilityAnalyzer:
    """
    Analyzes project activity using Git and file analysis.
    No LLM tokens used - all analysis is rule-based and heuristic.
    """
    
    # Keywords for categorizing changes
    FEATURE_KEYWORDS = ['add', 'implement', 'create', 'new', 'feature', 'introduce']
    BUGFIX_KEYWORDS = ['fix', 'bug', 'issue', 'resolve', 'correct', 'patch']
    REFACTOR_KEYWORDS = ['refactor', 'clean', 'improve', 'optimize', 'restructure']
    TEST_KEYWORDS = ['test', 'spec', 'coverage', 'unit', 'e2e']
    DOCS_KEYWORDS = ['doc', 'readme', 'comment', 'changelog', 'license']
    CONFIG_KEYWORDS = ['config', 'setup', 'dependency', 'package', 'requirements']
    
    def __init__(self, project_path: str, reports_dir: Optional[str] = None):
        self.project_path = Path(project_path).resolve()
        self.reports_dir = Path(reports_dir) if reports_dir else self.project_path / '.kimi_pimcp' / 'traceability'
        self.reports_dir.mkdir(parents=True, exist_ok=True)
        
        # Import git integration
        try:
            from git_integration import GitIntegration
            self.git = GitIntegration(str(self.project_path))
        except ImportError:
            from .git_integration import GitIntegration
            self.git = GitIntegration(str(self.project_path))
        
        # Session tracking
        self.current_session: Optional[SessionActivity] = None
        self.sessions_file = self.reports_dir / 'sessions.json'
        
        # Load existing sessions
        self.sessions: List[SessionActivity] = self._load_sessions()
    
    def _load_sessions(self) -> List[SessionActivity]:
        """Load existing sessions from disk."""
        if not self.sessions_file.exists():
            return []
        
        try:
            with open(self.sessions_file, 'r') as f:
                data = json.load(f)
            
            sessions = []
            for item in data:
                session = SessionActivity(
                    session_id=item['session_id'],
                    start_time=datetime.fromisoformat(item['start_time']),
                    end_time=datetime.fromisoformat(item['end_time']) if item.get('end_time') else None,
                    files_touched=set(item.get('files_touched', [])),
                    queries_made=item.get('queries_made', []),
                    summary=item.get('summary', '')
                )
                sessions.append(session)
            
            return sessions
        except Exception as e:
            logger.warning(f"Error loading sessions: {e}")
            return []
    
    def _save_sessions(self):
        """Save sessions to disk."""
        try:
            data = []
            for session in self.sessions:
                data.append({
                    'session_id': session.session_id,
                    'start_time': session.start_time.isoformat(),
                    'end_time': session.end_time.isoformat() if session.end_time else None,
                    'files_touched': list(session.files_touched),
                    'queries_made': session.queries_made,
                    'summary': session.summary
                })
            
            with open(self.sessions_file, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.warning(f"Error saving sessions: {e}")
    
    def start_session(self) -> str:
        """Start a new tracing session."""
        session_id = hashlib.md5(f"{datetime.now().isoformat()}".encode()).hexdigest()[:12]
        
        self.current_session = SessionActivity(
            session_id=session_id,
            start_time=datetime.now()
        )
        
        logger.info(f"Started traceability session: {session_id}")
        return session_id
    
    def end_session(self, generate_summary: bool = True) -> Optional[str]:
        """End current session and optionally generate summary."""
        if not self.current_session:
            return None
        
        self.current_session.end_time = datetime.now()
        
        if generate_summary:
            self.current_session.summary = self._generate_session_summary(self.current_session)
        
        # Save session
        self.sessions.append(self.current_session)
        self._save_sessions()
        
        session_id = self.current_session.session_id
        logger.info(f"Ended traceability session: {session_id}")
        
        self.current_session = None
        return session_id
    
    def record_query(self, query: str):
        """Record a query made during the session."""
        if self.current_session:
            self.current_session.queries_made.append(query)
    
    def record_file_access(self, filepath: str):
        """Record a file being accessed."""
        if self.current_session:
            self.current_session.files_touched.add(filepath)
    
    def _generate_session_summary(self, session: SessionActivity) -> str:
        """Generate a summary for a session using heuristics."""
        duration = (session.end_time - session.start_time).total_seconds() / 60
        
        parts = []
        parts.append(f"## Session Summary ({session.session_id})")
        parts.append(f"**Duration:** {duration:.1f} minutes")
        parts.append(f"**Files touched:** {len(session.files_touched)}")
        parts.append(f"**Queries made:** {len(session.queries_made)}")
        
        if session.queries_made:
            parts.append("\n### Queries Made")
            for i, query in enumerate(session.queries_made[:10], 1):
                parts.append(f"{i}. {query}")
            if len(session.queries_made) > 10:
                parts.append(f"... and {len(session.queries_made) - 10} more")
        
        if session.files_touched:
            parts.append("\n### Files Accessed")
            for filepath in sorted(session.files_touched)[:15]:
                parts.append(f"- `{filepath}`")
            if len(session.files_touched) > 15:
                parts.append(f"... and {len(session.files_touched) - 15} more")
        
        return '\n'.join(parts)
    
    def analyze_commit_message(self, message: str) -> Dict[str, Any]:
        """Analyze a commit message to extract intent without using LLM."""
        message_lower = message.lower()
        
        # Detect change type based on keywords
        change_type = 'other'
        confidence = 0.5
        
        if any(kw in message_lower for kw in self.FEATURE_KEYWORDS):
            change_type = 'feature'
            confidence = 0.8
        elif any(kw in message_lower for kw in self.BUGFIX_KEYWORDS):
            change_type = 'bugfix'
            confidence = 0.8
        elif any(kw in message_lower for kw in self.REFACTOR_KEYWORDS):
            change_type = 'refactor'
            confidence = 0.7
        elif any(kw in message_lower for kw in self.TEST_KEYWORDS):
            change_type = 'test'
            confidence = 0.75
        elif any(kw in message_lower for kw in self.DOCS_KEYWORDS):
            change_type = 'docs'
            confidence = 0.75
        elif any(kw in message_lower for kw in self.CONFIG_KEYWORDS):
            change_type = 'config'
            confidence = 0.7
        
        # Extract scope (e.g., "feat(auth): ...")
        scope_match = re.search(r'\(([^)]+)\)', message)
        scope = scope_match.group(1) if scope_match else None
        
        # Extract issue references
        issue_refs = re.findall(r'#(\d+)', message)
        
        # Extract breaking change indicator
        is_breaking = 'breaking change' in message_lower or '!' in message
        
        return {
            'type': change_type,
            'confidence': confidence,
            'scope': scope,
            'issue_refs': issue_refs,
            'is_breaking': is_breaking,
            'summary': message.split('\n')[0][:80]
        }
    
    def get_commit_stats(self, commit_hash: str) -> Dict[str, Any]:
        """Get detailed stats for a commit."""
        if not self.git.is_git_repo():
            return {}
        
        import subprocess
        
        # Get stats
        result = subprocess.run(
            ['git', 'show', '--stat', '--format=', commit_hash],
            cwd=self.project_path,
            capture_output=True,
            text=True
        )
        
        if result.returncode != 0:
            return {}
        
        stats = {
            'files_changed': 0,
            'insertions': 0,
            'deletions': 0,
            'files': []
        }
        
        # Parse stat output
        for line in result.stdout.strip().split('\n'):
            if '|' in line:
                parts = line.split('|')
                if len(parts) == 2:
                    filepath = parts[0].strip()
                    changes = parts[1].strip()
                    
                    # Count changes
                    insertions = changes.count('+')
                    deletions = changes.count('-')
                    
                    stats['files'].append({
                        'path': filepath,
                        'changes': changes,
                        'insertions': insertions,
                        'deletions': deletions
                    })
                    stats['files_changed'] += 1
                    stats['insertions'] += insertions
                    stats['deletions'] += deletions
        
        return stats
    
    def get_daily_commits(self, date: Optional[str] = None) -> List[Dict]:
        """Get all commits for a specific date."""
        if not self.git.is_git_repo():
            return []
        
        import subprocess
        
        if date is None:
            date = datetime.now().strftime('%Y-%m-%d')
        
        # Get commits for the date
        result = subprocess.run(
            ['git', 'log', '--after', f'{date} 00:00', '--before', f'{date} 23:59',
             '--format=%H|%an|%ad|%s', '--date=short'],
            cwd=self.project_path,
            capture_output=True,
            text=True
        )
        
        if result.returncode != 0:
            return []
        
        commits = []
        for line in result.stdout.strip().split('\n'):
            if not line:
                continue
            
            parts = line.split('|', 3)
            if len(parts) >= 4:
                commit_hash = parts[0]
                analysis = self.analyze_commit_message(parts[3])
                stats = self.get_commit_stats(commit_hash)
                
                commits.append({
                    'hash': commit_hash[:8],
                    'author': parts[1],
                    'date': parts[2],
                    'message': parts[3],
                    'analysis': analysis,
                    'stats': stats
                })
        
        return commits
    
    def generate_daily_report(self, date: Optional[str] = None, save: bool = True) -> DailyReport:
        """Generate a daily report without using LLM tokens."""
        if date is None:
            date = datetime.now().strftime('%Y-%m-%d')
        
        report = DailyReport(date=date)
        
        # Get commits
        report.commits = self.get_daily_commits(date)
        
        # Aggregate stats
        all_files = set()
        type_counts = defaultdict(int)
        
        for commit in report.commits:
            stats = commit.get('stats', {})
            report.additions += stats.get('insertions', 0)
            report.deletions += stats.get('deletions', 0)
            
            for file_info in stats.get('files', []):
                filepath = file_info['path']
                all_files.add(filepath)
                
                # Categorize file
                if file_info.get('insertions', 0) > 0 and file_info.get('deletions', 0) == 0:
                    if filepath not in report.new_files:
                        report.new_files.append(filepath)
                elif file_info.get('deletions', 0) > 0 and file_info.get('insertions', 0) == 0:
                    if filepath not in report.deleted_files:
                        report.deleted_files.append(filepath)
                else:
                    if filepath not in report.modified_files:
                        report.modified_files.append(filepath)
            
            # Count change types
            change_type = commit.get('analysis', {}).get('type', 'other')
            type_counts[change_type] += 1
        
        report.files_changed = list(all_files)
        
        # Generate intelligent summary
        report.summary = self._generate_daily_summary(report, type_counts)
        
        # Generate key changes
        report.key_changes = self._extract_key_changes(report.commits)
        
        # Save if requested
        if save:
            self._save_daily_report(report)
        
        return report
    
    def _generate_daily_summary(self, report: DailyReport, type_counts: Dict) -> str:
        """Generate a human-readable summary without LLM."""
        parts = []
        
        # Activity level
        total_changes = report.additions + report.deletions
        if total_changes > 500:
            activity = "Very high activity"
        elif total_changes > 200:
            activity = "High activity"
        elif total_changes > 50:
            activity = "Moderate activity"
        else:
            activity = "Light activity"
        
        parts.append(f"{activity} with {len(report.commits)} commits")
        
        # Change types
        if type_counts:
            type_summary = []
            for change_type, count in sorted(type_counts.items(), key=lambda x: -x[1]):
                if count > 0:
                    type_summary.append(f"{count} {change_type}{'s' if count > 1 else ''}")
            if type_summary:
                parts.append(f"including {', '.join(type_summary)}")
        
        # File changes
        if report.new_files:
            parts.append(f"{len(report.new_files)} new files added")
        if report.deleted_files:
            parts.append(f"{len(report.deleted_files)} files removed")
        
        # Code changes
        parts.append(f"(+{report.additions}/-{report.deletions}) lines changed")
        
        return ". ".join(parts) + "."
    
    def _extract_key_changes(self, commits: List[Dict]) -> List[str]:
        """Extract key changes from commits."""
        key_changes = []
        
        for commit in commits:
            analysis = commit.get('analysis', {})
            message = commit['message']
            
            # Extract first line (summary)
            summary = message.split('\n')[0][:100]
            
            # Add emoji based on type
            emoji_map = {
                'feature': '✨',
                'bugfix': '🐛',
                'refactor': '♻️',
                'test': '🧪',
                'docs': '📚',
                'config': '⚙️',
                'other': '📝'
            }
            
            emoji = emoji_map.get(analysis.get('type', 'other'), '📝')
            key_changes.append(f"{emoji} {summary}")
        
        return key_changes
    
    def _save_daily_report(self, report: DailyReport):
        """Save daily report to disk."""
        filename = f"daily_report_{report.date}.md"
        filepath = self.reports_dir / filename
        
        content = self._format_daily_report_md(report)
        
        with open(filepath, 'w') as f:
            f.write(content)
        
        logger.info(f"Saved daily report: {filepath}")
    
    def _format_daily_report_md(self, report: DailyReport) -> str:
        """Format daily report as markdown."""
        lines = []
        
        # Header
        lines.append(f"# Daily Report - {report.date}")
        lines.append("")
        
        # Summary
        lines.append("## Summary")
        lines.append(report.summary)
        lines.append("")
        
        # Stats
        lines.append("## Statistics")
        lines.append(f"- **Commits:** {len(report.commits)}")
        lines.append(f"- **Files Changed:** {len(report.files_changed)}")
        lines.append(f"- **Additions:** +{report.additions}")
        lines.append(f"- **Deletions:** -{report.deletions}")
        lines.append("")
        
        # Key Changes
        if report.key_changes:
            lines.append("## Key Changes")
            for change in report.key_changes:
                lines.append(f"- {change}")
            lines.append("")
        
        # New Files
        if report.new_files:
            lines.append("### New Files")
            for filepath in report.new_files[:20]:
                lines.append(f"- `{filepath}`")
            if len(report.new_files) > 20:
                lines.append(f"- ... and {len(report.new_files) - 20} more")
            lines.append("")
        
        # Modified Files
        if report.modified_files:
            lines.append("### Modified Files")
            for filepath in report.modified_files[:20]:
                lines.append(f"- `{filepath}`")
            if len(report.modified_files) > 20:
                lines.append(f"- ... and {len(report.modified_files) - 20} more")
            lines.append("")
        
        # Deleted Files
        if report.deleted_files:
            lines.append("### Deleted Files")
            for filepath in report.deleted_files[:20]:
                lines.append(f"- `{filepath}`")
            if len(report.deleted_files) > 20:
                lines.append(f"- ... and {len(report.deleted_files) - 20} more")
            lines.append("")
        
        # Commits Detail
        if report.commits:
            lines.append("## Commits")
            for commit in report.commits:
                lines.append(f"### `{commit['hash']}` - {commit['message'][:60]}")
                lines.append(f"- **Author:** {commit['author']}")
                lines.append(f"- **Type:** {commit.get('analysis', {}).get('type', 'unknown')}")
                
                stats = commit.get('stats', {})
                if stats:
                    lines.append(f"- **Changes:** {stats.get('files_changed', 0)} files "
                               f"(+{stats.get('insertions', 0)}/-{stats.get('deletions', 0)})")
                lines.append("")
        
        # Footer
        lines.append("---")
        lines.append(f"*Generated by Kimi-PIMCP Traceability on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*")
        
        return '\n'.join(lines)
    
    def generate_weekly_report(self, week_start: Optional[str] = None, save: bool = True) -> str:
        """Generate a weekly summary report."""
        if week_start is None:
            # Get start of current week (Monday)
            today = datetime.now()
            monday = today - timedelta(days=today.weekday())
            week_start = monday.strftime('%Y-%m-%d')
        
        # Generate daily reports for the week
        week_dates = []
        start = datetime.strptime(week_start, '%Y-%m-%d')
        for i in range(7):
            date = (start + timedelta(days=i)).strftime('%Y-%m-%d')
            week_dates.append(date)
        
        daily_reports = []
        for date in week_dates:
            report = self.generate_daily_report(date, save=False)
            daily_reports.append(report)
        
        # Aggregate stats
        total_commits = sum(len(r.commits) for r in daily_reports)
        total_additions = sum(r.additions for r in daily_reports)
        total_deletions = sum(r.deletions for r in daily_reports)
        all_files = set()
        for r in daily_reports:
            all_files.update(r.files_changed)
        
        # Generate markdown
        lines = []
        lines.append(f"# Weekly Report - Week of {week_start}")
        lines.append("")
        lines.append("## Overview")
        lines.append(f"- **Total Commits:** {total_commits}")
        lines.append(f"- **Files Changed:** {len(all_files)}")
        lines.append(f"- **Total Additions:** +{total_additions}")
        lines.append(f"- **Total Deletions:** -{total_deletions}")
        lines.append(f"- **Net Change:** {total_additions - total_deletions:+d} lines")
        lines.append("")
        
        # Daily breakdown
        lines.append("## Daily Breakdown")
        lines.append("")
        for report in daily_reports:
            if report.commits:  # Only show days with activity
                lines.append(f"### {report.date}")
                lines.append(f"- Commits: {len(report.commits)}")
                lines.append(f"- Changes: (+{report.additions}/-{report.deletions})")
                if report.key_changes:
                    lines.append("- Highlights:")
                    for change in report.key_changes[:3]:
                        lines.append(f"  - {change}")
                lines.append("")
        
        # Top changed files
        file_change_counts = defaultdict(int)
        for r in daily_reports:
            for f in r.files_changed:
                file_change_counts[f] += 1
        
        if file_change_counts:
            lines.append("## Most Changed Files")
            top_files = sorted(file_change_counts.items(), key=lambda x: -x[1])[:10]
            for filepath, count in top_files:
                lines.append(f"- `{filepath}` ({count} changes)")
            lines.append("")
        
        # Footer
        lines.append("---")
        lines.append(f"*Generated by Kimi-PIMCP Traceability*")
        
        content = '\n'.join(lines)
        
        if save:
            filename = f"weekly_report_{week_start}.md"
            filepath = self.reports_dir / filename
            with open(filepath, 'w') as f:
                f.write(content)
            logger.info(f"Saved weekly report: {filepath}")
        
        return content
    
    def get_traceability_summary(self, days: int = 7) -> str:
        """Get a quick summary of recent activity."""
        lines = []
        lines.append("# Recent Activity Summary")
        lines.append("")
        
        # Get commits from last N days
        import subprocess
        
        result = subprocess.run(
            ['git', 'log', f'--since={days} days ago',
             '--format=%H|%an|%ad|%s', '--date=short'],
            cwd=self.project_path,
            capture_output=True,
            text=True
        )
        
        if result.returncode != 0:
            return "Unable to get git history."
        
        commits = []
        for line in result.stdout.strip().split('\n'):
            if not line:
                continue
            parts = line.split('|', 3)
            if len(parts) >= 4:
                analysis = self.analyze_commit_message(parts[3])
                commits.append({
                    'hash': parts[0][:8],
                    'author': parts[1],
                    'date': parts[2],
                    'message': parts[3],
                    'type': analysis['type']
                })
        
        # Group by date
        by_date = defaultdict(list)
        for c in commits:
            by_date[c['date']].append(c)
        
        lines.append(f"**Last {days} days:** {len(commits)} commits")
        lines.append("")
        
        for date in sorted(by_date.keys(), reverse=True):
            day_commits = by_date[date]
            lines.append(f"### {date} ({len(day_commits)} commits)")
            for c in day_commits[:5]:
                emoji = {
                    'feature': '✨', 'bugfix': '🐛', 'refactor': '♻️',
                    'test': '🧪', 'docs': '📚', 'config': '⚙️', 'other': '📝'
                }.get(c['type'], '📝')
                lines.append(f"- {emoji} `{c['hash']}` {c['message'][:50]}")
            if len(day_commits) > 5:
                lines.append(f"- ... and {len(day_commits) - 5} more")
            lines.append("")
        
        return '\n'.join(lines)
    
    def list_reports(self) -> List[str]:
        """List all generated reports."""
        reports = []
        for f in self.reports_dir.glob('*.md'):
            reports.append(str(f.name))
        return sorted(reports)
    
    def get_report(self, report_name: str) -> Optional[str]:
        """Get the content of a specific report."""
        filepath = self.reports_dir / report_name
        if filepath.exists():
            with open(filepath, 'r') as f:
                return f.read()
        return None
    
    def get_stats(self) -> Dict[str, Any]:
        """Get traceability statistics."""
        return {
            'reports_dir': str(self.reports_dir),
            'total_reports': len(self.list_reports()),
            'total_sessions': len(self.sessions),
            'current_session': self.current_session.session_id if self.current_session else None,
            'git_available': self.git.is_git_repo()
        }


# Singleton instance
traceability_instances: Dict[str, TraceabilityAnalyzer] = {}


def get_traceability(project_path: str) -> TraceabilityAnalyzer:
    """Get or create traceability analyzer for a project."""
    if project_path not in traceability_instances:
        traceability_instances[project_path] = TraceabilityAnalyzer(project_path)
    return traceability_instances[project_path]


if __name__ == '__main__':
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python traceability.py <project_path> [daily|weekly|summary]")
        sys.exit(1)
    
    project_path = sys.argv[1]
    command = sys.argv[2] if len(sys.argv) > 2 else 'daily'
    
    analyzer = TraceabilityAnalyzer(project_path)
    
    if command == 'daily':
        report = analyzer.generate_daily_report()
        print(f"Generated daily report: {analyzer.reports_dir}/daily_report_{report.date}.md")
    elif command == 'weekly':
        content = analyzer.generate_weekly_report()
        print(f"Generated weekly report in: {analyzer.reports_dir}/")
    elif command == 'summary':
        print(analyzer.get_traceability_summary())
    else:
        print(f"Unknown command: {command}")
