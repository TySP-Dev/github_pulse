"""
Dataverse API Manager
Handles PowerApp/Dataverse operations for UUF items
"""

import json
import re
import requests
import urllib.parse
from typing import List, Dict, Any, Optional
from urllib.parse import urlparse

# Constants
USER_AGENT = "azure-devops-github-processor/2.0"


class DataverseAPI:
    """Dataverse/PowerApp API client for UUF items"""
    
    def __init__(self, environment_url: str, table_name: str, logger=None, config: dict = None):
        self.environment_url = environment_url.rstrip('/')
        self.table_name = table_name
        self.logger = logger
        self.config = config or {}
        self.access_token = None
        self.api_version = "v9.2"
    
    def log(self, message: str) -> None:
        """Log a message"""
        if self.logger:
            self.logger.log(message)
        else:
            print(message)
    
    def authenticate(self, client_id: str, client_secret: str, tenant_id: str) -> bool:
        """Authenticate with Azure AD and get access token"""
        try:
            # Azure AD token endpoint
            token_url = f"https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token"
            
            # Prepare request data
            data = {
                'grant_type': 'client_credentials',
                'client_id': client_id,
                'client_secret': client_secret,
                'scope': f"{self.environment_url}/.default"
            }
            
            headers = {
                'Content-Type': 'application/x-www-form-urlencoded'
            }
            
            self.log("Authenticating with Azure AD...")
            response = requests.post(token_url, data=data, headers=headers, timeout=30)
            response.raise_for_status()
            
            token_data = response.json()
            self.access_token = token_data['access_token']
            
            self.log("✅ Successfully authenticated with Azure AD")
            return True
            
        except requests.RequestException as e:
            self.log(f"❌ Network error during authentication: {str(e)}")
            return False
        except KeyError as e:
            self.log(f"❌ Invalid token response: {str(e)}")
            return False
        except Exception as e:
            self.log(f"❌ Authentication error: {str(e)}")
            return False
    
    def _headers(self):
        """Get headers for Dataverse API requests"""
        return {
            "Authorization": f"Bearer {self.access_token}",
            "OData-MaxVersion": "4.0",
            "OData-Version": "4.0",
            "Accept": "application/json",
            "Content-Type": "application/json",
            "User-Agent": USER_AGENT
        }

    def fetch_uuf_items(self, filter_query: Optional[str] = None) -> List[Dict[str, Any]]:
        """Fetch UUF items from Dataverse"""
        try:
            if not self.access_token:
                raise RuntimeError("Not authenticated. Call authenticate() first.")
            
            self.log(f"Fetching UUF items from table: {self.table_name}")
            
            # Build API URL
            api_url = f"{self.environment_url}/api/data/{self.api_version}/{self.table_name}"
            
            # Add filter if provided
            if filter_query:
                api_url += f"?$filter={urllib.parse.quote(filter_query)}"
            
            response = requests.get(api_url, headers=self._headers(), timeout=60)
            
            if response.status_code != 200:
                raise RuntimeError(f"Failed to fetch UUF items: {response.status_code} - {response.text}")
            
            data = response.json()
            items = data.get('value', [])
            
            self.log(f"✅ Fetched {len(items)} UUF items from Dataverse")
            return items
            
        except Exception as e:
            self.log(f"❌ Error fetching UUF items: {str(e)}")
            raise

    def process_uuf_item(self, uuf_item: dict) -> dict | None:
        """Process a single UUF item from Dataverse/PowerApp

        UUF items may have different field names than Azure DevOps work items.
        Adjust the field mapping based on your actual Dataverse table schema.
        """
        try:
            # Extract UUF item ID (adjust field names as needed)
            uuf_id = uuf_item.get('cr4af_uufid') or uuf_item.get('cr4af_name') or uuf_item.get('cr_uufitemid') or 'unknown'

            # Extract title
            title = uuf_item.get('cr4af_title') or uuf_item.get('cr4af_subject') or uuf_item.get('cr_title') or 'No Title'

            # Extract description/details
            description = uuf_item.get('cr4af_description') or uuf_item.get('cr4af_details') or uuf_item.get('cr_description') or ''

            if not description:
                self.log(f"UUF item {uuf_id} has no description, skipping")
                return None

            # Extract document URL
            doc_url = uuf_item.get('cr4af_documenturl') or uuf_item.get('cr4af_docurl') or uuf_item.get('cr_documenturl') or ''

            if not doc_url:
                self.log(f"UUF item {uuf_id} has no document URL, skipping")
                return None

            # Extract text to change and new text
            text_to_change = uuf_item.get('cr4af_texttochange') or uuf_item.get('cr4af_currenttext') or uuf_item.get('cr_currenttext') or ''
            new_text = uuf_item.get('cr4af_proposednewtext') or uuf_item.get('cr4af_newtext') or uuf_item.get('cr_newtext') or ''

            if not text_to_change or not new_text:
                self.log(f"UUF item {uuf_id} missing text fields, skipping")
                return None

            # Extract GitHub info from document URL
            github_info = self._extract_github_info(doc_url)

            # If the document does not include an original_content_git_url, skip this item
            if not github_info.get('original_content_git_url'):
                self.log(f"UUF item {uuf_id} skipped: original_content_git_url not found in document {doc_url}")
                return None

            processed_item = {
                'id': uuf_id,
                'title': title,
                'nature_of_request': 'UUF Item - Modify existing docs',
                'mydoc_url': doc_url,
                'text_to_change': text_to_change,
                'new_text': new_text,
                'github_info': github_info,
                'status': 'Ready',
                'original_new_text': new_text,
                'source': 'UUF'  # Mark as UUF item
            }

            self.log(f"Successfully processed UUF item {uuf_id}")
            return processed_item

        except Exception as e:
            self.log(f"Error processing UUF item {uuf_item.get('cr4af_uufid', 'unknown')}: {str(e)}")
            return None

    def _extract_github_info(self, doc_url: str) -> dict:
        """Extract GitHub repository info and ms.author from document URL

        If GITHUB_REPO is configured in .env, it will be used instead of the repo
        extracted from the document metadata. This allows you to create PRs in your
        fork while preserving the file path and ms.author from the original document.
        """
        try:
            # Fetch the document
            headers = {'User-Agent': USER_AGENT}
            response = requests.get(doc_url, headers=headers, timeout=30)
            response.raise_for_status()

            html = response.text

            # Extract ms.author
            ms_author = self._extract_meta_tag(html, 'ms.author')

            # Extract original_content_git_url
            original_content_git_url = self._extract_meta_tag(html, 'original_content_git_url')

            if not original_content_git_url:
                # Try alternative extraction method
                match = re.search(r"original_content_git_url[\"\']?\s*[:=]\s*[\"\']([^\"']+)[\"']", html, re.IGNORECASE)
                if match:
                    original_content_git_url = match.group(1).strip()

            if not original_content_git_url:
                raise ValueError("original_content_git_url not found in document")

            # Check if GITHUB_REPO is configured in .env
            # If it is, use that instead of the repo from the document
            configured_repo = self.config.get('GITHUB_REPO')

            if configured_repo and '/' in configured_repo:
                # Use the configured repository (e.g., "b-tsammons/fabric-docs-pr")
                parts = configured_repo.split('/', 1)
                owner = parts[0].strip()
                repo = parts[1].strip()
                self.log(f"Using configured GITHUB_REPO: {owner}/{repo} (overriding document metadata)")
            else:
                # Parse GitHub owner/repo from original_content_git_url (fallback to document metadata)
                owner, repo = self._parse_github_url(original_content_git_url)
                self.log(f"Using repository from document metadata: {owner}/{repo}")

            return {
                'ms_author': ms_author,
                'original_content_git_url': original_content_git_url,
                'owner': owner,
                'repo': repo
            }

        except Exception as e:
            self.log(f"Error extracting GitHub info from {doc_url}: {str(e)}")
            return {
                'ms_author': None,
                'original_content_git_url': None,
                'owner': None,
                'repo': None,
                'error': str(e)
            }

    def _extract_meta_tag(self, html: str, name: str) -> str | None:
        """Extract content from meta tag"""
        pattern = rf'<meta\s+(?:[^>]*?\s)?(?:name|property)\s*=\s*["\'](?P<n>{re.escape(name)})["\']\s+[^>]*?\bcontent\s*=\s*["\'](?P<content>[^"\']+)["\'][^>]*?>'
        match = re.search(pattern, html, re.IGNORECASE)
        if match:
            return match.group('content').strip()
        return None

    def _parse_github_url(self, url: str) -> tuple[str, str]:
        """Parse GitHub URL to extract owner and repo"""
        parsed = urlparse(url)
        if "github.com" not in parsed.netloc.lower():
            raise ValueError(f"Not a GitHub URL: {url}")
        parts = [p for p in parsed.path.split("/") if p]
        if len(parts) < 2:
            raise ValueError(f"Unable to parse owner/repo from: {url}")
        return parts[0], parts[1]