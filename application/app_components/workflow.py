"""
Workflow Manager
Manages GitHub workflow items (Issues and Pull Requests) from target and fork repositories
"""

import requests
from typing import List, Dict, Any, Optional, Tuple


class WorkflowItem:
    """Represents a GitHub workflow item (Issue or PR)"""

    def __init__(self, item_type: str, data: Dict[str, Any], repo_source: str):
        """
        Initialize a workflow item

        Args:
            item_type: 'issue' or 'pull_request'
            data: Raw data from GitHub API
            repo_source: 'target' or 'fork'
        """
        self.item_type = item_type
        self.repo_source = repo_source
        self.data = data

        # Extract common fields
        self.number = data.get('number')
        self.title = data.get('title', 'No Title')
        self.state = data.get('state', 'unknown')
        self.created_at = data.get('created_at', '')
        self.updated_at = data.get('updated_at', '')
        self.body = data.get('body', '')
        self.url = data.get('html_url', '')
        self.api_url = data.get('url', '')

        # Author information
        user = data.get('user', {})
        self.author = user.get('login', 'unknown') if user else 'unknown'
        self.author_url = user.get('html_url', '') if user else ''

        # Labels
        self.labels = [label.get('name', '') for label in data.get('labels', [])]

        # Assignees
        assignees = data.get('assignees', [])
        self.assignees = [a.get('login', '') for a in assignees if a]

        # PR-specific fields
        if item_type == 'pull_request':
            self.is_draft = data.get('draft', False)
            self.mergeable_state = data.get('mergeable_state', 'unknown')
            self.merged = data.get('merged', False)
            self.base_ref = data.get('base', {}).get('ref', '')
            self.head_ref = data.get('head', {}).get('ref', '')
        else:
            self.is_draft = False
            self.mergeable_state = None
            self.merged = False
            self.base_ref = None
            self.head_ref = None

        # Comments count
        self.comments_count = data.get('comments', 0)

    def __repr__(self):
        return f"<WorkflowItem {self.item_type} #{self.number}: {self.title[:50]}>"

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for easy serialization"""
        return {
            'item_type': self.item_type,
            'repo_source': self.repo_source,
            'data': self.data,  # Include raw data for full reconstruction
            'number': self.number,
            'title': self.title,
            'state': self.state,
            'created_at': self.created_at,
            'updated_at': self.updated_at,
            'body': self.body,
            'url': self.url,
            'api_url': self.api_url,
            'author': self.author,
            'author_url': self.author_url,
            'labels': self.labels,
            'assignees': self.assignees,
            'is_draft': self.is_draft,
            'mergeable_state': self.mergeable_state,
            'merged': self.merged,
            'base_ref': self.base_ref,
            'head_ref': self.head_ref,
            'comments_count': self.comments_count
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'WorkflowItem':
        """Create WorkflowItem from dictionary (for cache deserialization)"""
        # Extract the raw GitHub API data if available, otherwise use the dict itself
        raw_data = data.get('data', data)
        item_type = data.get('item_type', 'issue')
        repo_source = data.get('repo_source', 'target')

        return cls(item_type, raw_data, repo_source)


class GitHubRepoFetcher:
    """Fetches repository information from GitHub"""

    def __init__(self, github_token: str, logger=None):
        """
        Initialize the repo fetcher

        Args:
            github_token: GitHub Personal Access Token
            logger: Optional logger instance
        """
        self.token = github_token
        self.logger = logger
        self.headers = {
            "Authorization": f"Bearer {github_token}",
            "Accept": "application/vnd.github+json",
            "User-Agent": "github-automation-tool/1.0"
        }

    def log(self, message: str):
        """Log a message"""
        if self.logger:
            self.logger.log(message)
        else:
            print(message)

    def get_authenticated_user(self) -> Optional[Dict[str, Any]]:
        """
        Get information about the authenticated user

        Returns:
            Dictionary with user information or None if error
        """
        try:
            url = "https://api.github.com/user"
            response = requests.get(url, headers=self.headers, timeout=30)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            self.log(f"❌ Error fetching authenticated user: {str(e)}")
            return None

    def fetch_user_repos(self, repo_type: str = 'owner', per_page: int = 100) -> List[Dict[str, Any]]:
        """
        Fetch repositories for the authenticated user

        Args:
            repo_type: 'owner', 'member', or 'all'
            per_page: Number of repos per page (max 100)

        Returns:
            List of repository dictionaries
        """
        try:
            url = "https://api.github.com/user/repos"
            params = {
                'type': repo_type,
                'per_page': min(per_page, 100),
                'sort': 'updated',
                'direction': 'desc'
            }

            response = requests.get(url, headers=self.headers, params=params, timeout=30)
            response.raise_for_status()

            repos = response.json()
            self.log(f"✅ Found {len(repos)} repositories ({repo_type})")
            return repos

        except Exception as e:
            self.log(f"❌ Error fetching user repos: {str(e)}")
            return []

    def fetch_repos_with_permissions(self, min_permission: str = 'push') -> List[Dict[str, Any]]:
        """
        Fetch repositories where user has specific permissions

        Args:
            min_permission: Minimum permission level ('pull', 'push', 'admin')

        Returns:
            List of repository dictionaries with sufficient permissions
        """
        try:
            # Fetch all repos user has access to
            all_repos = self.fetch_user_repos(repo_type='all')

            # Filter by permission level
            filtered_repos = []
            permission_levels = {'pull': 0, 'push': 1, 'admin': 2}
            min_level = permission_levels.get(min_permission, 1)

            for repo in all_repos:
                permissions = repo.get('permissions', {})

                # Check permission level
                if permissions.get('admin'):
                    level = 2
                elif permissions.get('push'):
                    level = 1
                elif permissions.get('pull'):
                    level = 0
                else:
                    level = -1

                if level >= min_level:
                    filtered_repos.append(repo)

            self.log(f"✅ Found {len(filtered_repos)} repos with '{min_permission}' permission or higher")
            return filtered_repos

        except Exception as e:
            self.log(f"❌ Error fetching repos with permissions: {str(e)}")
            return []

    def search_repositories(self, query: str, per_page: int = 30) -> List[Dict[str, Any]]:
        """
        Search for repositories on GitHub

        Args:
            query: Search query string
            per_page: Number of results per page (max 100)

        Returns:
            List of repository dictionaries
        """
        if not query or not query.strip():
            return []

        try:
            url = "https://api.github.com/search/repositories"
            params = {
                'q': query.strip(),
                'per_page': min(per_page, 100),
                'sort': 'updated',
                'order': 'desc'
            }

            response = requests.get(url, headers=self.headers, params=params, timeout=30)
            response.raise_for_status()

            data = response.json()
            repos = data.get('items', [])
            total_count = data.get('total_count', 0)

            self.log(f"✅ Search found {total_count} repositories (showing {len(repos)})")
            return repos

        except Exception as e:
            self.log(f"❌ Error searching repositories: {str(e)}")
            return []

    def get_repo_names(self, repos: List[Dict[str, Any]]) -> List[str]:
        """
        Extract repository names in 'owner/repo' format

        Args:
            repos: List of repository dictionaries

        Returns:
            List of repository name strings
        """
        return [repo.get('full_name', '') for repo in repos if repo.get('full_name')]


class WorkflowManager:
    """Manages workflow items from GitHub repositories"""

    def __init__(self, github_token: str, logger=None):
        """
        Initialize the workflow manager

        Args:
            github_token: GitHub Personal Access Token
            logger: Optional logger instance
        """
        self.token = github_token
        self.logger = logger
        self.headers = {
            "Authorization": f"Bearer {github_token}",
            "Accept": "application/vnd.github+json",
            "User-Agent": "github-automation-tool/1.0"
        }
        # Initialize repo fetcher
        self.repo_fetcher = GitHubRepoFetcher(github_token, logger)

    def log(self, message: str):
        """Log a message"""
        if self.logger:
            self.logger.log(message)
        else:
            print(message)

    def _parse_repo(self, repo_str: str) -> Optional[Tuple[str, str]]:
        """
        Parse a repository string into owner and name

        Args:
            repo_str: Repository string in format "owner/repo"

        Returns:
            Tuple of (owner, repo) or None if invalid
        """
        if not repo_str or '/' not in repo_str:
            return None

        parts = repo_str.strip().split('/')
        if len(parts) != 2:
            return None

        return parts[0], parts[1]

    def fetch_issues(self, repo_str: str, repo_source: str = 'target',
                     state: str = 'all', per_page: int = 100) -> List[WorkflowItem]:
        """
        Fetch issues from a repository

        Args:
            repo_str: Repository string in format "owner/repo"
            repo_source: 'target' or 'fork' to identify source
            state: 'open', 'closed', or 'all'
            per_page: Number of items per page (max 100)

        Returns:
            List of WorkflowItem objects
        """
        parsed = self._parse_repo(repo_str)
        if not parsed:
            self.log(f"L Invalid repository format: {repo_str}")
            return []

        owner, repo = parsed
        self.log(f"Fetching issues from {owner}/{repo} ({repo_source})...")

        try:
            url = f"https://api.github.com/repos/{owner}/{repo}/issues"
            params = {
                'state': state,
                'per_page': min(per_page, 100),
                'sort': 'updated',
                'direction': 'desc'
            }

            response = requests.get(url, headers=self.headers, params=params, timeout=30)
            response.raise_for_status()

            items_data = response.json()

            # Filter out pull requests (GitHub's issues endpoint includes PRs)
            issues_data = [item for item in items_data if 'pull_request' not in item]

            issues = [WorkflowItem('issue', data, repo_source) for data in issues_data]

            self.log(f" Found {len(issues)} issues in {owner}/{repo}")
            return issues

        except requests.HTTPError as e:
            self.log(f"L HTTP Error fetching issues from {owner}/{repo}: {e}")
            if e.response.status_code == 401:
                self.log("   Check your GitHub Personal Access Token")
            elif e.response.status_code == 404:
                self.log("   Repository not found or no access")
            return []
        except Exception as e:
            self.log(f"L Error fetching issues from {owner}/{repo}: {str(e)}")
            return []

    def fetch_pull_requests(self, repo_str: str, repo_source: str = 'target',
                           state: str = 'all', per_page: int = 100) -> List[WorkflowItem]:
        """
        Fetch pull requests from a repository

        Args:
            repo_str: Repository string in format "owner/repo"
            repo_source: 'target' or 'fork' to identify source
            state: 'open', 'closed', or 'all'
            per_page: Number of items per page (max 100)

        Returns:
            List of WorkflowItem objects
        """
        parsed = self._parse_repo(repo_str)
        if not parsed:
            self.log(f"L Invalid repository format: {repo_str}")
            return []

        owner, repo = parsed
        self.log(f"Fetching pull requests from {owner}/{repo} ({repo_source})...")

        try:
            url = f"https://api.github.com/repos/{owner}/{repo}/pulls"
            params = {
                'state': state,
                'per_page': min(per_page, 100),
                'sort': 'updated',
                'direction': 'desc'
            }

            response = requests.get(url, headers=self.headers, params=params, timeout=30)
            response.raise_for_status()

            prs_data = response.json()
            prs = [WorkflowItem('pull_request', data, repo_source) for data in prs_data]

            self.log(f" Found {len(prs)} pull requests in {owner}/{repo}")
            return prs

        except requests.HTTPError as e:
            self.log(f"L HTTP Error fetching PRs from {owner}/{repo}: {e}")
            if e.response.status_code == 401:
                self.log("   Check your GitHub Personal Access Token")
            elif e.response.status_code == 404:
                self.log("   Repository not found or no access")
            return []
        except Exception as e:
            self.log(f"L Error fetching PRs from {owner}/{repo}: {str(e)}")
            return []

    def fetch_all_workflow_items(self, target_repo: str, fork_repo: str = None,
                                 include_issues: bool = True,
                                 include_prs: bool = True,
                                 state: str = 'all') -> Dict[str, List[WorkflowItem]]:
        """
        Fetch all workflow items from both target and fork repositories

        Args:
            target_repo: Target repository string "owner/repo"
            fork_repo: Fork repository string "owner/repo" (optional)
            include_issues: Whether to fetch issues
            include_prs: Whether to fetch pull requests
            state: 'open', 'closed', or 'all'

        Returns:
            Dictionary with keys 'target_issues', 'target_prs', 'fork_issues', 'fork_prs'
        """
        results = {
            'target_issues': [],
            'target_prs': [],
            'fork_issues': [],
            'fork_prs': []
        }

        # Fetch from target repository
        if target_repo:
            if include_issues:
                results['target_issues'] = self.fetch_issues(target_repo, 'target', state)
            if include_prs:
                results['target_prs'] = self.fetch_pull_requests(target_repo, 'target', state)

        # Fetch from fork repository
        if fork_repo:
            if include_issues:
                results['fork_issues'] = self.fetch_issues(fork_repo, 'fork', state)
            if include_prs:
                results['fork_prs'] = self.fetch_pull_requests(fork_repo, 'fork', state)

        # Log summary
        total = sum(len(items) for items in results.values())
        self.log(f"\n=� Summary: Fetched {total} total items")
        self.log(f"   Target Issues: {len(results['target_issues'])}")
        self.log(f"   Target PRs: {len(results['target_prs'])}")
        if fork_repo:
            self.log(f"   Fork Issues: {len(results['fork_issues'])}")
            self.log(f"   Fork PRs: {len(results['fork_prs'])}")

        return results

    def get_combined_items(self, workflow_items: Dict[str, List[WorkflowItem]],
                          sort_by: str = 'updated') -> List[WorkflowItem]:
        """
        Combine and sort all workflow items

        Args:
            workflow_items: Dictionary from fetch_all_workflow_items()
            sort_by: 'updated', 'created', or 'number'

        Returns:
            Sorted list of all workflow items
        """
        all_items = []
        for items_list in workflow_items.values():
            all_items.extend(items_list)

        # Sort items
        if sort_by == 'updated':
            all_items.sort(key=lambda x: x.updated_at, reverse=True)
        elif sort_by == 'created':
            all_items.sort(key=lambda x: x.created_at, reverse=True)
        elif sort_by == 'number':
            all_items.sort(key=lambda x: x.number, reverse=True)

        return all_items

    def filter_items(self, items: List[WorkflowItem], **filters) -> List[WorkflowItem]:
        """
        Filter workflow items based on criteria

        Args:
            items: List of WorkflowItem objects
            **filters: Filter criteria (state, item_type, repo_source, author, labels)

        Returns:
            Filtered list of items
        """
        filtered = items

        if 'state' in filters and filters['state']:
            filtered = [item for item in filtered if item.state == filters['state']]

        if 'item_type' in filters and filters['item_type']:
            filtered = [item for item in filtered if item.item_type == filters['item_type']]

        if 'repo_source' in filters and filters['repo_source']:
            filtered = [item for item in filtered if item.repo_source == filters['repo_source']]

        if 'author' in filters and filters['author']:
            filtered = [item for item in filtered if item.author == filters['author']]

        if 'labels' in filters and filters['labels']:
            label_filter = filters['labels']
            if isinstance(label_filter, str):
                label_filter = [label_filter]
            filtered = [item for item in filtered
                       if any(label in item.labels for label in label_filter)]

        return filtered

    def fetch_comments(self, repo_str: str, issue_number: int, is_pull_request: bool = False) -> List[Dict[str, Any]]:
        """
        Fetch comments for an issue or pull request

        Args:
            repo_str: Repository string in format "owner/repo"
            issue_number: Issue or PR number
            is_pull_request: Whether this is a pull request (for PR-specific comments)

        Returns:
            List of comment dictionaries with keys: 'user', 'body', 'created_at', 'updated_at'
        """
        try:
            # Parse repository string
            if '/' not in repo_str:
                self.log(f"Invalid repository format: {repo_str}")
                return []

            owner, repo = repo_str.split('/', 1)

            # Fetch issue/PR comments (these are the same endpoint for both issues and PRs)
            url = f"https://api.github.com/repos/{owner}/{repo}/issues/{issue_number}/comments"
            print(f"DEBUG: Fetching comments from URL: {url}", flush=True)

            response = requests.get(url, headers=self.headers)
            print(f"DEBUG: Response status code: {response.status_code}", flush=True)
            print(f"DEBUG: Response headers: {dict(response.headers)}", flush=True)
            print(f"DEBUG: Response text length: {len(response.text)}", flush=True)
            print(f"DEBUG: Response content (first 500): {response.text[:500]}", flush=True)

            response.raise_for_status()

            response_data = response.json()
            print(f"DEBUG: Response data type: {type(response_data)}", flush=True)
            print(f"DEBUG: Number of items: {len(response_data) if isinstance(response_data, list) else 'Not a list'}", flush=True)

            if isinstance(response_data, list) and len(response_data) > 0:
                print(f"DEBUG: First item keys: {list(response_data[0].keys())}", flush=True)

            comments = []
            for comment_data in response_data:
                comments.append({
                    'user': comment_data.get('user', {}).get('login', 'unknown'),
                    'body': comment_data.get('body', ''),
                    'created_at': comment_data.get('created_at', ''),
                    'updated_at': comment_data.get('updated_at', ''),
                    'url': comment_data.get('html_url', '')
                })

            self.log(f"Fetched {len(comments)} comments for {repo_str} #{issue_number}")
            print(f"DEBUG: Successfully parsed {len(comments)} comments", flush=True)
            return comments

        except requests.exceptions.RequestException as e:
            self.log(f"Error fetching comments for {repo_str} #{issue_number}: {e}")
            print(f"DEBUG: RequestException occurred: {e}", flush=True)
            import traceback
            traceback.print_exc()
            return []
        except Exception as e:
            self.log(f"Unexpected error fetching comments: {e}")
            print(f"DEBUG: Exception occurred: {e}", flush=True)
            import traceback
            traceback.print_exc()
            return []
