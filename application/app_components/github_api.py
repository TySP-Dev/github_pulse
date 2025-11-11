"""
GitHub API Manager
Handles GitHub GraphQL operations, PR/Issue creation, and Copilot interactions
"""

import base64
import difflib
import json
import requests
from typing import Optional, Tuple, Dict, Any, List
from urllib.parse import urlparse

# Constants
GITHUB_GRAPHQL_ENDPOINT = "https://api.github.com/graphql"
USER_AGENT = "azure-devops-github-processor/2.0"


class GitHubGQL:
    """GitHub GraphQL API client for creating issues, PRs, and managing assignments"""
    
    def __init__(self, token: str, logger=None, dry_run: bool = False):
        self.token = token
        self.logger = logger
        self.dry_run = dry_run
    
    def log(self, message: str) -> None:
        """Log a message"""
        if self.logger:
            self.logger.log(message)
        else:
            print(message)

    def _headers(self):
        """Get headers for GitHub API requests"""
        return {
            "Authorization": f"Bearer {self.token}",
            "User-Agent": USER_AGENT,
            "Content-Type": "application/json"
        }
    
    def run(self, query: str, variables: dict | None = None) -> dict:
        """Execute a GraphQL query"""
        payload = {"query": query, "variables": variables or {}}
        
        if self.dry_run:
            self.log("[DRY-RUN] Would POST GraphQL payload:")
            pretty = json.dumps(payload, indent=2)
            self.log(pretty)
            return {"dryRun": True, "data": None}

        try:
            resp = requests.post(GITHUB_GRAPHQL_ENDPOINT, headers=self._headers(), json=payload, timeout=60)
            if resp.status_code != 200:
                raise RuntimeError(f"GraphQL HTTP {resp.status_code}: {resp.text}")
            
            data = resp.json()
            if "errors" in data and data["errors"]:
                raise RuntimeError(f"GraphQL errors: {json.dumps(data['errors'], indent=2)}")
            
            return data
        except requests.RequestException as e:
            raise RuntimeError(f"Request failed: {str(e)}")
    
    def _make_rest_request(self, method: str, url: str, data: Dict[str, Any] = None) -> Dict[str, Any]:
        """Make a REST API request to GitHub"""
        headers = {
            "Authorization": f"Bearer {self.token}",
            "Accept": "application/vnd.github+json",
            "User-Agent": USER_AGENT
        }
        
        if self.dry_run:
            self.log(f"[DRY-RUN] Would make {method} request to: {url}")
            return {"number": 123, "html_url": "https://github.com/example/repo/pull/123"}
        
        response = requests.request(method, url, headers=headers, json=data, timeout=30)
        response.raise_for_status()
        
        return response.json()
    
    def get_repo_id(self, owner: str, name: str) -> str:
        """Get GitHub repository ID"""
        self.log(f"Fetching repositoryId for {owner}/{name}...")
        query = """
        query($owner:String!, $name:String!) {
          repository(owner:$owner, name:$name) {
            id
            url
          }
        }
        """
        data = self.run(query, {"owner": owner, "name": name})
        
        if data.get("dryRun"):
            return "DRY_RUN_REPO_ID"
            
        repo = data["data"]["repository"]
        if not repo:
            raise RuntimeError(f"Repository {owner}/{name} not found or token lacks access.")
            
        self.log(f"Repository ID: {repo['id']} ({repo['url']})")
        return repo["id"]
    
    def get_copilot_actor_id(self, owner: str, name: str) -> tuple[str | None, str | None]:
        """Find Copilot actor ID for assignment"""
        self.log("Querying suggestedActors for CAN_BE_ASSIGNED...")
        query = """
        query($owner:String!, $name:String!) {
          repository(owner:$owner, name:$name) {
            suggestedActors(capabilities:[CAN_BE_ASSIGNED], first:100) {
              nodes {
                login
                __typename
                ... on Bot { id }
                ... on User { id }
              }
            }
          }
        }
        """
        data = self.run(query, {"owner": owner, "name": name})
        
        if data.get("dryRun"):
            return ("DRY_RUN_ACTOR_ID", "copilot-swe-agent")

        nodes = data["data"]["repository"]["suggestedActors"]["nodes"]
        if not nodes:
            self.log("No suggestedActors returned.")
            return (None, None)

        # Log all available actors for debugging
        self.log(f"Available assignable actors ({len(nodes)}):")
        for node in nodes:
            self.log(f"  - {node.get('login', 'N/A')} ({node.get('__typename', 'N/A')}) ID: {node.get('id', 'N/A')}")

        # Prefer known Copilot logins
        preferred = ("copilot-swe-agent", "copilot", "github-copilot", "github-advanced-security")
        chosen = None
        
        # First, try exact matches
        for candidate in nodes:
            login = candidate.get("login", "").lower()
            if login in preferred:
                chosen = candidate
                break
        
        # If no exact match, try partial matches
        if not chosen:
            for candidate in nodes:
                login = candidate.get("login", "").lower()
                if "copilot" in login:
                    chosen = candidate
                    break
        
        if not chosen:
            self.log("Copilot not found in suggestedActors list.")
            self.log("Available actors: " + ", ".join([n.get("login", "N/A") for n in nodes]))
            return (None, None)

        login = chosen["login"]
        actor_id = chosen.get("id")
        
        if not actor_id:
            self.log(f"Warning: No actor ID found for {login}")
            return (None, None)
            
        self.log(f"Found assignable Copilot actor: {login} (id={actor_id})")
        return (actor_id, login)
    
    def create_issue(self, repository_id: str, title: str, body: str) -> tuple[str, str, int]:
        """Create a GitHub issue"""
        self.log("Creating issue with createIssue mutation...")
        mutation = """
        mutation($repositoryId:ID!, $title:String!, $body:String!) {
          createIssue(input:{repositoryId:$repositoryId, title:$title, body:$body}) {
            issue {
              id
              url
              number
              title
            }
          }
        }
        """
        data = self.run(mutation, {"repositoryId": repository_id, "title": title, "body": body})
        
        if data.get("dryRun"):
            return ("DRY_RUN_ISSUE_ID", "https://github.com/owner/repo/issues/123", 123)
            
        issue = data["data"]["createIssue"]["issue"]
        self.log(f"Issue created: {issue['url']} (#{issue['number']})")
        return (issue["id"], issue["url"], issue["number"])
    
    def create_branch_from_main(self, owner: str, repo: str, branch_name: str) -> bool:
        """Create a new branch from the main branch"""
        self.log(f"Creating branch '{branch_name}' in {owner}/{repo}")
        
        try:
            # Get the SHA of the main branch
            main_ref_url = f"https://api.github.com/repos/{owner}/{repo}/git/ref/heads/main"
            main_ref_response = self._make_rest_request("GET", main_ref_url)
            main_sha = main_ref_response["object"]["sha"]
            
            self.log(f"Main branch SHA: {main_sha}")
            
            # Create new branch
            new_ref_url = f"https://api.github.com/repos/{owner}/{repo}/git/refs"
            new_ref_data = {
                "ref": f"refs/heads/{branch_name}",
                "sha": main_sha
            }
            
            if self.dry_run:
                self.log(f"🧪 DRY RUN: Would create branch '{branch_name}' from main ({main_sha})")
                return True
            
            self._make_rest_request("POST", new_ref_url, new_ref_data)
            self.log(f"✅ Branch '{branch_name}' created successfully")
            return True
            
        except Exception as e:
            self.log(f"❌ Failed to create branch: {str(e)}")
            return False
    
    def get_user_forks(self, include_org_repos: bool = True) -> List[str]:
        """Get list of user's forked repositories"""
        self.log("Fetching user's forked repositories...")
        
        if self.dry_run:
            # Return sample data for dry run
            return [
                "username/fabric-docs",
                "username/azure-docs", 
                "username/powerbi-docs"
            ]
        
        try:
            forks = []
            page = 1
            per_page = 100
            
            while page <= 5:  # Limit to 5 pages to avoid long waits
                url = f"https://api.github.com/user/repos?type=forks&per_page={per_page}&page={page}"
                
                response = self._make_rest_request("GET", url)
                repos = response if isinstance(response, list) else response.get('data', [])
                
                if not repos:
                    break
                
                for repo in repos:
                    if repo.get('fork', False):
                        forks.append(f"{repo['owner']['login']}/{repo['name']}")
                
                if len(repos) < per_page:
                    break
                    
                page += 1
            
            self.log(f"Found {len(forks)} forked repositories")
            return forks
            
        except Exception as e:
            self.log(f"❌ Failed to fetch user forks: {str(e)}")
            return []
    
    def get_authenticated_user(self) -> Dict[str, Any]:
        """Get authenticated user information"""
        if self.dry_run:
            return {"login": "dry-run-user", "name": "Dry Run User"}
        
        try:
            return self._make_rest_request("GET", "https://api.github.com/user")
        except Exception as e:
            self.log(f"❌ Failed to get user info: {str(e)}")
            return {}
    
    def fork_repository(self, owner: str, repo: str, target_org: str = None) -> tuple[str, str]:
        """Fork a repository to the authenticated user's account or specified organization"""
        self.log(f"Forking repository {owner}/{repo}")
        
        fork_url = f"https://api.github.com/repos/{owner}/{repo}/forks"
        fork_data = {}
        
        if target_org:
            fork_data["organization"] = target_org
        
        if self.dry_run:
            # Get authenticated user for dry run
            user_url = "https://api.github.com/user"
            try:
                user_data = self._make_rest_request("GET", user_url)
                fork_owner = target_org if target_org else user_data["login"]
                self.log(f"🧪 DRY RUN: Would fork {owner}/{repo} to {fork_owner}/{repo}")
                return fork_owner, repo
            except:
                self.log(f"🧪 DRY RUN: Would fork {owner}/{repo}")
                return "dry-run-user", repo
        
        try:
            fork_response = self._make_rest_request("POST", fork_url, fork_data)
            fork_owner = fork_response["owner"]["login"]
            fork_name = fork_response["name"]
            
            self.log(f"✅ Repository forked to {fork_owner}/{fork_name}")
            return fork_owner, fork_name
            
        except Exception as e:
            self.log(f"❌ Failed to fork repository: {str(e)}")
            raise

    def check_repository_exists(self, owner: str, repo: str) -> bool:
        """Check if a repository exists and is accessible"""
        try:
            url = f"https://api.github.com/repos/{owner}/{repo}"
            response = self._make_rest_request("GET", url)
            return bool(response.get('id'))
        except:
            return False
    
    def find_matching_repositories(self, target_repo: str, fork_repo: str) -> Dict[str, List[str]]:
        """Find matching repositories to suggest alternatives for mismatched repos"""
        self.log(f"Finding matching repositories for target: {target_repo}, fork: {fork_repo}")
        
        if self.dry_run:
            return {
                "target_alternatives": ["microsoftdocs/fabric-docs-pr"],
                "fork_alternatives": ["b-tsammons/azure-docs-pr"]
            }
        
        try:
            target_owner, target_name = target_repo.split('/', 1) if '/' in target_repo else ("", target_repo)
            fork_owner, fork_name = fork_repo.split('/', 1) if '/' in fork_repo else ("", fork_repo)
            
            target_alternatives = []
            fork_alternatives = []
            
            # Get authenticated user info
            user_info = self.get_authenticated_user()
            user_login = user_info.get('login', '')
            
            # Search for repositories with similar names
            search_terms = [target_name, fork_name]
            for term in search_terms:
                if term:
                    # Clean up the search term (remove common suffixes)
                    clean_term = term.replace('-docs', '').replace('-pr', '').replace('_', ' ')
                    
                    # Search for repositories
                    search_url = f"https://api.github.com/search/repositories?q={clean_term}&per_page=20"
                    try:
                        search_response = self._make_rest_request("GET", search_url)
                        repositories = search_response.get('items', [])
                        
                        for repo_data in repositories:
                            repo_full_name = repo_data['full_name']
                            repo_owner = repo_data['owner']['login']
                            
                            # Check if this is a potential target alternative
                            if (repo_owner == target_owner and 
                                repo_data['name'] != target_name and
                                repo_full_name not in target_alternatives):
                                target_alternatives.append(repo_full_name)
                            
                            # Check if this is a potential fork alternative  
                            if (repo_owner == user_login and 
                                repo_data['name'] != fork_name and
                                repo_data.get('fork', False) and
                                repo_full_name not in fork_alternatives):
                                fork_alternatives.append(repo_full_name)
                                
                    except Exception as e:
                        self.log(f"❌ Search failed for term '{term}': {str(e)}")
            
            return {
                "target_alternatives": target_alternatives[:5],  # Limit to 5 suggestions
                "fork_alternatives": fork_alternatives[:5]
            }
            
        except Exception as e:
            self.log(f"❌ Failed to find matching repositories: {str(e)}")
            return {"target_alternatives": [], "fork_alternatives": []}
    
    def make_documentation_change(self, owner: str, repo: str, branch_name: str, file_path: str,
                                   old_text: str, new_text: str, commit_message: str) -> bool:
        """Make actual documentation changes to a file in the repository

        This fetches the file, makes the text replacement, and commits it to the branch.

        Returns True if successful, False otherwise.
        """
        if self.dry_run:
            self.log(f"[DRY-RUN] Would update {file_path} in branch {branch_name}")
            self.log(f"[DRY-RUN] Replace: {old_text[:50]}...")
            self.log(f"[DRY-RUN] With: {new_text[:50]}...")
            return True

        try:
            rest_headers = {
                "Authorization": f"Bearer {self.token}",
                "Accept": "application/vnd.github+json",
                "User-Agent": USER_AGENT
            }

            # 1. Get the current file content from the branch
            self.log(f"Fetching file: {file_path}")
            file_url = f"https://api.github.com/repos/{owner}/{repo}/contents/{file_path}?ref={branch_name}"
            resp = requests.get(file_url, headers=rest_headers, timeout=30)

            if resp.status_code == 404:
                self.log(f"❌ File not found: {file_path}")
                self.log(f"   The file path might be incorrect or the file doesn't exist")
                return False

            resp.raise_for_status()
            file_data = resp.json()

            # Decode the file content
            current_content = base64.b64decode(file_data["content"]).decode('utf-8')
            file_sha = file_data["sha"]

            self.log(f"✅ File retrieved ({len(current_content)} bytes)")

            # Detect line ending style to preserve it
            line_ending = '\r\n' if '\r\n' in current_content else '\n'
            self.log(f"📝 Detected line endings: {'CRLF' if line_ending == '\\r\\n' else 'LF'}")

            # Normalize everything to LF for consistent processing
            normalized_content = current_content.replace('\r\n', '\n')
            normalized_old = old_text.replace('\r\n', '\n')
            normalized_new = new_text.replace('\r\n', '\n')

            # 2. Make the text replacement
            if normalized_old not in normalized_content:
                self.log(f"⚠️ Warning: Could not find exact text to replace in {file_path}")
                self.log(f"   Searching for similar text...")

                # Try to find similar text (case-insensitive, whitespace-flexible)
                lines = normalized_content.split('\n')
                old_lines = normalized_old.split('\n')

                # Find the best matching sequence
                matcher = difflib.SequenceMatcher(None, old_lines, lines)
                match = matcher.find_longest_match(0, len(old_lines), 0, len(lines))

                if match.size > len(old_lines) * 0.7:  # If we find 70% match
                    self.log(f"   Found similar text at line {match.b + 1}")
                    self.log(f"   Making best-effort replacement...")
                    # This is a simplified approach - in production you'd want more sophisticated matching
                else:
                    self.log(f"❌ Could not find text to replace. The document may have changed.")
                    self.log(f"   Creating PR with instructions instead...")
                    return False

            # Replace the text (using normalized versions)
            updated_content = normalized_content.replace(normalized_old, normalized_new)

            if updated_content == normalized_content:
                self.log(f"⚠️ No changes made - text might not exist in file")
                return False

            self.log(f"✅ Text replacement successful")

            # Restore original line endings
            if line_ending == '\r\n':
                updated_content = updated_content.replace('\n', '\r\n')
                self.log(f"✅ Restored CRLF line endings")

            # 3. Commit the updated file
            self.log(f"Committing changes to {file_path}...")
            encoded_content = base64.b64encode(updated_content.encode('utf-8')).decode()

            update_payload = {
                "message": commit_message,
                "content": encoded_content,
                "sha": file_sha,
                "branch": branch_name
            }

            update_url = f"https://api.github.com/repos/{owner}/{repo}/contents/{file_path}"
            resp = requests.put(update_url, headers=rest_headers, json=update_payload, timeout=30)
            resp.raise_for_status()

            self.log(f"✅ Changes committed to branch {branch_name}")
            return True

        except requests.HTTPError as e:
            self.log(f"❌ HTTP Error making changes: {e}")
            if e.response.status_code == 403:
                self.log("   Permission denied - token doesn't have write access")
            elif e.response.status_code == 404:
                self.log(f"   File not found: {file_path}")
            return False
        except Exception as e:
            self.log(f"❌ Error making changes: {str(e)}")
            return False
    
    def create_cross_repo_pull_request(self, source_owner: str, source_repo: str, target_owner: str, target_repo: str,
                                      title: str, body: str, head_ref: str, base_ref: str = "main") -> tuple[str, str, int]:
        """Create a pull request from source repo to target repo"""
        self.log(f"Creating cross-repository PR from {source_owner}/{source_repo}:{head_ref} to {target_owner}/{target_repo}:{base_ref}")
        
        # Get target repository ID
        target_repo_id = self.get_repo_id(target_owner, target_repo)
        
        # Format the head reference for cross-repo PR
        head_ref_full = f"{source_owner}:{head_ref}"
        
        mutation = """
        mutation($repositoryId:ID!, $title:String!, $body:String!, $headRefName:String!, $baseRefName:String!) {
          createPullRequest(input:{
            repositoryId:$repositoryId,
            title:$title,
            body:$body,
            headRefName:$headRefName,
            baseRefName:$baseRefName
          }) {
            pullRequest {
              id
              url
              number
            }
          }
        }
        """
        
        variables = {
            "repositoryId": target_repo_id,
            "title": title,
            "body": body,
            "headRefName": head_ref_full,
            "baseRefName": base_ref
        }
        
        if self.dry_run:
            self.log(f"🧪 DRY RUN: Would create cross-repo PR '{title}' from {head_ref_full} to {base_ref}")
            return "dry-run-pr-id", f"https://github.com/{target_owner}/{target_repo}/pull/0", 0

        try:
            data = self.run(mutation, variables)
            pr_data = data["data"]["createPullRequest"]["pullRequest"]
            
            pr_id = pr_data["id"]
            pr_url = pr_data["url"]
            pr_number = pr_data["number"]
            
            self.log(f"✅ Cross-repo pull request created: {pr_url}")
            return pr_id, pr_url, pr_number
            
        except Exception as e:
            self.log(f"❌ Failed to create cross-repo pull request: {str(e)}")
            raise
    
    def create_pull_request(self, repository_id: str, title: str, body: str, head_ref: str, base_ref: str = "main") -> tuple[str, str, int]:
        """Create a pull request with AB# linking"""
        self.log(f"Creating pull request with createPullRequest mutation from {head_ref} to {base_ref}...")
        mutation = """
        mutation($repositoryId:ID!, $title:String!, $body:String!, $headRefName:String!, $baseRefName:String!) {
          createPullRequest(input:{
            repositoryId:$repositoryId, 
            title:$title, 
            body:$body, 
            headRefName:$headRefName, 
            baseRefName:$baseRefName
          }) {
            pullRequest {
              id
              url
              number
              title
            }
          }
        }
        """
        variables = {
            "repositoryId": repository_id,
            "title": title,
            "body": body,
            "headRefName": head_ref,
            "baseRefName": base_ref
        }
        data = self.run(mutation, variables)
        if data.get("dryRun"):
            return ("DRY_RUN_PR_ID", "https://github.com/owner/repo/pull/456", 456)
        pr = data["data"]["createPullRequest"]["pullRequest"]
        self.log(f"Pull request created: {pr['url']} (#{pr['number']})")
        return (pr["id"], pr["url"], pr["number"])
    
    def assign_to_copilot(self, assignable_id: str, actor_ids: list[str]) -> bool:
        """Assign issue to Copilot

        Returns True if successful, False otherwise.
        """
        self.log("Assigning with replaceActorsForAssignable mutation...")
        mutation = """
        mutation($assignableId:ID!, $actorIds:[ID!]!) {
          replaceActorsForAssignable(input:{assignableId:$assignableId, actorIds:$actorIds}) {
            assignable {
              ... on Issue {
                id
                title
                assignees(first:10) { nodes { login } }
                url
              }
              ... on PullRequest {
                id
                title
                assignees(first:10) { nodes { login } }
                url
              }
            }
          }
        }
        """
        try:
            data = self.run(mutation, {"assignableId": assignable_id, "actorIds": actor_ids})

            if data.get("dryRun"):
                self.log("[DRY-RUN] Would have assigned Copilot.")
                return True

            assigned = data["data"]["replaceActorsForAssignable"]["assignable"]["assignees"]["nodes"]
            assignees = ", ".join([n["login"] for n in assigned]) or "(none)"
            self.log(f"Current assignees: {assignees}")
            return True
        except Exception as e:
            error_message = str(e)
            self.log(f"Error assigning Copilot: {error_message}")
            
            # Provide specific guidance for common permission issues
            if "FORBIDDEN" in error_message and "ReplaceActorsForAssignable" in error_message:
                self.log("")
                self.log("📋 Permission Issue: Cannot assign GitHub Copilot")
                self.log("   This is a repository permission limitation, not an application error.")
                self.log("")
                self.log("   Possible solutions:")
                self.log("   1. Repository admin can assign Copilot manually to the PR")
                self.log("   2. Repository admin can grant assignment permissions")
                self.log("   3. The @copilot comment will still notify Copilot to work on the PR")
                self.log("")
                self.log("   ✅ The PR was created successfully with @copilot instructions")
                self.log("   ✅ Copilot can still see and act on the @copilot comment")
            elif "NOT_FOUND" in error_message:
                self.log("")
                self.log("📋 Copilot Actor Not Found")
                self.log("   This repository may not have GitHub Copilot enabled or available.")
                self.log("   The @copilot comment was still added to notify available Copilot services.")
            
            return False
    
    def add_copilot_comment(self, owner: str, repo: str, pr_number: int,
                            file_path: str, old_text: str, new_text: str, branch_name: str,
                            work_item_id: str = None, item_source: str = None, doc_url: str = None, 
                            custom_instructions: str = None) -> bool:
        """Add a comment mentioning @copilot with explicit instructions to work on THIS PR

        This tells Copilot to make changes in the current PR's branch, not create a new PR.

        Args:
            owner: Repository owner
            repo: Repository name
            pr_number: Pull request number
            file_path: Path to the file to modify
            old_text: Text to find and replace
            new_text: New text to replace with
            branch_name: Branch name for this PR
            work_item_id: Work item or UUF issue ID
            item_source: Source of the item ('UUF' or 'Azure DevOps')

        Returns True if successful, False otherwise.
        """
        if self.dry_run:
            self.log(f"[DRY-RUN] Would add @copilot comment to PR #{pr_number}")
            return True

        try:
            rest_headers = {
                "Authorization": f"Bearer {self.token}",
                "Accept": "application/vnd.github+json",
                "User-Agent": USER_AGENT
            }

            # Build work item reference
            if work_item_id:
                if item_source == 'UUF':
                    work_item_ref = f"**UUF Issue:** {work_item_id}\n"
                else:
                    work_item_ref = f"**Azure DevOps Work Item:** AB#{work_item_id}\n"
            else:
                work_item_ref = ""

            # Build document reference
            if file_path and not file_path.startswith("See work item") and not file_path.startswith("File path not specified"):
                doc_ref = f"**Document to modify:** `{file_path}`\n"
                file_instruction = f"2. Locate the file: `{file_path}`"
            elif doc_url:
                doc_ref = f"**Document URL:** {doc_url}\n"
                file_instruction = f"2. Locate the file from this document URL: {doc_url}"
            else:
                doc_ref = "**Note:** File path not specified in work item\n"
                file_instruction = "2. Review the PR description and work item details to identify the file(s) that need to be modified"

            # Build custom instructions section
            if custom_instructions and custom_instructions.strip():
                custom_instructions_section = f"""
**Custom AI Instructions:**
{custom_instructions.strip()}

"""
            else:
                custom_instructions_section = ""

            # Create a comment mentioning @copilot with VERY explicit instructions
            comment_body = f"""@copilot

{work_item_ref}{doc_ref}

**Instructions:**

Task: Update the documentation file with the changes requested above.

Steps to complete:

Locate the file containing the reference shown below.
Find the reference text within the file
Replace it with the 'Proposed New Text' shown above or use the reference as guidance
Maintain the existing formatting, indentation, and markdown structure
Ensure no other content in the file is modified

> [!IMPORTANT]
> Only replace the specified text - do not make additional changes.
> Preserve all markdown formatting, links, and code blocks.
> If the current text cannot be found exactly, search for similar text.
> Please ensure the changes align with Microsoft documentation standards.
> Do not remove any text unless the reference or suggested guidance indicates to do so, if the text is obsolete or incorrect.

1. Make changes to `{branch_name}` branch for this pull request.

{file_instruction}

3. Find this reference in the content:
```
{old_text}
```

4. Use this text as guidance for the new content:
```
{new_text}
```

5. Ensure the changes align with the context of the work item.

6. Do a freshness check to ensure the file content is up-to-date before making changes.

7. Commit the changes to the `{branch_name}` branch

> [!NOTE]
> This documentation is maintained by spelluru.
> If guidance is empty, follow the reference to make changes.

{custom_instructions_section}
Thank you!
"""

            # Post the comment to the PR
            comments_url = f"https://api.github.com/repos/{owner}/{repo}/issues/{pr_number}/comments"
            comment_data = {"body": comment_body}

            resp = requests.post(comments_url, headers=rest_headers, json=comment_data, timeout=30)

            if resp.status_code == 403:
                self.log("❌ Permission denied when adding comment")
                return False

            resp.raise_for_status()
            self.log(f"✅ Added @copilot comment to PR #{pr_number}")
            self.log("   Copilot has been instructed to work on THIS PR's branch")
            return True

        except requests.HTTPError as e:
            self.log(f"❌ HTTP Error adding comment: {e}")
            return False
        except Exception as e:
            self.log(f"❌ Error adding comment: {str(e)}")
            return False

    def add_pr_suggestion(self, owner: str, repo: str, pr_number: int, file_path: str,
                          old_text: str, new_text: str) -> bool:
        """Add a suggested change comment to a PR

        This creates a review comment with a code suggestion that can be applied
        with one click, keeping everything in the same PR.

        Returns True if successful, False otherwise.
        """
        if self.dry_run:
            self.log(f"[DRY-RUN] Would add suggested change to PR #{pr_number}")
            return True

        try:
            # Use REST API to create a review comment with suggestion
            rest_headers = {
                "Authorization": f"Bearer {self.token}",
                "Accept": "application/vnd.github+json",
                "User-Agent": USER_AGENT
            }

            # First, get the latest commit SHA from the PR
            pr_url = f"https://api.github.com/repos/{owner}/{repo}/pulls/{pr_number}"
            resp = requests.get(pr_url, headers=rest_headers, timeout=30)
            resp.raise_for_status()
            pr_data = resp.json()
            commit_sha = pr_data["head"]["sha"]

            self.log(f"Latest commit SHA: {commit_sha}")

            # Get the file content to find line numbers
            file_url = f"https://api.github.com/repos/{owner}/{repo}/contents/{file_path}?ref={commit_sha}"
            resp = requests.get(file_url, headers=rest_headers, timeout=30)

            if resp.status_code == 404:
                self.log(f"⚠️ File not found in PR: {file_path}")
                return False

            resp.raise_for_status()
            file_data = resp.json()

            content = base64.b64decode(file_data["content"]).decode('utf-8')
            lines = content.split('\n')

            # Find the line number where the old text appears
            old_text_lines = old_text.split('\n')
            start_line = None

            for i in range(len(lines) - len(old_text_lines) + 1):
                if '\n'.join(lines[i:i+len(old_text_lines)]) == old_text:
                    start_line = i + 1  # Line numbers are 1-based
                    break

            if not start_line:
                self.log("⚠️ Could not find text in file to create suggestion")
                return False

            end_line = start_line + len(old_text_lines) - 1

            # Create a review comment with suggested change
            suggestion_body = f"""```suggestion
{new_text}
```

**Automated Suggestion:** This change was requested in Azure DevOps work item.

Click "Commit suggestion" above to apply this change directly to the PR."""

            comment_data = {
                "body": suggestion_body,
                "commit_id": commit_sha,
                "path": file_path,
                "line": end_line,
                "start_line": start_line if start_line != end_line else None,
                "start_side": "RIGHT"
            }

            # Remove start_line if it's the same as line (single-line comment)
            if start_line == end_line:
                del comment_data["start_line"]

            comments_url = f"https://api.github.com/repos/{owner}/{repo}/pulls/{pr_number}/comments"
            resp = requests.post(comments_url, headers=rest_headers, json=comment_data, timeout=30)

            if resp.status_code == 403:
                self.log("❌ Permission denied when adding suggestion")
                return False

            resp.raise_for_status()
            self.log(f"✅ Added suggested change comment to PR #{pr_number}")
            self.log("   User can click 'Commit suggestion' to apply it")
            return True

        except requests.HTTPError as e:
            self.log(f"❌ HTTP Error adding suggestion: {e}")
            if hasattr(e, 'response') and e.response is not None:
                self.log(f"   Response: {e.response.text[:200]}")
            return False
        except Exception as e:
            self.log(f"❌ Error adding suggestion: {str(e)}")
            return False

    def create_branch_with_placeholder(self, owner: str, repo: str, branch_name: str, instructions: str) -> bool:
        """Create a branch with a placeholder commit using REST API

        This creates a branch from main and adds a .copilot-instructions.md file
        so that the branch has at least one commit, allowing PR creation.

        Returns True if successful, False otherwise.
        """
        if self.dry_run:
            self.log(f"[DRY-RUN] Would create branch {branch_name} with placeholder commit")
            return True

        try:
            # Use REST API for branch/file creation
            rest_headers = {
                "Authorization": f"Bearer {self.token}",
                "Accept": "application/vnd.github+json",
                "User-Agent": USER_AGENT
            }

            # 1. Get the SHA of the main branch
            self.log(f"Getting SHA of main branch...")
            ref_url = f"https://api.github.com/repos/{owner}/{repo}/git/refs/heads/main"
            resp = requests.get(ref_url, headers=rest_headers, timeout=30)
            resp.raise_for_status()
            main_sha = resp.json()["object"]["sha"]
            self.log(f"Main branch SHA: {main_sha}")

            # 2. Create new branch from main
            self.log(f"Creating branch {branch_name}...")
            create_ref_url = f"https://api.github.com/repos/{owner}/{repo}/git/refs"
            create_ref_payload = {
                "ref": f"refs/heads/{branch_name}",
                "sha": main_sha
            }
            resp = requests.post(create_ref_url, headers=rest_headers, json=create_ref_payload, timeout=30)

            # Check for permission errors
            if resp.status_code == 403:
                self.log("❌ Permission denied: GitHub token doesn't have write access to this repository")
                self.log(f"   Repository: {owner}/{repo}")
                self.log("   Required permission: 'repo' scope with write access")
                self.log("")
                self.log("   Please verify:")
                self.log("   1. Your token has the 'repo' scope enabled")
                self.log("   2. You have write/push access to this repository")
                self.log("   3. The repository exists and the name is correct")
                self.log("")
                self.log("   TIP: You can still create Issues (uncheck the PR checkbox)")
                return False

            # Branch might already exist, that's okay
            if resp.status_code == 422:
                error_detail = resp.json()
                if "already exists" in str(error_detail).lower():
                    self.log(f"Branch {branch_name} already exists, using existing branch")
                    return True
                else:
                    self.log(f"Error creating branch: {error_detail}")

            resp.raise_for_status()
            self.log(f"✅ Branch {branch_name} created")

            # 3. Create a placeholder file with instructions
            self.log("Creating placeholder commit with Copilot instructions...")
            file_content = f"""# Copilot Instructions

This is a placeholder file created to allow PR creation.

## Task
{instructions}

Please process the instructions above and make the necessary changes to the documentation.

Once you've made the changes, you can delete this file.
"""

            encoded_content = base64.b64encode(file_content.encode('utf-8')).decode()

            file_payload = {
                "message": f"Add Copilot instructions for {branch_name}",
                "content": encoded_content,
                "branch": branch_name
            }

            file_url = f"https://api.github.com/repos/{owner}/{repo}/contents/.copilot-instructions.md"
            resp = requests.put(file_url, headers=rest_headers, json=file_payload, timeout=30)
            resp.raise_for_status()

            self.log(f"✅ Placeholder commit created in branch {branch_name}")
            return True

        except requests.HTTPError as e:
            self.log(f"❌ HTTP Error creating branch with placeholder: {e}")
            if e.response.status_code == 403:
                self.log("   Permission denied - token doesn't have write access")
            return False
        except Exception as e:
            self.log(f"❌ Error creating branch with placeholder: {str(e)}")
            return False


# Backward compatibility alias
GitHubAPI = GitHubGQL