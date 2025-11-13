"""
Cache Manager for GitHub PRs and Issues
Stores fetched items in temporary cache to avoid reloading on every app start
"""

import json
import os
import tempfile
import time
from pathlib import Path
from typing import List, Dict, Any, Optional
from hashlib import md5


class CacheManager:
    """Manages caching of GitHub PRs and Issues"""

    def __init__(self, cache_duration_hours: int = 24):
        """
        Initialize cache manager

        Args:
            cache_duration_hours: How long cache is valid (default 24 hours)
        """
        self.cache_duration_seconds = cache_duration_hours * 3600
        self.cache_dir = Path(tempfile.gettempdir()) / "github_pulse_cache"
        self.cache_dir.mkdir(exist_ok=True)

    def _get_cache_key(self, source_type: str, identifier: str) -> str:
        """Generate cache key from source type and identifier"""
        # Use MD5 hash to create safe filename
        key_str = f"{source_type}_{identifier}"
        return md5(key_str.encode()).hexdigest()

    def _get_cache_path(self, cache_key: str) -> Path:
        """Get full path to cache file"""
        return self.cache_dir / f"{cache_key}.json"

    def is_cache_valid(self, source_type: str, identifier: str) -> bool:
        """Check if cache exists and is still valid"""
        cache_key = self._get_cache_key(source_type, identifier)
        cache_path = self._get_cache_path(cache_key)

        if not cache_path.exists():
            return False

        # Check if cache has expired
        file_age = time.time() - cache_path.stat().st_mtime
        return file_age < self.cache_duration_seconds

    def load_from_cache(self, source_type: str, identifier: str) -> Optional[List[Dict[str, Any]]]:
        """
        Load GitHub items from cache

        Args:
            source_type: 'github_prs', 'github_issues', 'target_prs', 'fork_prs', etc.
            identifier: repository identifier or config hash

        Returns:
            List of items if cache is valid, None otherwise
        """
        if not self.is_cache_valid(source_type, identifier):
            return None

        cache_key = self._get_cache_key(source_type, identifier)
        cache_path = self._get_cache_path(cache_key)

        try:
            with open(cache_path, 'r', encoding='utf-8') as f:
                cache_data = json.load(f)

            # Validate cache structure
            if 'timestamp' not in cache_data or 'items' not in cache_data:
                return None

            return cache_data['items']

        except Exception as e:
            print(f"Error loading cache: {e}")
            return None

    def save_to_cache(self, source_type: str, identifier: str, items: List[Dict[str, Any]]) -> bool:
        """
        Save GitHub items to cache

        Args:
            source_type: 'github_prs', 'github_issues', 'target_prs', 'fork_prs', etc.
            identifier: repository identifier or config hash
            items: List of items to cache (PRs or Issues)

        Returns:
            True if successful, False otherwise
        """
        cache_key = self._get_cache_key(source_type, identifier)
        cache_path = self._get_cache_path(cache_key)

        try:
            cache_data = {
                'timestamp': time.time(),
                'source_type': source_type,
                'identifier': identifier,
                'items': items
            }

            with open(cache_path, 'w', encoding='utf-8') as f:
                json.dump(cache_data, f, indent=2, ensure_ascii=False)

            return True

        except Exception as e:
            print(f"Error saving cache: {e}")
            return False

    def invalidate_cache(self, source_type: str = None, identifier: str = None):
        """
        Invalidate (delete) cache

        Args:
            source_type: If specified, only invalidate this source type
            identifier: If specified, only invalidate this specific cache
        """
        if source_type and identifier:
            # Invalidate specific cache
            cache_key = self._get_cache_key(source_type, identifier)
            cache_path = self._get_cache_path(cache_key)
            if cache_path.exists():
                cache_path.unlink()
        elif source_type:
            # Invalidate all caches for this source type
            for cache_file in self.cache_dir.glob("*.json"):
                try:
                    with open(cache_file, 'r', encoding='utf-8') as f:
                        cache_data = json.load(f)
                    if cache_data.get('source_type') == source_type:
                        cache_file.unlink()
                except:
                    pass
        else:
            # Invalidate all caches
            for cache_file in self.cache_dir.glob("*.json"):
                cache_file.unlink()

    def get_cache_info(self) -> Dict[str, Any]:
        """Get information about cached items"""
        cache_files = list(self.cache_dir.glob("*.json"))

        info = {
            'cache_dir': str(self.cache_dir),
            'total_files': len(cache_files),
            'total_size_bytes': sum(f.stat().st_size for f in cache_files),
            'caches': []
        }

        for cache_file in cache_files:
            try:
                with open(cache_file, 'r', encoding='utf-8') as f:
                    cache_data = json.load(f)

                file_age = time.time() - cache_file.stat().st_mtime
                is_valid = file_age < self.cache_duration_seconds

                info['caches'].append({
                    'source_type': cache_data.get('source_type', 'unknown'),
                    'item_count': len(cache_data.get('items', [])),
                    'age_hours': round(file_age / 3600, 1),
                    'is_valid': is_valid,
                    'size_kb': round(cache_file.stat().st_size / 1024, 1)
                })
            except:
                pass

        return info

    def cleanup_expired(self):
        """Remove expired cache files"""
        current_time = time.time()
        removed_count = 0

        for cache_file in self.cache_dir.glob("*.json"):
            file_age = current_time - cache_file.stat().st_mtime
            if file_age >= self.cache_duration_seconds:
                cache_file.unlink()
                removed_count += 1

        return removed_count
