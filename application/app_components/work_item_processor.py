"""
Work Item Processor
Handles processing of Azure DevOps work items and UUF items
"""

import re
import html
import requests
from typing import Dict, Any, Optional, Tuple
from urllib.parse import urlparse
from .utils import WorkItemFieldExtractor

# User agent for web requests
USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'


class WorkItemProcessor:
    """Processor for extracting and validating work item data with advanced parsing"""
    
    def __init__(self, logger, config: Dict[str, Any] = None):
        self.logger = logger
        self.log = logger.log if hasattr(logger, 'log') else logger
        self.config = config or {}
    
    def process_work_item(self, work_item: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Process a single work item to extract required fields with advanced validation"""
        try:
            work_item_id = work_item['id']
            title = work_item.get('fields', {}).get('System.Title', 'No Title')
            description = work_item.get('fields', {}).get('System.Description', '')
            
            if not description:
                self.log(f"Work item {work_item_id} has no description, skipping")
                return None
                
            # Parse description for required fields
            parsed_data = self._parse_description(description)
            
            if not parsed_data:
                self.log(f"Work item {work_item_id} doesn't contain required fields, skipping")
                return None
                
            # Validate nature of request (check for both variations)
            nature_lower = parsed_data['nature_of_request'].lower()
            if not ("modify existing docs" in nature_lower or "modifying existing docs" in nature_lower):
                self.log(f"Work item {work_item_id} nature of request doesn't contain 'modify existing docs', skipping")
                return None
                
            # Extract GitHub info from document URL
            github_info = self._extract_github_info(parsed_data['mydoc_url'])

            # If the document does not include an original_content_git_url, skip this work item
            if not github_info.get('original_content_git_url'):
                self.log(f"Work item {work_item_id} skipped: original_content_git_url not found in document {parsed_data['mydoc_url']}")
                return None
            
            # Construct proper web URL for work item
            # The API returns something like: https://dev.azure.com/org/project/_apis/wit/workItems/123
            # We need to convert it to: https://dev.azure.com/org/project/_workitems/edit/123
            work_item_url = ''
            api_url = work_item.get('url', '')
            if api_url:
                # Convert API URL to web URL
                # Replace /_apis/wit/workItems/ with /_workitems/edit/
                work_item_url = api_url.replace('/_apis/wit/workItems/', '/_workitems/edit/')

            processed_item = {
                'id': work_item_id,
                'title': title,
                'nature_of_request': parsed_data['nature_of_request'],
                'mydoc_url': parsed_data['mydoc_url'],
                'text_to_change': parsed_data['text_to_change'],
                'new_text': parsed_data['new_text'],
                'github_info': github_info,
                'status': 'Ready',
                'source': 'Azure DevOps',
                'source_url': work_item_url,  # URL to Azure DevOps work item
                'original_new_text': parsed_data['new_text']  # Keep original for reference
            }
            
            self.log(f"Successfully processed work item {work_item_id}")
            return processed_item
            
        except Exception as e:
            self.log(f"Error processing work item {work_item.get('id', 'unknown')}: {str(e)}")
            return None
    
    def process_uuf_item(self, uuf_item: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Process a single UUF item from Dataverse/PowerApp with enhanced field mapping"""
        try:
            # Extract UUF item ID (adjust field name as needed)
            uuf_id = uuf_item.get('cr4af_uufid') or uuf_item.get('cr4af_name') or 'unknown'

            # Extract title
            title = uuf_item.get('cr4af_title') or uuf_item.get('cr4af_subject') or 'No Title'

            # Extract description/details
            description = uuf_item.get('cr4af_description') or uuf_item.get('cr4af_details') or ''

            if not description:
                self.log(f"UUF item {uuf_id} has no description, skipping")
                return None

            # Extract document URL
            doc_url = uuf_item.get('cr4af_documenturl') or uuf_item.get('cr4af_docurl') or ''

            if not doc_url:
                self.log(f"UUF item {uuf_id} has no document URL, skipping")
                return None

            # Extract text to change and new text
            text_to_change = uuf_item.get('cr4af_texttochange') or uuf_item.get('cr4af_currenttext') or ''
            new_text = uuf_item.get('cr4af_proposednewtext') or uuf_item.get('cr4af_newtext') or ''

            if not text_to_change or not new_text:
                self.log(f"UUF item {uuf_id} missing text fields, skipping")
                return None

            # Extract GitHub info from document URL
            github_info = self._extract_github_info(doc_url)

            # If the document does not include an original_content_git_url, skip this item
            if not github_info.get('original_content_git_url'):
                self.log(f"UUF item {uuf_id} skipped: original_content_git_url not found in document {doc_url}")
                return None

            # Get UUF item URL if available (e.g., from Dataverse)
            uuf_url = uuf_item.get('cr4af_itemurl', '') or uuf_item.get('cr4af_url', '')

            processed_item = {
                'id': uuf_id,
                'title': title,
                'nature_of_request': 'UUF Item - Modify existing docs',
                'mydoc_url': doc_url,
                'text_to_change': text_to_change,
                'new_text': new_text,
                'github_info': github_info,
                'status': 'Ready',
                'source': 'UUF',  # Mark as UUF item
                'source_url': uuf_url,  # URL to UUF item (if available)
                'original_new_text': new_text
            }

            self.log(f"Successfully processed UUF item {uuf_id}")
            return processed_item

        except Exception as e:
            self.log(f"Error processing UUF item {uuf_item.get('cr4af_uufid', 'unknown')}: {str(e)}")
            return None
    
    def _parse_description(self, description: str) -> Optional[Dict[str, Any]]:
        """Parse work item description to extract required fields using enhanced regex patterns"""
        # Enhanced regex patterns from regex_V5
        patterns = {
            'nature_of_request': r'nature\s+of\s+request[:\s]*([^\)]*\))',
            'link_to_doc': r'link\s+to\s+doc[:\s]*([^\s&]+)',
            'text_to_change': r'text\s+to\s+change[:\s]*([\s\S]*?)(?=\n*-+\s*Proposed new text|If adding brand new docs:|$)',
            'proposed_new_text': r'proposed\s+new\s+text[:\s]*([\s\S]+?)(?=\s*If\s+adding\s+brand\s+new\s+docs:)'
        }
        
        # Clean HTML tags if present
        clean_description = re.sub(r'<[^>]+>', '', description)
        
        # Convert HTML entities to characters (e.g., &quot; to ", &amp; to &)
        clean_description = html.unescape(clean_description)
        
        extracted = {}
        for field, pattern in patterns.items():
            match = re.search(pattern, clean_description, re.IGNORECASE | re.DOTALL)
            if match:
                value = match.group(1).strip()
                
                if field == 'nature_of_request':
                    extracted['nature_of_request'] = value
                elif field == 'link_to_doc':
                    extracted['mydoc_url'] = value.rstrip('-')
                elif field == 'text_to_change':
                    extracted['text_to_change'] = value
                elif field == 'proposed_new_text':
                    extracted['new_text'] = value
                    
        # If enhanced patterns don't work, fall back to basic patterns
        if not all(field in extracted for field in ['nature_of_request', 'mydoc_url', 'text_to_change', 'new_text']):
            basic_patterns = {
                'nature_of_request': r'nature\s+of\s+request[:\s]*([^\n]+)',
                'link_to_doc': r'link\s+to\s+doc[:\s]*([^\s]+)',
                'text_to_change': r'text\s+to\s+change[:\s]*(.+?)(?=proposed\s+new\s+text|$)',
                'proposed_new_text': r'proposed\s+new\s+text[:\s]*(.+?)(?=\n\n|$)'
            }
            
            extracted = {}
            for field, pattern in basic_patterns.items():
                match = re.search(pattern, clean_description, re.IGNORECASE | re.DOTALL)
                if match:
                    value = match.group(1).strip()
                    
                    if field == 'nature_of_request':
                        extracted['nature_of_request'] = value
                    elif field == 'link_to_doc':
                        extracted['mydoc_url'] = value
                    elif field == 'text_to_change':
                        extracted['text_to_change'] = value
                    elif field == 'proposed_new_text':
                        extracted['new_text'] = value
        
        # Validate all required fields are present
        required_fields = ['nature_of_request', 'mydoc_url', 'text_to_change', 'new_text']
        if not all(field in extracted for field in required_fields):
            return None
            
        return extracted

    def _extract_github_info(self, doc_url: str) -> Dict[str, Any]:
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

            html_content = response.text

            # Extract ms.author
            ms_author = self._extract_meta_tag(html_content, 'ms.author')

            # Extract original_content_git_url
            original_content_git_url = self._extract_meta_tag(html_content, 'original_content_git_url')

            if not original_content_git_url:
                # Try alternative extraction method
                match = re.search(r"original_content_git_url[\"\']?\s*[:=]\s*[\"\']([^\"']+)[\"']", html_content, re.IGNORECASE)
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

    def _extract_meta_tag(self, html_content: str, name: str) -> Optional[str]:
        """Extract content from meta tag"""
        pattern = rf'<meta\s+(?:[^>]*?\s)?(?:name|property)\s*=\s*["\'](?P<n>{re.escape(name)})["\']\s+[^>]*?\bcontent\s*=\s*["\'](?P<content>[^"\']+)["\'][^>]*?>'
        match = re.search(pattern, html_content, re.IGNORECASE)
        if match:
            return match.group('content').strip()
        return None

    def _parse_github_url(self, url: str) -> Tuple[str, str]:
        """Parse GitHub URL to extract owner and repo"""
        parsed = urlparse(url)
        if "github.com" not in parsed.netloc.lower():
            raise ValueError(f"Not a GitHub URL: {url}")
        parts = [p for p in parsed.path.split("/") if p]
        if len(parts) < 2:
            raise ValueError(f"Unable to parse owner/repo from: {url}")
        return parts[0], parts[1]