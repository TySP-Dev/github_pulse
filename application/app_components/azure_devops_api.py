"""
Azure DevOps API Manager
Handles Azure DevOps REST API operations for work items
"""

import base64
import json
import re
import requests
from typing import List, Dict, Any, Tuple
from urllib.parse import urlparse, parse_qs

# User agent for Azure DevOps API requests
USER_AGENT = "azure-devops-github-processor/2.0"


class AzureDevOpsAPI:
    """Azure DevOps REST API client"""
    
    def __init__(self, organization: str, pat_token: str, logger=None):
        self.organization = organization
        self.pat_token = pat_token
        self.logger = logger
        self.base_url = f"https://dev.azure.com/{organization}"
        self.api_version = "7.0"
    
    def log(self, message: str) -> None:
        """Log a message"""
        if self.logger:
            self.logger.log(message)
        else:
            print(message)
    
    def _headers(self):
        """Get headers for Azure DevOps API requests"""
        return {
            "Authorization": f"Basic {base64.b64encode(f':{self.pat_token}'.encode()).decode()}",
            "Content-Type": "application/json-patch+json",
            "User-Agent": USER_AGENT
        }
    
    def parse_query_url(self, url: str) -> Tuple[str, str, str]:
        """Parse Azure DevOps query URL to extract org, project, and query ID
        
        Supports both URL formats:
        1. https://dev.azure.com/organization/project/_queries/query/12345/
        2. https://organization.visualstudio.com/project/_queries/query/12345/
        """
        parsed_url = urlparse(url)
        
        # Check for dev.azure.com format
        if 'dev.azure.com' in parsed_url.netloc:
            path_parts = parsed_url.path.strip('/').split('/')
            
            if len(path_parts) < 5:
                raise ValueError("Invalid query URL format for dev.azure.com")
                
            organization = path_parts[0]
            project = path_parts[1]
            
        # Check for visualstudio.com format
        elif 'visualstudio.com' in parsed_url.netloc:
            # Extract organization from subdomain (e.g., msft-skilling.visualstudio.com)
            hostname_parts = parsed_url.netloc.split('.')
            if len(hostname_parts) < 3 or hostname_parts[1] != 'visualstudio':
                raise ValueError("Invalid visualstudio.com URL format")
                
            organization = hostname_parts[0]
            
            path_parts = parsed_url.path.strip('/').split('/')
            
            if len(path_parts) < 4:
                raise ValueError("Invalid query URL format for visualstudio.com")
                
            project = path_parts[0]
            
        else:
            raise ValueError("URL must be from dev.azure.com or visualstudio.com")
        
        # Find query ID in the URL (same logic for both formats)
        query_id = None
        if '_queries/query/' in url:
            # Extract query ID from path
            for i, part in enumerate(path_parts):
                if part == 'query' and i > 0 and path_parts[i-1] == '_queries':
                    if i + 1 < len(path_parts):
                        query_id = path_parts[i + 1]
                    break
        elif 'queryId=' in url:
            match = re.search(r'queryId=([^&]+)', url)
            if match:
                query_id = match.group(1)
                
        if not query_id:
            raise ValueError("Could not extract query ID from URL")
            
        return organization, project, query_id
    
    def execute_query(self, org: str, project: str, query_id: str, token: str) -> List[Dict[str, Any]]:
        """Execute Azure DevOps query and return work items"""
        # Build API URL for query execution
        api_url = f"https://dev.azure.com/{org}/{project}/_apis/wit/wiql/{query_id}?api-version=6.0"
        
        # Prepare headers
        auth_string = base64.b64encode(f":{token}".encode()).decode()
        headers = {
            'Authorization': f'Basic {auth_string}',
            'Content-Type': 'application/json',
            'User-Agent': USER_AGENT
        }
        
        # Execute query
        self.log(f"Executing query at: {api_url}")
        response = requests.get(api_url, headers=headers, timeout=30)
        
        if response.status_code != 200:
            raise RuntimeError(f"Query execution failed: {response.status_code} - {response.text}")
            
        query_result = response.json()
        work_item_refs = query_result.get('workItems', [])
        
        if not work_item_refs:
            self.log("No work items found in query result")
            return []
            
        # Get detailed work item data
        work_item_ids = [str(item['id']) for item in work_item_refs]
        ids_param = ','.join(work_item_ids)
        
        details_url = f"https://dev.azure.com/{org}/{project}/_apis/wit/workitems?ids={ids_param}&api-version=6.0"
        
        self.log(f"Fetching details for {len(work_item_ids)} work items")
        details_response = requests.get(details_url, headers=headers, timeout=30)
        
        if details_response.status_code != 200:
            raise RuntimeError(f"Work item details fetch failed: {details_response.status_code}")
            
        return details_response.json().get('value', [])
    
    def _get_work_items_details(self, organization: str, work_item_ids: List[str], pat_token: str) -> List[Dict[str, Any]]:
        """Get detailed information for work items"""
        try:
            # Build batch request URL
            ids_param = ','.join(work_item_ids)
            details_url = f"https://dev.azure.com/{organization}/_apis/wit/workitems"
            
            headers = {
                "Authorization": f"Basic {self._encode_pat(pat_token)}",
                "Content-Type": "application/json",
                "Accept": "application/json",
                "User-Agent": USER_AGENT
            }
            
            params = {
                "ids": ids_param,
                "api-version": self.api_version,
                "$expand": "fields"
            }
            
            self.log(f"Fetching details for work items: {ids_param}")
            response = requests.get(details_url, headers=headers, params=params, timeout=30)
            response.raise_for_status()
            
            result = response.json()
            work_items = result.get('value', [])
            
            self.log(f"Retrieved details for {len(work_items)} work item(s)")
            return work_items
            
        except requests.RequestException as e:
            raise Exception(f"Network error fetching work item details: {str(e)}")
        except Exception as e:
            raise Exception(f"Error fetching work item details: {str(e)}")
    
    def add_github_link_to_work_item(self, work_item_id: str, github_url: str, link_title: str = "GitHub Issue"):
        """Add a GitHub issue/PR link to an Azure DevOps work item"""
        self.log(f"Adding GitHub link to work item #{work_item_id}: {github_url}")
        
        url = f"{self.base_url}/_apis/wit/workitems/{work_item_id}?api-version=7.0"
        
        patch_document = [
            {
                "op": "add",
                "path": "/relations/-",
                "value": {
                    "rel": "Hyperlink",
                    "url": github_url,
                    "attributes": {
                        "comment": link_title
                    }
                }
            }
        ]
        
        try:
            response = requests.patch(url, headers=self._headers(), json=patch_document, timeout=30)
            if response.status_code == 200:
                self.log(f"✅ Successfully linked GitHub resource to work item #{work_item_id}")
                return True
            else:
                self.log(f"❌ Failed to link GitHub resource: {response.status_code} - {response.text}")
                return False
        except Exception as e:
            self.log(f"❌ Exception linking GitHub resource: {str(e)}")
            return False
    
    def _encode_pat(self, pat_token: str) -> str:
        """Encode PAT token for Basic authentication"""
        import base64
        # For Azure DevOps, username can be empty, just use :token
        credentials = f":{pat_token}"
        encoded = base64.b64encode(credentials.encode()).decode()
        return encoded