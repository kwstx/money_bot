from typing import Dict, Any, List
from datetime import datetime, timezone
from .schemas import TeamActivity

class TeamMonitor:
    """Monitors team communication, github activity, and project milestones."""
    
    def __init__(self, project_id: str):
        self.project_id = project_id
        
    def evaluate_github_activity(self, commits: List[Dict[str, Any]]) -> int:
        """
        Evaluates GitHub commits and returns the count of meaningful commits.
        Filters out automated repository changes, bot commits, or trivial updates
        like fixing typos in READMEs.
        """
        meaningful_count = 0
        
        for commit in commits:
            author = commit.get("author", "").lower()
            message = commit.get("message", "").lower()
            
            # Skip likely bots
            if "bot" in author or "dependabot" in author:
                continue
                
            # Skip automated/superficial changes
            superficial_keywords = [
                "update readme", "typo", "bump version", "automated release", 
                "merge branch", "update dependencies"
            ]
            
            if any(kw in message for kw in superficial_keywords):
                continue
                
            # If it passed filters, consider it meaningful
            meaningful_count += 1
            
        return meaningful_count
        
    def track_activity(self, 
                       communication_events: int,
                       days_active: float,
                       github_commits: List[Dict[str, Any]],
                       milestones_met: int,
                       partnerships: int) -> TeamActivity:
        """
        Aggregates team activity over a period and calculates authenticity.
        """
        freq = (communication_events / days_active) if days_active > 0 else 0.0
        
        meaningful_commits = self.evaluate_github_activity(github_commits)
        
        # Calculate authenticity score
        # High comms but zero code/milestones looks superficial
        authenticity = 1.0
        if freq > 5.0 and meaningful_commits == 0 and milestones_met == 0:
            authenticity = 0.2  # Likely just hype
        elif freq < 0.1 and meaningful_commits > 0:
            authenticity = 0.9  # Quiet but building
            
        # If huge number of commits but very few are meaningful, score goes down
        if len(github_commits) > 0:
            meaningful_ratio = meaningful_commits / len(github_commits)
            if meaningful_ratio < 0.1:
                authenticity -= 0.3
                
        authenticity = max(0.0, min(1.0, authenticity))
        
        return TeamActivity(
            project_id=self.project_id,
            communication_frequency=freq,
            meaningful_commit_count=meaningful_commits,
            roadmap_milestones_completed=milestones_met,
            partnerships_announced=partnerships,
            activity_authenticity_score=authenticity,
            timestamp=datetime.now(timezone.utc)
        )
