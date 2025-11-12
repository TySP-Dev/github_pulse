"""
AI Manager
Handles AI module availability checking, installation, and provider management
Includes AI provider implementations (Claude, ChatGPT) and git operations
"""

import os
import shutil
import subprocess
import sys
import tempfile
import time
import tkinter as tk
from abc import ABC, abstractmethod
from pathlib import Path
from tkinter import messagebox
from typing import List, Tuple, Optional


class Logger:
    """Simple logger interface"""
    def __init__(self, log_func):
        self.log = log_func


class AIProvider(ABC):
    """Base class for AI providers"""

    def __init__(self, api_key: str, logger: Logger):
        self.api_key = api_key
        self.logger = logger

    @abstractmethod
    def make_change(self, file_content: str, old_text: str, new_text: str, file_path: str, custom_instructions: str = None) -> Optional[str]:
        """
        Use AI to make a change in the file content.

        Args:
            file_content: Current content of the file
            old_text: Text to find and replace
            new_text: New text to replace with
            file_path: Path to the file (for context)
            custom_instructions: Optional custom instructions from user

        Returns:
            Updated file content, or None if AI couldn't make the change
        """
        pass


class ClaudeProvider(AIProvider):
    """Claude AI provider using Anthropic API"""

    def make_change(self, file_content: str, old_text: str, new_text: str, file_path: str, custom_instructions: str = None) -> Optional[str]:
        """Make smart, targeted changes based on reference text and suggestions

        Args:
            file_content: Full file content
            old_text: Reference text (what user is talking about - may not be exact)
            new_text: Suggested changes (what user wants to see)
            file_path: Path to the file being modified
            custom_instructions: Optional custom instructions from user
        """

        # Step 1: Try direct string replacement if reference text is exact match
        if old_text and old_text.strip() in file_content:
            self.logger.log("✅ Making direct string replacement (reference text found exactly)")
            updated_content = file_content.replace(old_text.strip(), new_text.strip())
            if updated_content != file_content:
                original_lines = file_content.split('\n')
                updated_lines = updated_content.split('\n')
                import difflib
                diff = list(difflib.unified_diff(original_lines, updated_lines, lineterm=''))
                changed_lines = len([line for line in diff if line.startswith('+') or line.startswith('-')])
                self.logger.log(f"✅ Direct replacement successful ({changed_lines} lines changed)")
                return updated_content

        # Step 2: Use AI to generate full document with targeted changes
        self.logger.log("📝 Using AI to modify the document...")
        return self._generate_updated_document(file_content, old_text, new_text, file_path, custom_instructions)

    def _generate_updated_document(self, file_content: str, old_text: str, new_text: str, file_path: str, custom_instructions: str = None) -> Optional[str]:
        """Generate updated document content using Claude"""
        
        try:
            import anthropic
            client = anthropic.Anthropic(api_key=self.api_key)

            # Build custom instructions text
            if custom_instructions and custom_instructions.strip():
                custom_instructions_text = f"""
**Additional Custom Instructions:**
{custom_instructions.strip()}

"""
            else:
                custom_instructions_text = ""

            # Handle case where new_text is empty or just guidance
            if new_text and new_text.strip() and not new_text.strip().lower().startswith('<blank'):
                # We have specific replacement text
                guidance_text = f"""
**Reference text to find:**
```
{old_text}
```

**Replace with this specific content:**
```
{new_text}
```

Please find the reference text and replace it with the suggested content."""
            else:
                # new_text is empty or just guidance - use old_text as instructions
                guidance_text = f"""
**Task Instructions:**
{old_text}

**Note:** No specific replacement text provided. Use the task instructions above to determine what changes to make to improve the document. Add appropriate content based on the instructions."""

            prompt = f"""**Instructions:**

Task: Update the documentation file with the changes requested.

Steps to complete:

1. Review the current file content below
2. Follow the guidance provided to determine what changes to make
3. Make appropriate improvements while maintaining existing formatting
4. Return the complete updated file content

> [!IMPORTANT]
> OUTPUT REQUIREMENTS:
> - Return ONLY the complete file content - no explanatory text, dialog, or commentary
> - Do NOT add any text before or after the file content
> - Do NOT wrap output in markdown code blocks (```), just return the raw content
> - Return the ENTIRE document - no truncation, no placeholders like [Rest of the document here...]
> - Every single line of the original document must be present in your response
> - Preserve all markdown formatting, links, and code blocks exactly
> - Please ensure the changes align with Microsoft documentation standards
> - Only make changes that fulfill the specified request

{custom_instructions_text}

**Current File Content:**
```
{file_content}
```

{guidance_text}

Return the complete updated file content now (NO explanatory text):"""

            message = client.messages.create(
                model="claude-3-5-haiku-20241022",
                max_tokens=4096,
                temperature=0.1,
                messages=[{"role": "user", "content": prompt}]
            )
            
            updated_content = message.content[0].text.strip()
            
            # Basic validation - ensure content was actually changed
            if updated_content and updated_content != file_content:
                original_lines = file_content.split('\n')
                updated_lines = updated_content.split('\n')
                import difflib
                diff = list(difflib.unified_diff(original_lines, updated_lines, lineterm=''))
                changed_lines = len([line for line in diff if line.startswith('+') or line.startswith('-')])
                
                self.logger.log(f"✅ Claude document update successful ({changed_lines} lines affected)")
                return updated_content
            else:
                self.logger.log("⚠️ No changes detected in AI response")
                return None
                
        except Exception as e:
            self.logger.log(f"❌ Error generating updated document with Claude: {str(e)}")
            return None

    def _generate_with_context_window_claude(self, file_content: str, old_text: str, new_text: str, file_path: str) -> Optional[str]:
        """Use context window approach with Claude - AI only sees/modifies a small section

        This physically prevents AI from rewriting entire file by only giving it
        the relevant section to work with.
        """
        try:
            import difflib
            import anthropic

            # Step 1: Find where the reference text is located
            lines = file_content.split('\n')
            ref_lines = old_text.split('\n') if old_text else []

            # Find best matching location for reference text
            start_line = 0
            if ref_lines:
                matcher = difflib.SequenceMatcher(None, ref_lines, lines)
                match = matcher.find_longest_match(0, len(ref_lines), 0, len(lines))
                if match.size > 0:
                    start_line = match.b
                    self.logger.log(f"📍 Found reference area at line {start_line + 1}")
                else:
                    self.logger.log("📍 Reference text not found, using beginning of file")

            # Step 2: Extract context window (30 lines before, 30 lines after)
            window_before = 30
            window_after = 30

            window_start = max(0, start_line - window_before)
            window_end = min(len(lines), start_line + len(ref_lines) + window_after)

            context_window = lines[window_start:window_end]
            self.logger.log(f"📄 Context window: lines {window_start + 1} to {window_end} ({len(context_window)} lines)")
            self.logger.log(f"   (AI can only modify this section, rest of file is protected)")

            # Step 3: Have AI modify only the context window
            context_text = '\n'.join(context_window)

            client = anthropic.Anthropic(api_key=self.api_key)

            prompt = f"""You are helping modify a small section of a documentation file. You can ONLY modify the section provided below.

File: {file_path}
Section location: Lines {window_start + 1} to {window_end}

REFERENCE TEXT (what user is referring to):
{old_text}

SUGGESTED CHANGES (what user wants):
{new_text}

SECTION TO MODIFY:
```
{context_text}
```

INSTRUCTIONS:
1. Understand the user's INTENT from the reference and suggestions:
   - "add/include/incorporate a section" = Add a COMPLETE NEW SECTION with heading and full content
   - "update/modify/change X" = Modify existing text X intelligently
   - "fix/correct" = Make specific correction only
   - Be generous with new content when asked to add something

2. For ADDING content (sections, paragraphs, examples):
   - Create complete, well-written content (not just stubs or brief additions)
   - Add proper markdown headers (## Best Practices, ### Example, etc.)
   - Place it logically (end of section, before ## Related content, etc.)
   - Match the document's writing style and tone

3. For MODIFYING content:
   - Change only what's requested
   - Leave everything else exactly as-is

4. Return the ENTIRE section (all {len(context_window)} lines) with your changes
5. No explanations - just the modified section

OUTPUT THE COMPLETE MODIFIED SECTION:"""

            message = client.messages.create(
                model="claude-3-5-haiku-20241022",
                max_tokens=4096,
                temperature=0.1,
                messages=[{"role": "user", "content": prompt}]
            )

            modified_window = message.content[0].text.strip()

            # Clean up code blocks if AI wrapped it
            if modified_window.startswith('```'):
                modified_window = '\n'.join(modified_window.split('\n')[1:-1])

            # Step 4: Replace the context window in the full file
            modified_lines = modified_window.split('\n')
            result_lines = lines[:window_start] + modified_lines + lines[window_end:]
            updated_content = '\n'.join(result_lines)

            # Verify change is minimal
            diff = list(difflib.unified_diff(lines, result_lines, lineterm=''))
            changed_lines = len([line for line in diff if line.startswith('+') or line.startswith('-')])

            self.logger.log(f"✅ Context window approach successful ({changed_lines} lines changed)")

            # Ensure we actually made changes
            if updated_content == file_content:
                self.logger.log("⚠️ No changes detected, falling back to full-document approach")
                return self._generate_updated_document(file_content, old_text, new_text, file_path)

            return updated_content

        except Exception as e:
            self.logger.log(f"❌ Error with context window approach: {str(e)}")
            self.logger.log("⚠️ Falling back to full-document approach")
            return self._generate_updated_document(file_content, old_text, new_text, file_path)

    def _validate_diff_patch(self, diff_patch: str, original_content: str, old_text: str, new_text: str) -> bool:
        """Validate that the AI-generated diff is safe and appropriate"""
        try:
            # Check for common problems
            lines = diff_patch.split('\n')

            # Problem 0: Check for proper diff structure
            has_hunk_header = any(line.startswith('@@') for line in lines)
            if not has_hunk_header:
                self.logger.log("❌ Invalid diff: Missing @@ hunk headers")
                return False

            # Problem 1: Check for duplicate +++ lines
            plus_count = sum(1 for line in lines if line.startswith('+++'))
            if plus_count > 1:
                self.logger.log("❌ Invalid diff: Multiple +++ lines detected")
                return False

            # Problem 2: Check for removal of metadata (title, author, etc.)
            for line in lines:
                if line.startswith('-') and not line.startswith('---'):
                    removed_content = line[1:].strip()
                    # Check if removing metadata
                    if any(keyword in removed_content.lower() for keyword in ['title:', 'author:', 'description:', 'ms.author:', 'ms.date:']):
                        self.logger.log(f"❌ Invalid diff: Attempting to remove metadata: {removed_content}")
                        return False

            # Problem 3: Check if diff is too large (indicates rewrite)
            removed_lines = len([line for line in lines if line.startswith('-') and not line.startswith('---')])
            added_lines = len([line for line in lines if line.startswith('+') and not line.startswith('+++')])

            if removed_lines > 10:  # Too many removals for an additive change
                self.logger.log(f"❌ Invalid diff: Too many removals ({removed_lines} lines)")
                return False

            return True

        except Exception as e:
            self.logger.log(f"❌ Error validating diff: {str(e)}")
            return False
    
    def _create_safe_diff(self, file_content: str, old_text: str, new_text: str, file_path: str) -> Optional[str]:
        """Create a safer, simpler diff that just adds content without removing anything"""
        try:
            # Strategy: Find the best location to add the new content and insert it there
            lines = file_content.split('\n')
            
            # Look for common insertion points for adding sections
            insertion_point = self._find_safe_insertion_point(lines, old_text, new_text)
            
            if insertion_point is None:
                self.logger.log("⚠️ Could not find safe insertion point")
                return None
            
            # Insert the new content at the found location
            new_lines = lines[:insertion_point] + [new_text.strip(), ''] + lines[insertion_point:]
            updated_content = '\n'.join(new_lines)
            
            self.logger.log(f"✅ Created safe diff - inserting content at line {insertion_point}")
            return updated_content
            
        except Exception as e:
            self.logger.log(f"❌ Error creating safe diff: {str(e)}")
            return None
    
    def _find_safe_insertion_point(self, lines: list, old_text: str, new_text: str) -> Optional[int]:
        """Find the best place to insert new content safely"""
        try:
            # Look for section headers to insert after
            for i, line in enumerate(lines):
                # If the old_text contains context about where to insert
                if old_text and old_text.lower().strip() in line.lower():
                    # Insert after this line
                    return i + 1
                
                # Look for pattern where we should insert a new section
                # Insert before conclusion, examples, or other sections
                if line.strip().startswith('##') and any(keyword in line.lower() for keyword in ['example', 'conclusion', 'summary', 'next steps']):
                    return i
            
            # If no specific location found, insert before the last section
            for i in range(len(lines) - 1, -1, -1):
                if lines[i].strip().startswith('##'):
                    return i
            
            # Last resort: insert at 80% through the document
            return int(len(lines) * 0.8)
            
        except Exception:
            return None

    def _apply_diff_patch(self, original_content: str, diff_patch: str, file_path: str) -> Optional[str]:
        """Apply a unified diff patch to the original content"""
        try:
            import tempfile
            import subprocess
            import os
            
            # Create temporary files
            with tempfile.TemporaryDirectory() as temp_dir:
                # Write original content to temp file
                original_file = os.path.join(temp_dir, "original.txt")
                with open(original_file, 'w', encoding='utf-8') as f:
                    f.write(original_content)
                
                # Write diff patch to temp file
                patch_file = os.path.join(temp_dir, "changes.patch")
                with open(patch_file, 'w', encoding='utf-8') as f:
                    f.write(diff_patch)
                
                # Apply patch using git apply (more reliable than patch command)
                try:
                    # First try git apply
                    subprocess.run(['git', 'apply', '--verbose', patch_file], 
                                 cwd=temp_dir, check=True, capture_output=True, text=True)
                    
                    # Read the result
                    with open(original_file, 'r', encoding='utf-8') as f:
                        return f.read()
                        
                except subprocess.CalledProcessError:
                    # Fallback to manual patch application
                    self.logger.log("📝 Git apply failed, trying manual diff application...")
                    return self._manual_diff_apply(original_content, diff_patch)
                    
        except Exception as e:
            self.logger.log(f"⚠️ Patch application failed: {str(e)}")
            return self._manual_diff_apply(original_content, diff_patch)

    def _manual_diff_apply(self, original_content: str, diff_patch: str) -> Optional[str]:
        """Manually apply a diff patch when git apply fails"""
        try:
            # Detect original line ending style
            has_crlf = '\r\n' in original_content

            original_lines = original_content.split('\n')
            result_lines = original_lines.copy()

            # Parse the diff patch
            diff_lines = diff_patch.split('\n')
            current_original_line = 0

            i = 0
            while i < len(diff_lines):
                line = diff_lines[i]

                # Look for @@ headers
                if line.startswith('@@'):
                    # Extract line numbers: @@ -start,count +start,count @@
                    parts = line.split()
                    if len(parts) >= 3:
                        old_info = parts[1][1:]  # Remove the -
                        if ',' in old_info:
                            start_line = int(old_info.split(',')[0]) - 1  # Convert to 0-based
                        else:
                            start_line = int(old_info) - 1

                        current_original_line = start_line
                    i += 1
                    continue

                # Skip diff headers (must check before processing -/+ lines)
                if line.startswith('---') or line.startswith('+++'):
                    i += 1
                    continue

                # Process diff lines
                if line.startswith('-'):
                    # Remove line
                    if current_original_line < len(result_lines):
                        del result_lines[current_original_line]
                elif line.startswith('+'):
                    # Add line
                    new_line = line[1:]  # Remove the +
                    # If original had CRLF and this line doesn't have \r, add it
                    if has_crlf and not new_line.endswith('\r'):
                        new_line = new_line + '\r'
                    result_lines.insert(current_original_line, new_line)
                    current_original_line += 1
                elif line.startswith(' '):
                    # Context line - advance
                    current_original_line += 1

                i += 1

            return '\n'.join(result_lines)
            
        except Exception as e:
            self.logger.log(f"❌ Manual diff application failed: {str(e)}")
            return None

    def _detect_change_type(self, old_text: str, new_text: str, file_path: str) -> str:
        """Detect the type of change requested"""
        old_lower = old_text.lower()
        new_lower = new_text.lower()
        
        # Additive indicators
        additive_keywords = ['add', 'include', 'incorporate', 'insert', 'create section', 'new section', 'best practices']
        if any(keyword in old_lower or keyword in new_lower for keyword in additive_keywords):
            return "ADDITIVE"
        
        # Corrective indicators  
        corrective_keywords = ['correct', 'fix', 'grammar', 'spelling', 'typo', 'misspell', 'wrong', 'error']
        if any(keyword in old_lower or keyword in new_lower for keyword in corrective_keywords):
            return "CORRECTIVE"
        
        # If new text is much longer than old text, likely additive
        if len(new_text.strip()) > len(old_text.strip()) * 2:
            return "ADDITIVE"
        
        # If similar length, likely corrective
        if abs(len(new_text.strip()) - len(old_text.strip())) < 50:
            return "CORRECTIVE"
        
        return "GENERAL"

    def _handle_additive_change(self, file_content: str, old_text: str, new_text: str, file_path: str) -> Optional[str]:
        """Handle additive changes by generating content and inserting it"""
        self.logger.log("🔨 Handling additive change - generating new content...")
        
        try:
            import anthropic
            client = anthropic.Anthropic(api_key=self.api_key)

            prompt = f"""**Instructions:**

Task: Add new content to the documentation file as requested.

Steps to complete:

1. Generate ONLY the new content that should be added to the documentation file
2. Maintain proper formatting, indentation, and markdown structure
3. Make content standalone - don't reference existing content in the file
4. Use Microsoft documentation standards

> [!IMPORTANT]
> Only create the new content - do not rewrite or modify existing content.
> Preserve markdown formatting, links, and code blocks as appropriate.
> Please ensure the changes align with Microsoft documentation standards.

File: {file_path}
Request: {old_text}
Content to add: {new_text}

Generate only the new content that should be added:"""

            message = client.messages.create(
                model="claude-3-5-haiku-20241022",
                max_tokens=2048,
                temperature=0.1,
                messages=[{"role": "user", "content": prompt}]
            )
            
            new_content = message.content[0].text.strip()
            
            # Find best insertion point in the file
            insertion_point = self._find_insertion_point(file_content, old_text, file_path)
            
            # Insert the new content
            lines = file_content.split('\n')
            lines.insert(insertion_point, '\n' + new_content + '\n')
            updated_content = '\n'.join(lines)
            
            # Count actual changes
            original_lines = file_content.split('\n')
            updated_lines = updated_content.split('\n')
            import difflib
            diff = list(difflib.unified_diff(original_lines, updated_lines, lineterm=''))
            changed_lines = len([line for line in diff if line.startswith('+')])
            
            self.logger.log(f"✅ Added new content ({changed_lines} lines added)")
            return updated_content
            
        except Exception as e:
            self.logger.log(f"❌ Error in additive change: {str(e)}")
            return None

    def _handle_corrective_change(self, file_content: str, old_text: str, new_text: str, file_path: str) -> Optional[str]:
        """Handle corrective changes by finding and fixing specific issues"""
        self.logger.log("🔍 Handling corrective change - finding specific issues...")
        
        try:
            import anthropic
            client = anthropic.Anthropic(api_key=self.api_key)

            prompt = f"""**Instructions:**

Task: Find and fix a specific issue in the documentation file.

Steps to complete:

1. Locate the exact text that needs to be corrected in the file
2. Provide the precise replacement text
3. Make minimal changes - fix only what needs to be fixed
4. Maintain existing formatting and structure

> [!IMPORTANT]
> Only make the specified correction - do not make additional changes.
> Preserve all markdown formatting, links, and code blocks.
> Please ensure the changes align with Microsoft documentation standards.

Issue: {old_text}
Fix: {new_text}
File: {file_path}

Return your response in this format:
OLD: [exact text to find]
NEW: [exact replacement text]

Be very specific - find the minimal text that needs changing. For example:
- If fixing "Microsft" → return OLD: Microsft, NEW: Microsoft
- If fixing grammar → return OLD: [the incorrect phrase], NEW: [corrected phrase]

Find the exact text to correct:"""

            message = client.messages.create(
                model="claude-3-5-haiku-20241022",
                max_tokens=1024,
                temperature=0.1,
                messages=[{"role": "user", "content": f"{prompt}\n\nFile content to search:\n{file_content}"}]
            )
            
            response = message.content[0].text.strip()
            
            # Parse the response to extract OLD and NEW
            old_match = None
            new_match = None
            
            for line in response.split('\n'):
                if line.startswith('OLD:'):
                    old_match = line[4:].strip()
                elif line.startswith('NEW:'):
                    new_match = line[4:].strip()
            
            if old_match and new_match and old_match in file_content:
                updated_content = file_content.replace(old_match, new_match)
                # Count changes
                original_lines = file_content.split('\n')
                updated_lines = updated_content.split('\n')
                import difflib
                diff = list(difflib.unified_diff(original_lines, updated_lines, lineterm=''))
                changed_lines = len([line for line in diff if line.startswith('+') or line.startswith('-')])
                self.logger.log(f"✅ Corrective change successful ({changed_lines} lines affected)")
                return updated_content
            else:
                self.logger.log(f"⚠️ Could not find exact text to correct")
                return None
                
        except Exception as e:
            self.logger.log(f"❌ Error in corrective change: {str(e)}")
            return None

    def _find_insertion_point(self, file_content: str, context: str, file_path: str) -> int:
        """Find the best place to insert new content"""
        lines = file_content.split('\n')
        
        # For markdown files, try to find a good section to add after
        if file_path.endswith('.md'):
            # Look for existing sections
            for i, line in enumerate(lines):
                if line.startswith('#') and i < len(lines) - 1:
                    # Insert after this section
                    continue
            
            # If no good sections found, add at the end
            return len(lines)
        
        # For other files, add at the end
        return len(lines)

    def _handle_general_change(self, file_content: str, old_text: str, new_text: str, file_path: str) -> Optional[str]:
        """Handle general changes with enhanced targeting"""
        self.logger.log("🎯 Handling general change with enhanced targeting...")
        
        max_retries = 3
        base_delay = 2

        for attempt in range(max_retries):
            try:
                import anthropic
                client = anthropic.Anthropic(api_key=self.api_key)

                prompt = f"""**Instructions:**

Task: Update the documentation file with the specific change requested.

Steps to complete:

1. Locate the specific section that needs changing in the file
2. Make ONLY the requested change
3. Maintain the existing formatting, indentation, and markdown structure
4. Preserve everything else exactly as-is
5. Return the complete updated file

> [!IMPORTANT]
> Only make the specified change - do not rewrite or reorganize content.
> Preserve all markdown formatting, links, and code blocks.
> Please ensure the changes align with Microsoft documentation standards.
> Make the SMALLEST possible change.

File: {file_path}
Change needed: {old_text}
New content: {new_text}

Current file content:
{file_content}"""

                message = client.messages.create(
                    model="claude-3-5-haiku-20241022",
                    max_tokens=4096,
                    temperature=0.1,
                    messages=[{"role": "user", "content": prompt}]
                )

                updated_content = message.content[0].text

                if new_text.strip() in updated_content:
                    original_lines = file_content.split('\n')
                    updated_lines = updated_content.split('\n')
                    
                    import difflib
                    diff = list(difflib.unified_diff(original_lines, updated_lines, lineterm=''))
                    changed_lines = len([line for line in diff if line.startswith('+') or line.startswith('-')])
                    
                    if changed_lines > 30:
                        self.logger.log(f"⚠️ Change affected {changed_lines} lines - may be too broad")
                    else:
                        self.logger.log(f"✅ General change successful ({changed_lines} lines affected)")
                    
                    return updated_content
                else:
                    self.logger.log("⚠️ New text not found in result")
                    return None

            except Exception as e:
                if attempt < max_retries - 1:
                    delay = base_delay * (2 ** attempt)
                    self.logger.log(f"⚠️ Retry {attempt + 1}/{max_retries} after {delay}s...")
                    time.sleep(delay)
                    continue
                else:
                    self.logger.log(f"❌ Error in general change: {str(e)}")
                    return None

        return None


class ChatGPTProvider(AIProvider):
    """ChatGPT/GPT-4 provider using OpenAI API"""

    def make_change(self, file_content: str, old_text: str, new_text: str, file_path: str, custom_instructions: str = None) -> Optional[str]:
        """Make smart, targeted changes based on reference text and suggestions

        Args:
            file_content: Full file content
            old_text: Reference text (what user is talking about - may not be exact)
            new_text: Suggested changes (what user wants to see)
            file_path: Path to file being modified
            custom_instructions: Optional custom instructions from user
        """

        # Step 1: Try direct string replacement if reference text is exact match
        if old_text and old_text.strip() in file_content:
            self.logger.log("✅ Making direct string replacement (reference text found exactly)")
            updated_content = file_content.replace(old_text.strip(), new_text.strip())
            if updated_content != file_content:
                original_lines = file_content.split('\n')
                updated_lines = updated_content.split('\n')
                import difflib
                diff = list(difflib.unified_diff(original_lines, updated_lines, lineterm=''))
                changed_lines = len([line for line in diff if line.startswith('+') or line.startswith('-')])
                self.logger.log(f"✅ Direct replacement successful ({changed_lines} lines changed)")
                return updated_content

        # Step 2: Use AI to generate full document with targeted changes
        self.logger.log("📝 Using AI to modify the document...")
        return self._generate_updated_document_chatgpt(file_content, old_text, new_text, file_path, custom_instructions)

    def _generate_updated_document_chatgpt(self, file_content: str, old_text: str, new_text: str, file_path: str, custom_instructions: str = None) -> Optional[str]:
        """Generate updated document content using ChatGPT"""
        
        try:
            import openai
            client = openai.OpenAI(api_key=self.api_key)

            # Build custom instructions text
            if custom_instructions and custom_instructions.strip():
                custom_instructions_text = f"""

**Additional Custom Instructions:**
{custom_instructions.strip()}

"""
            else:
                custom_instructions_text = ""

            # Handle blank new_text field with dynamic prompt
            if not new_text or not new_text.strip():
                # General improvement request when new text is blank
                prompt = f"""**Instructions:**

Task: Review and improve the documentation file based on the reference context provided.

Steps to complete:

1. Review the current file content below
2. Look at the reference context: "{old_text}"
3. Improve the relevant sections based on Microsoft documentation standards
4. Maintain the existing formatting, indentation, and markdown structure
5. Return the complete updated file content

> [!IMPORTANT]
> OUTPUT REQUIREMENTS:
> - Return ONLY the complete file content - no explanatory text, dialog, or commentary
> - Do NOT add any text before or after the file content
> - Do NOT wrap output in markdown code blocks (```), just return the raw content
> - Return the ENTIRE document - no truncation, no placeholders like [Rest of the document here...]
> - Every single line of the original document must be present in your response
> - Focus on areas related to: {old_text}
> - Preserve all markdown formatting, links, and code blocks exactly
> - Please ensure improvements align with Microsoft documentation standards
> - Only make improvements - do not remove existing content unless it's redundant

{custom_instructions_text}

**Current File Content:**
```
{file_content}
```

**Context for improvements:**
```
{old_text}
```

Return the complete updated file content now (NO explanatory text):"""

            else:
                # Specific replacement when new text is provided  
                prompt = f"""**Instructions:**

Task: Update the documentation file with the changes requested.

Steps to complete:

1. Review the current file content below
2. Find the reference text that needs to be updated
3. Replace it with the suggested new content
4. Maintain the existing formatting, indentation, and markdown structure
5. Return the complete updated file content

> [!IMPORTANT]
> OUTPUT REQUIREMENTS:
> - Return ONLY the complete file content - no explanatory text, dialog, or commentary
> - Do NOT add any text before or after the file content
> - Do NOT wrap output in markdown code blocks (```), just return the raw content
> - Return the ENTIRE document - no truncation, no placeholders like [Rest of the document here...]
> - Every single line of the original document must be present in your response
> - Only replace the specified text - do not make additional changes
> - Preserve all markdown formatting, links, and code blocks exactly
> - If the current text cannot be found exactly, search for similar text
> - Please ensure the changes align with Microsoft documentation standards
> - Do not remove any text unless the reference or suggested guidance indicates to do so

{custom_instructions_text}

**Current File Content:**
```
{file_content}
```

**Reference text to find and replace:**
```
{old_text}
```

**Suggested new content:**
```
{new_text}
```

Return the complete updated file content now (NO explanatory text):"""

            response = client.chat.completions.create(
                model="gpt-4-turbo-preview",
                messages=[
                    {"role": "system", "content": "You are a document editor. Return ONLY the complete updated file content - no explanatory text, no dialog, no code blocks, no truncation, no placeholders. Output must be the raw complete file content with requested changes."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1
            )
            
            updated_content = response.choices[0].message.content.strip()
            
            # Clean up code blocks if AI wrapped it
            if updated_content.startswith('```'):
                updated_content = '\n'.join(updated_content.split('\n')[1:-1])
            
            # Basic validation - ensure content was actually changed
            if updated_content and updated_content != file_content:
                original_lines = file_content.split('\n')
                updated_lines = updated_content.split('\n')
                import difflib
                diff = list(difflib.unified_diff(original_lines, updated_lines, lineterm=''))
                changed_lines = len([line for line in diff if line.startswith('+') or line.startswith('-')])
                
                self.logger.log(f"✅ ChatGPT document update successful ({changed_lines} lines affected)")
                return updated_content
            else:
                self.logger.log("⚠️ No changes detected in AI response")
                return None
                
        except Exception as e:
            self.logger.log(f"❌ Error generating updated document with ChatGPT: {str(e)}")
            return None

    def _generate_with_context_window(self, file_content: str, old_text: str, new_text: str, file_path: str) -> Optional[str]:
        """Use context window approach - AI only sees/modifies a small section

        This physically prevents AI from rewriting entire file by only giving it
        the relevant section to work with.

        Args:
            file_content: Full file content
            old_text: Reference text (guides where to look)
            new_text: Suggestions (what to change to)
        """
        try:
            import difflib

            # Step 1: Find where the reference text is located
            lines = file_content.split('\n')
            ref_lines = old_text.split('\n') if old_text else []

            # Find best matching location for reference text
            start_line = 0
            if ref_lines:
                matcher = difflib.SequenceMatcher(None, ref_lines, lines)
                match = matcher.find_longest_match(0, len(ref_lines), 0, len(lines))
                if match.size > 0:
                    start_line = match.b
                    self.logger.log(f"📍 Found reference area at line {start_line + 1}")
                else:
                    self.logger.log("📍 Reference text not found, using beginning of file")

            # Step 2: Extract context window (30 lines before, 30 lines after)
            window_before = 30
            window_after = 30

            window_start = max(0, start_line - window_before)
            window_end = min(len(lines), start_line + len(ref_lines) + window_after)

            context_window = lines[window_start:window_end]
            self.logger.log(f"📄 Context window: lines {window_start + 1} to {window_end} ({len(context_window)} lines)")
            self.logger.log(f"   (AI can only modify this section, rest of file is protected)")

            # Step 3: Have AI modify only the context window
            context_text = '\n'.join(context_window)

            import openai
            client = openai.OpenAI(api_key=self.api_key)

            prompt = f"""You are helping modify a small section of a documentation file. You can ONLY modify the section provided below.

File: {file_path}
Section location: Lines {window_start + 1} to {window_end}

REFERENCE TEXT (what user is referring to):
{old_text}

SUGGESTED CHANGES (what user wants):
{new_text}

SECTION TO MODIFY:
```
{context_text}
```

INSTRUCTIONS:
1. Understand the user's INTENT from the reference and suggestions:
   - "add/include/incorporate a section" = Add a COMPLETE NEW SECTION with heading and full content
   - "update/modify/change X" = Modify existing text X intelligently
   - "fix/correct" = Make specific correction only
   - Be generous with new content when asked to add something

2. For ADDING content (sections, paragraphs, examples):
   - Create complete, well-written content (not just stubs or brief additions)
   - Add proper markdown headers (## Best Practices, ### Example, etc.)
   - Place it logically (end of section, before ## Related content, etc.)
   - Match the document's writing style and tone

3. For MODIFYING content:
   - Change only what's requested
   - Leave everything else exactly as-is

4. Return the ENTIRE section (all {len(context_window)} lines) with your changes
5. No explanations - just the modified section

OUTPUT THE COMPLETE MODIFIED SECTION:"""

            response = client.chat.completions.create(
                model="gpt-4-turbo-preview",
                messages=[
                    {"role": "system", "content": "You make precise, targeted edits to documentation sections. Return only the modified text, nothing else."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1
            )

            modified_window = response.choices[0].message.content.strip()

            # Clean up code blocks if AI wrapped it
            if modified_window.startswith('```'):
                modified_window = '\n'.join(modified_window.split('\n')[1:-1])

            # Step 4: Replace the context window in the full file
            modified_lines = modified_window.split('\n')
            result_lines = lines[:window_start] + modified_lines + lines[window_end:]
            updated_content = '\n'.join(result_lines)

            # Verify change is minimal
            diff = list(difflib.unified_diff(lines, result_lines, lineterm=''))
            changed_lines = len([line for line in diff if line.startswith('+') or line.startswith('-')])

            self.logger.log(f"✅ Context window approach successful ({changed_lines} lines changed)")

            # Ensure we actually made changes
            if updated_content == file_content:
                self.logger.log("⚠️ No changes detected, falling back to full-document approach")
                return self._generate_updated_document_chatgpt(file_content, old_text, new_text, file_path)

            return updated_content

        except Exception as e:
            self.logger.log(f"❌ Error with context window approach: {str(e)}")
            self.logger.log("⚠️ Falling back to full-document approach")
            return self._generate_updated_document_chatgpt(file_content, old_text, new_text, file_path)

    def _validate_diff_patch(self, diff_patch: str, original_content: str, old_text: str, new_text: str) -> bool:
        """Validate that the AI-generated diff is safe and appropriate"""
        try:
            # Check for common problems
            lines = diff_patch.split('\n')

            # Problem 0: Check for proper diff structure
            has_hunk_header = any(line.startswith('@@') for line in lines)
            if not has_hunk_header:
                self.logger.log("❌ Invalid diff: Missing @@ hunk headers")
                return False

            # Problem 1: Check for duplicate +++ lines
            plus_count = sum(1 for line in lines if line.startswith('+++'))
            if plus_count > 1:
                self.logger.log("❌ Invalid diff: Multiple +++ lines detected")
                return False

            # Problem 2: Check for removal of metadata (title, author, etc.)
            for line in lines:
                if line.startswith('-') and not line.startswith('---'):
                    removed_content = line[1:].strip()
                    # Check if removing metadata
                    if any(keyword in removed_content.lower() for keyword in ['title:', 'author:', 'description:', 'ms.author:', 'ms.date:']):
                        self.logger.log(f"❌ Invalid diff: Attempting to remove metadata: {removed_content}")
                        return False

            # Problem 3: Check if diff is too large (indicates rewrite)
            removed_lines = len([line for line in lines if line.startswith('-') and not line.startswith('---')])
            added_lines = len([line for line in lines if line.startswith('+') and not line.startswith('+++')])

            if removed_lines > 10:  # Too many removals for an additive change
                self.logger.log(f"❌ Invalid diff: Too many removals ({removed_lines} lines)")
                return False

            return True

        except Exception as e:
            self.logger.log(f"❌ Error validating diff: {str(e)}")
            return False
    
    def _create_safe_diff(self, file_content: str, old_text: str, new_text: str, file_path: str) -> Optional[str]:
        """Create a safer, simpler diff that just adds content without removing anything"""
        try:
            # Strategy: Find the best location to add the new content and insert it there
            lines = file_content.split('\n')
            
            # Look for common insertion points for adding sections
            insertion_point = self._find_safe_insertion_point(lines, old_text, new_text)
            
            if insertion_point is None:
                self.logger.log("⚠️ Could not find safe insertion point")
                return None
            
            # Insert the new content at the found location
            new_lines = lines[:insertion_point] + [new_text.strip(), ''] + lines[insertion_point:]
            updated_content = '\n'.join(new_lines)
            
            self.logger.log(f"✅ Created safe diff - inserting content at line {insertion_point}")
            return updated_content
            
        except Exception as e:
            self.logger.log(f"❌ Error creating safe diff: {str(e)}")
            return None
    
    def _find_safe_insertion_point(self, lines: list, old_text: str, new_text: str) -> Optional[int]:
        """Find the best place to insert new content safely"""
        try:
            # Look for section headers to insert after
            for i, line in enumerate(lines):
                # If the old_text contains context about where to insert
                if old_text and old_text.lower().strip() in line.lower():
                    # Insert after this line
                    return i + 1
                
                # Look for pattern where we should insert a new section
                # Insert before conclusion, examples, or other sections
                if line.strip().startswith('##') and any(keyword in line.lower() for keyword in ['example', 'conclusion', 'summary', 'next steps']):
                    return i
            
            # If no specific location found, insert before the last section
            for i in range(len(lines) - 1, -1, -1):
                if lines[i].strip().startswith('##'):
                    return i
            
            # Last resort: insert at 80% through the document
            return int(len(lines) * 0.8)
            
        except Exception:
            return None

    def _apply_diff_patch_chatgpt(self, original_content: str, diff_patch: str, file_path: str) -> Optional[str]:
        """Apply a unified diff patch to the original content"""
        try:
            import tempfile
            import subprocess
            import os
            
            # Create temporary files
            with tempfile.TemporaryDirectory() as temp_dir:
                # Write original content to temp file
                original_file = os.path.join(temp_dir, "original.txt")
                with open(original_file, 'w', encoding='utf-8') as f:
                    f.write(original_content)
                
                # Write diff patch to temp file
                patch_file = os.path.join(temp_dir, "changes.patch")
                with open(patch_file, 'w', encoding='utf-8') as f:
                    f.write(diff_patch)
                
                # Apply patch using git apply
                try:
                    subprocess.run(['git', 'apply', '--verbose', patch_file], 
                                 cwd=temp_dir, check=True, capture_output=True, text=True)
                    
                    # Read the result
                    with open(original_file, 'r', encoding='utf-8') as f:
                        return f.read()
                        
                except subprocess.CalledProcessError:
                    # Fallback to manual patch application
                    self.logger.log("📝 Git apply failed, trying manual diff application...")
                    return self._manual_diff_apply_chatgpt(original_content, diff_patch)
                    
        except Exception as e:
            self.logger.log(f"⚠️ ChatGPT patch application failed: {str(e)}")
            return self._manual_diff_apply_chatgpt(original_content, diff_patch)

    def _manual_diff_apply_chatgpt(self, original_content: str, diff_patch: str) -> Optional[str]:
        """Manually apply a diff patch when git apply fails"""
        try:
            # Detect original line ending style
            has_crlf = '\r\n' in original_content

            original_lines = original_content.split('\n')
            result_lines = original_lines.copy()

            # Parse the diff patch
            diff_lines = diff_patch.split('\n')
            current_original_line = 0

            i = 0
            while i < len(diff_lines):
                line = diff_lines[i]

                # Look for @@ headers
                if line.startswith('@@'):
                    # Extract line numbers: @@ -start,count +start,count @@
                    parts = line.split()
                    if len(parts) >= 3:
                        old_info = parts[1][1:]  # Remove the -
                        if ',' in old_info:
                            start_line = int(old_info.split(',')[0]) - 1  # Convert to 0-based
                        else:
                            start_line = int(old_info) - 1

                        current_original_line = start_line
                    i += 1
                    continue

                # Skip diff headers (must check before processing -/+ lines)
                if line.startswith('---') or line.startswith('+++'):
                    i += 1
                    continue

                # Process diff lines
                if line.startswith('-'):
                    # Remove line
                    if current_original_line < len(result_lines):
                        del result_lines[current_original_line]
                elif line.startswith('+'):
                    # Add line
                    new_line = line[1:]  # Remove the +
                    # If original had CRLF and this line doesn't have \r, add it
                    if has_crlf and not new_line.endswith('\r'):
                        new_line = new_line + '\r'
                    result_lines.insert(current_original_line, new_line)
                    current_original_line += 1
                elif line.startswith(' '):
                    # Context line - advance
                    current_original_line += 1

                i += 1

            return '\n'.join(result_lines)
            
        except Exception as e:
            self.logger.log(f"❌ ChatGPT manual diff application failed: {str(e)}")
            return None

    def _detect_change_type(self, old_text: str, new_text: str, file_path: str) -> str:
        """Detect the type of change requested"""
        old_lower = old_text.lower()
        new_lower = new_text.lower()
        
        # Additive indicators
        additive_keywords = ['add', 'include', 'incorporate', 'insert', 'create section', 'new section', 'best practices']
        if any(keyword in old_lower or keyword in new_lower for keyword in additive_keywords):
            return "ADDITIVE"
        
        # Corrective indicators  
        corrective_keywords = ['correct', 'fix', 'grammar', 'spelling', 'typo', 'misspell', 'wrong', 'error']
        if any(keyword in old_lower or keyword in new_lower for keyword in corrective_keywords):
            return "CORRECTIVE"
        
        # If new text is much longer than old text, likely additive
        if len(new_text.strip()) > len(old_text.strip()) * 2:
            return "ADDITIVE"
        
        # If similar length, likely corrective
        if abs(len(new_text.strip()) - len(old_text.strip())) < 50:
            return "CORRECTIVE"
        
        return "GENERAL"

    def _handle_additive_change_chatgpt(self, file_content: str, old_text: str, new_text: str, file_path: str) -> Optional[str]:
        """Handle additive changes using ChatGPT"""
        self.logger.log("🔨 ChatGPT handling additive change - generating new content...")
        
        try:
            import openai
            client = openai.OpenAI(api_key=self.api_key)

            prompt = f"""**Instructions:**

Task: Add new content to the documentation file as requested.

Steps to complete:

1. Generate ONLY the new content that should be added to the documentation file
2. Maintain proper formatting, indentation, and markdown structure
3. Make content standalone - don't reference existing content in the file
4. Use Microsoft documentation standards

> [!IMPORTANT]
> Only create the new content - do not rewrite or modify existing content.
> Preserve markdown formatting, links, and code blocks as appropriate.
> Please ensure the changes align with Microsoft documentation standards.

File: {file_path}
Request: {old_text}
Content to add: {new_text}

Generate only the new content that should be added:"""

            response = client.chat.completions.create(
                model="gpt-4-turbo-preview",
                messages=[
                    {"role": "system", "content": "You are a content generator. Generate only new content, never rewrite existing content."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1
            )
            
            new_content = response.choices[0].message.content.strip()
            
            # Find best insertion point and insert
            insertion_point = self._find_insertion_point(file_content, old_text, file_path)
            lines = file_content.split('\n')
            lines.insert(insertion_point, '\n' + new_content + '\n')
            updated_content = '\n'.join(lines)
            
            # Count actual changes
            original_lines = file_content.split('\n')
            updated_lines = updated_content.split('\n')
            import difflib
            diff = list(difflib.unified_diff(original_lines, updated_lines, lineterm=''))
            changed_lines = len([line for line in diff if line.startswith('+')])
            
            self.logger.log(f"✅ ChatGPT added new content ({changed_lines} lines added)")
            return updated_content
            
        except Exception as e:
            self.logger.log(f"❌ Error in ChatGPT additive change: {str(e)}")
            return None

    def _handle_corrective_change_chatgpt(self, file_content: str, old_text: str, new_text: str, file_path: str) -> Optional[str]:
        """Handle corrective changes using ChatGPT"""
        self.logger.log("🔍 ChatGPT handling corrective change - finding specific issues...")
        
        try:
            import openai
            client = openai.OpenAI(api_key=self.api_key)

            prompt = f"""**Instructions:**

Task: Find and fix a specific issue in the documentation file.

Steps to complete:

1. Locate the exact text that needs to be corrected in the file
2. Provide the precise replacement text
3. Make minimal changes - fix only what needs to be fixed
4. Maintain existing formatting and structure

> [!IMPORTANT]
> Only make the specified correction - do not make additional changes.
> Preserve all markdown formatting, links, and code blocks.
> Please ensure the changes align with Microsoft documentation standards.

Issue: {old_text}
Fix: {new_text}
File: {file_path}

Return your response in this format:
OLD: [exact text to find]
NEW: [exact replacement text]

Be very specific - find the minimal text that needs changing. For example:
- If fixing "Microsft" → return OLD: Microsft, NEW: Microsoft
- If fixing grammar → return OLD: [the incorrect phrase], NEW: [corrected phrase]

File content to search:
{file_content}

Find the exact text to correct:"""

            response = client.chat.completions.create(
                model="gpt-4-turbo-preview",
                messages=[
                    {"role": "system", "content": "You are a precise error detector. Find exact text that needs correction."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1
            )
            
            response_text = response.choices[0].message.content.strip()
            
            # Parse OLD and NEW
            old_match = None
            new_match = None
            
            for line in response_text.split('\n'):
                if line.startswith('OLD:'):
                    old_match = line[4:].strip()
                elif line.startswith('NEW:'):
                    new_match = line[4:].strip()
            
            if old_match and new_match and old_match in file_content:
                updated_content = file_content.replace(old_match, new_match)
                original_lines = file_content.split('\n')
                updated_lines = updated_content.split('\n')
                import difflib
                diff = list(difflib.unified_diff(original_lines, updated_lines, lineterm=''))
                changed_lines = len([line for line in diff if line.startswith('+') or line.startswith('-')])
                self.logger.log(f"✅ ChatGPT corrective change successful ({changed_lines} lines affected)")
                return updated_content
            else:
                self.logger.log(f"⚠️ ChatGPT could not find exact text to correct")
                return None
                
        except Exception as e:
            self.logger.log(f"❌ Error in ChatGPT corrective change: {str(e)}")
            return None

    def _handle_general_change_chatgpt(self, file_content: str, old_text: str, new_text: str, file_path: str) -> Optional[str]:
        """Handle general changes using ChatGPT with enhanced targeting"""
        self.logger.log("🎯 ChatGPT handling general change with enhanced targeting...")
        
        max_retries = 3
        base_delay = 2

        for attempt in range(max_retries):
            try:
                import openai
                client = openai.OpenAI(api_key=self.api_key)

                prompt = f"""You are helping make a specific text change in a documentation file.

File: {file_path}
Change needed: {old_text}
New content: {new_text}

CRITICAL: Make the SMALLEST possible change. Do not rewrite or reorganize content.

Your task:
1. Find the specific section that needs changing
2. Make ONLY that change
3. Preserve everything else exactly as-is
4. Return the complete updated file

Current file content:
{file_content}"""

                response = client.chat.completions.create(
                    model="gpt-4-turbo-preview",
                    messages=[
                        {"role": "system", "content": "You are a precise file editor. Make minimal targeted changes only."},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=0.1
                )

                updated_content = response.choices[0].message.content

                if new_text.strip() in updated_content:
                    original_lines = file_content.split('\n')
                    updated_lines = updated_content.split('\n')
                    
                    import difflib
                    diff = list(difflib.unified_diff(original_lines, updated_lines, lineterm=''))
                    changed_lines = len([line for line in diff if line.startswith('+') or line.startswith('-')])
                    
                    if changed_lines > 30:
                        self.logger.log(f"⚠️ ChatGPT change affected {changed_lines} lines - may be too broad")
                    else:
                        self.logger.log(f"✅ ChatGPT general change successful ({changed_lines} lines affected)")
                    
                    return updated_content
                else:
                    self.logger.log("⚠️ ChatGPT: New text not found in result")
                    return None

            except Exception as e:
                if attempt < max_retries - 1:
                    delay = base_delay * (2 ** attempt)
                    self.logger.log(f"⚠️ ChatGPT retry {attempt + 1}/{max_retries} after {delay}s...")
                    time.sleep(delay)
                    continue
                else:
                    self.logger.log(f"❌ Error in ChatGPT general change: {str(e)}")
                    return None

        return None

    def _find_insertion_point(self, file_content: str, context: str, file_path: str) -> int:
        """Find the best place to insert new content"""
        lines = file_content.split('\n')
        
        # For markdown files, try to find a good section to add after
        if file_path.endswith('.md'):
            # Look for existing sections
            for i, line in enumerate(lines):
                if line.startswith('#') and i < len(lines) - 1:
                    # Insert after this section
                    continue
            
            # If no good sections found, add at the end
            return len(lines)
        
        # For other files, add at the end
        return len(lines)


class GitHubCopilotProvider(AIProvider):
    """GitHub Copilot provider using GitHub Models API"""

    def make_change(self, file_content: str, old_text: str, new_text: str, file_path: str, custom_instructions: str = None) -> Optional[str]:
        """Use diff-based approach for surgical edits"""
        
        # Step 1: Always try direct string replacement first (most accurate)
        if old_text and old_text.strip() in file_content:
            self.logger.log("✅ Making direct string replacement (most precise)")
            updated_content = file_content.replace(old_text.strip(), new_text.strip())
            if updated_content != file_content:
                original_lines = file_content.split('\n')
                updated_lines = updated_content.split('\n')
                import difflib
                diff = list(difflib.unified_diff(original_lines, updated_lines, lineterm=''))
                changed_lines = len([line for line in diff if line.startswith('+') or line.startswith('-')])
                self.logger.log(f"✅ Direct replacement successful ({changed_lines} lines changed)")
                return updated_content
        
        # Step 2: Use AI to generate full document with targeted changes
        self.logger.log("📝 Using GitHub Copilot to modify the document...")
        return self._generate_updated_document_copilot(file_content, old_text, new_text, file_path, custom_instructions)

    def _generate_updated_document_copilot(self, file_content: str, old_text: str, new_text: str, file_path: str, custom_instructions: str = None) -> Optional[str]:
        """Generate updated document content using GitHub Copilot"""
        
        try:
            import requests
            
            url = "https://models.inference.ai.azure.com/chat/completions"
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            }

            # Build custom instructions text
            if custom_instructions and custom_instructions.strip():
                custom_instructions_text = f"""

**Additional Custom Instructions:**
{custom_instructions.strip()}

"""
            else:
                custom_instructions_text = ""

            # Handle blank new_text field with dynamic prompt
            if not new_text or not new_text.strip():
                # General improvement request when new text is blank
                prompt = f"""**Instructions:**

Task: Review and improve the documentation file based on the reference context provided.

Steps to complete:

1. Review the current file content below
2. Look at the reference context: "{old_text}"
3. Improve the relevant sections based on Microsoft documentation standards
4. Maintain the existing formatting, indentation, and markdown structure
5. Return the complete updated file content

> [!IMPORTANT]
> OUTPUT REQUIREMENTS:
> - Return ONLY the complete file content - no explanatory text, dialog, or commentary
> - Do NOT add any text before or after the file content
> - Do NOT wrap output in markdown code blocks (```), just return the raw content
> - Return the ENTIRE document - no truncation, no placeholders like [Rest of the document here...]
> - Every single line of the original document must be present in your response
> - Focus on areas related to: {old_text}
> - Preserve all markdown formatting, links, and code blocks exactly
> - Please ensure improvements align with Microsoft documentation standards
> - Only make improvements - do not remove existing content unless it's redundant

{custom_instructions_text}

**Current File Content:**
```
{file_content}
```

**Context for improvements:**
```
{old_text}
```

Return the complete updated file content now (NO explanatory text):"""

            else:
                # Specific replacement when new text is provided
                prompt = f"""**Instructions:**

Task: Update the documentation file with the changes requested.

Steps to complete:

1. Review the current file content below
2. Find the reference text that needs to be updated
3. Replace it with the suggested new content
4. Maintain the existing formatting, indentation, and markdown structure
5. Return the complete updated file content

> [!IMPORTANT]
> OUTPUT REQUIREMENTS:
> - Return ONLY the complete file content - no explanatory text, dialog, or commentary
> - Do NOT add any text before or after the file content
> - Do NOT wrap output in markdown code blocks (```), just return the raw content
> - Return the ENTIRE document - no truncation, no placeholders like [Rest of the document here...]
> - Every single line of the original document must be present in your response
> - Only replace the specified text - do not make additional changes
> - Preserve all markdown formatting, links, and code blocks exactly
> - If the current text cannot be found exactly, search for similar text
> - Please ensure the changes align with Microsoft documentation standards
> - Do not remove any text unless the reference or suggested guidance indicates to do so

{custom_instructions_text}

**Current File Content:**
```
{file_content}
```

**Reference text to find and replace:**
```
{old_text}
```

**Suggested new content:**
```
{new_text}
```

Return the complete updated file content now (NO explanatory text):"""

            data = {
                "messages": [
                    {"role": "system", "content": "You are a document editor. Return ONLY the complete updated file content - no explanatory text, no dialog, no code blocks, no truncation, no placeholders. Output must be the raw complete file content with requested changes."},
                    {"role": "user", "content": prompt}
                ],
                "model": "gpt-4o",
                "temperature": 0.1,
                "max_tokens": 4096
            }
            
            response = requests.post(url, headers=headers, json=data, timeout=60)
            response.raise_for_status()
            
            result = response.json()
            updated_content = result['choices'][0]['message']['content'].strip()
            
            # Clean up code blocks if AI wrapped it
            if updated_content.startswith('```'):
                updated_content = '\n'.join(updated_content.split('\n')[1:-1])
            
            # Basic validation - ensure content was actually changed
            if updated_content and updated_content != file_content:
                original_lines = file_content.split('\n')
                updated_lines = updated_content.split('\n')
                import difflib
                diff = list(difflib.unified_diff(original_lines, updated_lines, lineterm=''))
                changed_lines = len([line for line in diff if line.startswith('+') or line.startswith('-')])
                
                self.logger.log(f"✅ GitHub Copilot document update successful ({changed_lines} lines affected)")
                return updated_content
            else:
                self.logger.log("⚠️ No changes detected in AI response")
                return None
                
        except Exception as e:
            self.logger.log(f"❌ Error generating updated document with GitHub Copilot: {str(e)}")
            return None

    def _validate_diff_patch(self, diff_patch: str, original_content: str, old_text: str, new_text: str) -> bool:
        """Validate that the AI-generated diff is safe and appropriate"""
        try:
            # Check for common problems
            lines = diff_patch.split('\n')

            # Problem 0: Check for proper diff structure
            has_hunk_header = any(line.startswith('@@') for line in lines)
            if not has_hunk_header:
                self.logger.log("❌ Invalid diff: Missing @@ hunk headers")
                return False

            # Problem 1: Check for duplicate +++ lines
            plus_count = sum(1 for line in lines if line.startswith('+++'))
            if plus_count > 1:
                self.logger.log("❌ Invalid diff: Multiple +++ lines detected")
                return False

            # Problem 2: Check for removal of metadata (title, author, etc.)
            for line in lines:
                if line.startswith('-') and not line.startswith('---'):
                    removed_content = line[1:].strip()
                    # Check if removing metadata
                    if any(keyword in removed_content.lower() for keyword in ['title:', 'author:', 'description:', 'ms.author:', 'ms.date:']):
                        self.logger.log(f"❌ Invalid diff: Attempting to remove metadata: {removed_content}")
                        return False

            # Problem 3: Check if diff is too large (indicates rewrite)
            removed_lines = len([line for line in lines if line.startswith('-') and not line.startswith('---')])
            added_lines = len([line for line in lines if line.startswith('+') and not line.startswith('+++')])

            if removed_lines > 10:  # Too many removals for an additive change
                self.logger.log(f"❌ Invalid diff: Too many removals ({removed_lines} lines)")
                return False

            return True

        except Exception as e:
            self.logger.log(f"❌ Error validating diff: {str(e)}")
            return False
    
    def _create_safe_diff(self, file_content: str, old_text: str, new_text: str, file_path: str) -> Optional[str]:
        """Create a safer, simpler diff that just adds content without removing anything"""
        try:
            # Strategy: Find the best location to add the new content and insert it there
            lines = file_content.split('\n')
            
            # Look for common insertion points for adding sections
            insertion_point = self._find_safe_insertion_point(lines, old_text, new_text)
            
            if insertion_point is None:
                self.logger.log("⚠️ Could not find safe insertion point")
                return None
            
            # Insert the new content at the found location
            new_lines = lines[:insertion_point] + [new_text.strip(), ''] + lines[insertion_point:]
            updated_content = '\n'.join(new_lines)
            
            self.logger.log(f"✅ Created safe diff - inserting content at line {insertion_point}")
            return updated_content
            
        except Exception as e:
            self.logger.log(f"❌ Error creating safe diff: {str(e)}")
            return None
    
    def _find_safe_insertion_point(self, lines: list, old_text: str, new_text: str) -> Optional[int]:
        """Find the best place to insert new content safely"""
        try:
            # Look for section headers to insert after
            for i, line in enumerate(lines):
                # If the old_text contains context about where to insert
                if old_text and old_text.lower().strip() in line.lower():
                    # Insert after this line
                    return i + 1
                
                # Look for pattern where we should insert a new section
                # Insert before conclusion, examples, or other sections
                if line.strip().startswith('##') and any(keyword in line.lower() for keyword in ['example', 'conclusion', 'summary', 'next steps']):
                    return i
            
            # If no specific location found, insert before the last section
            for i in range(len(lines) - 1, -1, -1):
                if lines[i].strip().startswith('##'):
                    return i
            
            # Last resort: insert at 80% through the document
            return int(len(lines) * 0.8)
            
        except Exception:
            return None

    def _apply_diff_patch_copilot(self, original_content: str, diff_patch: str, file_path: str) -> Optional[str]:
        """Apply a unified diff patch to the original content"""
        try:
            import tempfile
            import subprocess
            import os
            
            # Create temporary files
            with tempfile.TemporaryDirectory() as temp_dir:
                # Write original content to temp file
                original_file = os.path.join(temp_dir, "original.txt")
                with open(original_file, 'w', encoding='utf-8') as f:
                    f.write(original_content)
                
                # Write diff patch to temp file
                patch_file = os.path.join(temp_dir, "changes.patch")
                with open(patch_file, 'w', encoding='utf-8') as f:
                    f.write(diff_patch)
                
                # Apply patch using git apply
                try:
                    subprocess.run(['git', 'apply', '--verbose', patch_file], 
                                 cwd=temp_dir, check=True, capture_output=True, text=True)
                    
                    # Read the result
                    with open(original_file, 'r', encoding='utf-8') as f:
                        return f.read()
                        
                except subprocess.CalledProcessError:
                    # Fallback to manual patch application
                    self.logger.log("📝 Git apply failed, trying manual diff application...")
                    return self._manual_diff_apply_copilot(original_content, diff_patch)
                    
        except Exception as e:
            self.logger.log(f"⚠️ GitHub Copilot patch application failed: {str(e)}")
            return self._manual_diff_apply_copilot(original_content, diff_patch)

    def _manual_diff_apply_copilot(self, original_content: str, diff_patch: str) -> Optional[str]:
        """Manually apply a diff patch when git apply fails"""
        try:
            # Detect original line ending style
            has_crlf = '\r\n' in original_content

            original_lines = original_content.split('\n')
            result_lines = original_lines.copy()

            # Parse the diff patch
            diff_lines = diff_patch.split('\n')
            current_original_line = 0

            i = 0
            while i < len(diff_lines):
                line = diff_lines[i]

                # Look for @@ headers
                if line.startswith('@@'):
                    # Extract line numbers: @@ -start,count +start,count @@
                    parts = line.split()
                    if len(parts) >= 3:
                        old_info = parts[1][1:]  # Remove the -
                        if ',' in old_info:
                            start_line = int(old_info.split(',')[0]) - 1  # Convert to 0-based
                        else:
                            start_line = int(old_info) - 1

                        current_original_line = start_line
                    i += 1
                    continue

                # Skip diff headers (must check before processing -/+ lines)
                if line.startswith('---') or line.startswith('+++'):
                    i += 1
                    continue

                # Process diff lines
                if line.startswith('-'):
                    # Remove line
                    if current_original_line < len(result_lines):
                        del result_lines[current_original_line]
                elif line.startswith('+'):
                    # Add line
                    new_line = line[1:]  # Remove the +
                    # If original had CRLF and this line doesn't have \r, add it
                    if has_crlf and not new_line.endswith('\r'):
                        new_line = new_line + '\r'
                    result_lines.insert(current_original_line, new_line)
                    current_original_line += 1
                elif line.startswith(' '):
                    # Context line - advance
                    current_original_line += 1

                i += 1

            return '\n'.join(result_lines)
            
        except Exception as e:
            self.logger.log(f"❌ GitHub Copilot manual diff application failed: {str(e)}")
            return None

    def _detect_change_type(self, old_text: str, new_text: str, file_path: str) -> str:
        """Detect the type of change requested"""
        old_lower = old_text.lower()
        new_lower = new_text.lower()
        
        # Additive indicators
        additive_keywords = ['add', 'include', 'incorporate', 'insert', 'create section', 'new section', 'best practices']
        if any(keyword in old_lower or keyword in new_lower for keyword in additive_keywords):
            return "ADDITIVE"
        
        # Corrective indicators  
        corrective_keywords = ['correct', 'fix', 'grammar', 'spelling', 'typo', 'misspell', 'wrong', 'error']
        if any(keyword in old_lower or keyword in new_lower for keyword in corrective_keywords):
            return "CORRECTIVE"
        
        # If new text is much longer than old text, likely additive
        if len(new_text.strip()) > len(old_text.strip()) * 2:
            return "ADDITIVE"
        
        # If similar length, likely corrective
        if abs(len(new_text.strip()) - len(old_text.strip())) < 50:
            return "CORRECTIVE"
        
        return "GENERAL"

    def _handle_additive_change_copilot(self, file_content: str, old_text: str, new_text: str, file_path: str) -> Optional[str]:
        """Handle additive changes using GitHub Copilot"""
        self.logger.log("🔨 GitHub Copilot handling additive change - generating new content...")
        
        try:
            import requests
            
            url = "https://models.inference.ai.azure.com/chat/completions"
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            }

            prompt = f"""You are helping add new content to a documentation file.

File: {file_path}
Request: {old_text}
Content to add: {new_text}

Your task: Generate ONLY the new content that should be added. Do not rewrite the existing file.

Rules:
1. Generate ONLY the new section/content to be added
2. Use proper markdown formatting if it's a markdown file
3. Make it standalone - don't reference existing content
4. Do not include any existing file content in your response
5. Return only the new content, nothing else

Generate the new content now:"""

            data = {
                "messages": [
                    {"role": "system", "content": "You are a content generator. Generate only new content, never rewrite existing content."},
                    {"role": "user", "content": prompt}
                ],
                "model": "gpt-4o",
                "temperature": 0.1,
                "max_tokens": 2048
            }
            
            response = requests.post(url, headers=headers, json=data, timeout=60)
            response.raise_for_status()
            
            result = response.json()
            new_content = result['choices'][0]['message']['content'].strip()
            
            # Clean up markdown blocks if needed
            if new_content.startswith("```") and new_content.endswith("```"):
                lines = new_content.split('\n')
                if len(lines) > 2:
                    new_content = '\n'.join(lines[1:-1])
            
            # Find insertion point and insert
            insertion_point = self._find_insertion_point(file_content, old_text, file_path)
            lines = file_content.split('\n')
            lines.insert(insertion_point, '\n' + new_content + '\n')
            updated_content = '\n'.join(lines)
            
            # Count actual changes
            original_lines = file_content.split('\n')
            updated_lines = updated_content.split('\n')
            import difflib
            diff = list(difflib.unified_diff(original_lines, updated_lines, lineterm=''))
            changed_lines = len([line for line in diff if line.startswith('+')])
            
            self.logger.log(f"✅ GitHub Copilot added new content ({changed_lines} lines added)")
            return updated_content
            
        except Exception as e:
            self.logger.log(f"❌ Error in GitHub Copilot additive change: {str(e)}")
            return None

    def _handle_corrective_change_copilot(self, file_content: str, old_text: str, new_text: str, file_path: str) -> Optional[str]:
        """Handle corrective changes using GitHub Copilot"""
        self.logger.log("🔍 GitHub Copilot handling corrective change - finding specific issues...")
        
        try:
            import requests
            
            url = "https://models.inference.ai.azure.com/chat/completions"
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            }

            prompt = f"""You are helping fix a specific issue in a documentation file.

Issue: {old_text}
Fix: {new_text}
File: {file_path}

Your task: Find the EXACT text that needs to be corrected and provide the EXACT replacement.

Return your response in this format:
OLD: [exact text to find]
NEW: [exact replacement text]

Be very specific - find the minimal text that needs changing. For example:
- If fixing "Microsft" → return OLD: Microsft, NEW: Microsoft
- If fixing grammar → return OLD: [the incorrect phrase], NEW: [corrected phrase]

File content to search:
{file_content}

Find the exact text to correct:"""

            data = {
                "messages": [
                    {"role": "system", "content": "You are a precise error detector. Find exact text that needs correction."},
                    {"role": "user", "content": prompt}
                ],
                "model": "gpt-4o",
                "temperature": 0.1,
                "max_tokens": 1024
            }
            
            response = requests.post(url, headers=headers, json=data, timeout=60)
            response.raise_for_status()
            
            result = response.json()
            response_text = result['choices'][0]['message']['content'].strip()
            
            # Parse OLD and NEW
            old_match = None
            new_match = None
            
            for line in response_text.split('\n'):
                if line.startswith('OLD:'):
                    old_match = line[4:].strip()
                elif line.startswith('NEW:'):
                    new_match = line[4:].strip()
            
            if old_match and new_match and old_match in file_content:
                updated_content = file_content.replace(old_match, new_match)
                original_lines = file_content.split('\n')
                updated_lines = updated_content.split('\n')
                import difflib
                diff = list(difflib.unified_diff(original_lines, updated_lines, lineterm=''))
                changed_lines = len([line for line in diff if line.startswith('+') or line.startswith('-')])
                self.logger.log(f"✅ GitHub Copilot corrective change successful ({changed_lines} lines affected)")
                return updated_content
            else:
                self.logger.log(f"⚠️ GitHub Copilot could not find exact text to correct")
                return None
                
        except Exception as e:
            self.logger.log(f"❌ Error in GitHub Copilot corrective change: {str(e)}")
            return None

    def _handle_general_change_copilot(self, file_content: str, old_text: str, new_text: str, file_path: str) -> Optional[str]:
        """Handle general changes using GitHub Copilot with enhanced targeting"""
        self.logger.log("🎯 GitHub Copilot handling general change with enhanced targeting...")
        
        try:
            import requests
            
            url = "https://models.inference.ai.azure.com/chat/completions"
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            }

            prompt = f"""You are helping make a specific text change in a documentation file.

File: {file_path}
Change needed: {old_text}
New content: {new_text}

CRITICAL: Make the SMALLEST possible change. Do not rewrite or reorganize content.

Your task:
1. Find the specific section that needs changing
2. Make ONLY that change
3. Preserve everything else exactly as-is
4. Return the complete updated file

Current file content:
{file_content}"""

            data = {
                "messages": [
                    {"role": "system", "content": "You are a precise file editor. Make minimal targeted changes only."},
                    {"role": "user", "content": prompt}
                ],
                "model": "gpt-4o",
                "temperature": 0.1,
                "max_tokens": 8000
            }
            
            response = requests.post(url, headers=headers, json=data, timeout=60)
            response.raise_for_status()
            
            result = response.json()
            updated_content = result['choices'][0]['message']['content'].strip()
            
            # Clean up markdown code blocks
            if updated_content.startswith("```"):
                lines = updated_content.split('\n')
                if len(lines) > 2:
                    if lines[0].startswith("```") and lines[-1].strip() == "```":
                        updated_content = '\n'.join(lines[1:-1])

            if new_text.strip() in updated_content:
                original_lines = file_content.split('\n')
                updated_lines = updated_content.split('\n')
                
                import difflib
                diff = list(difflib.unified_diff(original_lines, updated_lines, lineterm=''))
                changed_lines = len([line for line in diff if line.startswith('+') or line.startswith('-')])
                
                if changed_lines > 30:
                    self.logger.log(f"⚠️ GitHub Copilot change affected {changed_lines} lines - may be too broad")
                else:
                    self.logger.log(f"✅ GitHub Copilot general change successful ({changed_lines} lines affected)")
                
                return updated_content
            else:
                self.logger.log("⚠️ GitHub Copilot: New text not found in result")
                return None
                
        except Exception as e:
            self.logger.log(f"❌ Error in GitHub Copilot general change: {str(e)}")
            return None

    def _find_insertion_point(self, file_content: str, context: str, file_path: str) -> int:
        """Find the best place to insert new content"""
        lines = file_content.split('\n')
        
        # For markdown files, try to find a good section to add after
        if file_path.endswith('.md'):
            # Look for existing sections
            for i, line in enumerate(lines):
                if line.startswith('#') and i < len(lines) - 1:
                    # Insert after this section
                    continue
            
            # If no good sections found, add at the end
            return len(lines)
        
        # For other files, add at the end
        return len(lines)


class LocalGitManager:
    """Manages local git operations for making changes before creating PRs"""

    def __init__(self, logger: Logger, github_token: str):
        self.logger = logger
        self.github_token = github_token
        self.last_diff_content = ""  # Store the last generated diff content

    def get_repo_path(self, owner: str, repo: str, local_path: Optional[str] = None) -> Path:
        """Get or create local repository path

        Args:
            owner: Repository owner
            repo: Repository name
            local_path: Base path from LOCAL_REPO_PATH setting

        Returns:
            Full path to the repository (base/owner/repo)
        """
        # If LOCAL_REPO_PATH is configured, use it as the base directory
        if local_path and local_path.strip():
            base_path = Path(local_path.strip())

            # Warn if OneDrive path detected
            if 'OneDrive' in str(base_path):
                self.logger.log("⚠️ WARNING: Local Repo Path is in a OneDrive folder")
                self.logger.log("   OneDrive sync can cause file locking issues with git operations")
                self.logger.log("   Consider using a non-OneDrive location (e.g., C:\\git\\repos)")

            # Create base directory if it doesn't exist
            if not base_path.exists():
                self.logger.log(f"Creating local repo directory: {base_path}")
                try:
                    base_path.mkdir(parents=True, exist_ok=True)
                except Exception as e:
                    self.logger.log(f"⚠️ Could not create directory {base_path}: {e}")
                    self.logger.log("   Falling back to default location")
                    # Fall through to default
                else:
                    # Successfully created or exists, use it
                    repo_path = base_path / owner / repo
                    return repo_path
            else:
                # Base path exists, use it
                repo_path = base_path / owner / repo
                return repo_path

        # Default: Use Downloads folder (typically not in OneDrive)
        downloads = Path.home() / "Downloads"
        repo_path = downloads / "github_repos" / owner / repo
        return repo_path

    def clone_or_pull_repo(self, owner: str, repo: str, local_path: Optional[str] = None) -> Optional[Path]:
        """Clone repository if it doesn't exist, or pull latest changes if it does"""
        try:
            import git
            import gc

            repo_path = self.get_repo_path(owner, repo, local_path)
            repo_url = f"https://{self.github_token}@github.com/{owner}/{repo}.git"

            if repo_path.exists() and (repo_path / ".git").exists():
                # Repository exists, try to update it
                self.logger.log(f"Repository exists at {repo_path}, updating...")
                git_repo = None
                try:
                    git_repo = git.Repo(repo_path)

                    # Try alternative update methods that are more reliable
                    try:
                        # Method 1: Fetch and reset (more reliable than pull)
                        self.logger.log("Fetching latest changes...")
                        git_repo.git.fetch('origin')

                        # Make sure we're on main/master
                        try:
                            git_repo.git.checkout('main')
                            git_repo.git.reset('--hard', 'origin/main')
                        except:
                            git_repo.git.checkout('master')
                            git_repo.git.reset('--hard', 'origin/master')

                        self.logger.log("✅ Repository updated successfully")
                        return repo_path
                    except Exception as fetch_error:
                        self.logger.log(f"⚠️ Fetch/reset failed: {fetch_error}")
                        # Try simple pull as fallback
                        origin = git_repo.remotes.origin
                        origin.pull()
                        self.logger.log("✅ Pulled latest changes")
                        return repo_path

                except Exception as e:
                    self.logger.log(f"⚠️ Error updating repo: {e}")
                    self.logger.log("Repository will be reused as-is for this operation")

                    # Don't try to delete - just reuse the existing repo
                    # This avoids file locking issues
                    return repo_path
                finally:
                    # Always clean up
                    if git_repo:
                        try:
                            git_repo.close()
                            git_repo.__del__()
                        except:
                            pass
                    git_repo = None
                    gc.collect()

            # Clone repository
            self.logger.log(f"Cloning repository to {repo_path}...")
            repo_path.parent.mkdir(parents=True, exist_ok=True)
            git.Repo.clone_from(repo_url, repo_path)
            self.logger.log("✅ Repository cloned successfully")
            return repo_path

        except ImportError:
            self.logger.log("❌ GitPython not installed. Run: pip install GitPython")
            return None
        except Exception as e:
            self.logger.log(f"❌ Error with git operations: {str(e)}")
            return None

    def _safe_remove_tree(self, path: Path, max_retries: int = 3) -> bool:
        """Safely remove a directory tree with retry logic for Windows file locking"""
        import gc

        for attempt in range(max_retries):
            try:
                if path.exists():
                    # On Windows, make files writable before deletion
                    if sys.platform == 'win32':
                        for root, _, files in os.walk(str(path)):
                            for fname in files:
                                fpath = os.path.join(root, fname)
                                try:
                                    os.chmod(fpath, 0o777)
                                except:
                                    pass

                    shutil.rmtree(path, ignore_errors=False)
                    self.logger.log(f"✅ Removed directory: {path}")
                    return True
            except Exception as e:
                if attempt < max_retries - 1:
                    self.logger.log(f"⚠️ Attempt {attempt + 1} failed to remove {path}: {e}")
                    gc.collect()  # Force garbage collection
                    time.sleep(1)  # Wait longer between retries
                else:
                    self.logger.log(f"❌ Failed to remove {path} after {max_retries} attempts: {e}")
                    self.logger.log(f"💡 TIP: Close any file explorers or editors that might have this folder open")
                    return False
        return False

    def apply_diff_and_commit(self, repo_path: Path, branch_name: str,
                              file_path: str, diff_patch: str, commit_message: str) -> bool:
        """Apply diff patch using git apply and commit changes

        This is the preferred method as it uses native git to apply patches,
        which properly handles line endings, whitespace, and other edge cases.
        """
        git_repo = None
        try:
            import git
            import tempfile
            import os

            git_repo = git.Repo(repo_path)

            # Create new branch from main
            self.logger.log(f"Creating branch {branch_name}...")
            try:
                git_repo.git.checkout('main')
                git_repo.git.pull()
            except:
                git_repo.git.checkout('master')
                git_repo.git.pull()

            git_repo.git.checkout('-b', branch_name)
            self.logger.log(f"✅ Branch {branch_name} created")

            # Write diff patch to temp file
            # Ensure patch ends with newline for git apply compatibility
            patch_content = diff_patch if diff_patch.endswith('\n') else diff_patch + '\n'

            with tempfile.NamedTemporaryFile(mode='w', suffix='.patch', delete=False, encoding='utf-8', newline='\n') as patch_file:
                patch_file.write(patch_content)
                patch_file_path = patch_file.name

            try:
                # Apply patch using git apply
                self.logger.log(f"Applying diff patch to {file_path}...")
                self.logger.log(f"Patch file: {patch_file_path}")

                try:
                    git_repo.git.apply('--verbose', '--whitespace=nowarn', patch_file_path)
                    self.logger.log("✅ Diff patch applied successfully using git apply")
                except Exception as apply_error:
                    self.logger.log(f"⚠️ git apply failed: {str(apply_error)}")

                    # Log the patch content for debugging
                    self.logger.log("📄 Patch content (first 1000 chars):")
                    self.logger.log(patch_content[:1000])

                    self.logger.log("📝 Attempting to apply patch with --3way merge...")
                    try:
                        # Try with 3-way merge which is more forgiving
                        git_repo.git.apply('--3way', '--whitespace=nowarn', patch_file_path)
                        self.logger.log("✅ Diff patch applied using 3-way merge")
                    except Exception as merge_error:
                        self.logger.log(f"⚠️ 3-way merge also failed: {str(merge_error)}")

                        # Try one more time with --ignore-whitespace
                        self.logger.log("📝 Attempting with --ignore-whitespace...")
                        try:
                            git_repo.git.apply('--ignore-whitespace', '--whitespace=nowarn', patch_file_path)
                            self.logger.log("✅ Diff patch applied with --ignore-whitespace")
                        except:
                            self.logger.log("❌ All git apply methods failed")
                            # Keep the patch file for debugging
                            self.logger.log(f"💾 Patch file saved for debugging: {patch_file_path}")
                            raise

                # Stage and commit
                git_repo.index.add([file_path])
                git_repo.index.commit(commit_message)
                self.logger.log("✅ Changes committed")

                return True

            finally:
                # Clean up temp patch file only on success
                if git_repo and git_repo.head.is_valid():
                    try:
                        os.unlink(patch_file_path)
                    except:
                        pass

        except Exception as e:
            self.logger.log(f"❌ Error applying diff and committing: {str(e)}")
            self.logger.log("💡 This may indicate the file has changed since it was fetched")
            return False
        finally:
            if git_repo:
                try:
                    git_repo.close()
                    git_repo.__del__()
                except:
                    pass
                import gc
                gc.collect()

    def create_branch_and_commit(self, repo_path: Path, branch_name: str,
                                  file_path: str, updated_content: str,
                                  commit_message: str, line_ending: str = '\n') -> bool:
        """Create branch, update file, and commit

        Args:
            line_ending: Original line ending style to preserve ('\n' or '\r\n')

        NOTE: This method is deprecated in favor of apply_diff_and_commit which uses git apply.
        """
        git_repo = None
        try:
            import git
            import gc

            git_repo = git.Repo(repo_path)

            # Create new branch from main
            self.logger.log(f"Creating branch {branch_name}...")
            try:
                git_repo.git.checkout('main')
                git_repo.git.pull()
            except:
                git_repo.git.checkout('master')
                git_repo.git.pull()

            git_repo.git.checkout('-b', branch_name)
            self.logger.log(f"✅ Branch {branch_name} created")

            # Update the file
            full_file_path = repo_path / file_path
            if not full_file_path.exists():
                self.logger.log(f"❌ File not found: {file_path}")
                return False

            self.logger.log(f"Writing changes to {file_path}...")

            # Preserve original line endings
            if line_ending == '\r\n':
                # Normalize to CRLF if original had CRLF
                content_to_write = updated_content.replace('\r\n', '\n').replace('\n', '\r\n')
                self.logger.log(f"✅ Preserving CRLF line endings")
            else:
                content_to_write = updated_content

            full_file_path.write_text(content_to_write, encoding='utf-8', newline='')

            # Stage and commit
            git_repo.index.add([file_path])
            git_repo.index.commit(commit_message)
            self.logger.log("✅ Changes committed")

            return True

        except Exception as e:
            self.logger.log(f"❌ Error creating branch and committing: {str(e)}")
            return False
        finally:
            if git_repo:
                try:
                    git_repo.close()
                    git_repo.__del__()
                except:
                    pass
                import gc
                gc.collect()  # Force garbage collection to release file handles

    def push_branch(self, repo_path: Path, branch_name: str) -> bool:
        """Push branch to remote"""
        git_repo = None
        try:
            import git
            import gc

            self.logger.log(f"Pushing branch {branch_name} to remote...")
            git_repo = git.Repo(repo_path)
            origin = git_repo.remotes.origin
            origin.push(branch_name)
            self.logger.log("✅ Branch pushed to remote")
            return True

        except Exception as e:
            self.logger.log(f"❌ Error pushing branch: {str(e)}")
            return False
        finally:
            if git_repo:
                try:
                    git_repo.close()
                    git_repo.__del__()
                except:
                    pass
                import gc
                gc.collect()  # Force garbage collection to release file handles

    def make_ai_assisted_change(self, owner: str, repo: str, branch_name: str,
                                file_path: str, old_text: str, new_text: str,
                                commit_message: str, ai_provider: AIProvider,
                                local_path: Optional[str] = None, custom_instructions: str = None) -> Tuple[bool, Optional[str]]:
        """
        Complete workflow: clone, make TARGETED changes, commit, and push
        This uses direct string replacement to avoid AI rewriting entire files

        Returns:
            (success: bool, error_message: Optional[str])
        """
        try:
            # Step 1: Clone or pull repository
            repo_path = self.clone_or_pull_repo(owner, repo, local_path)
            if not repo_path:
                return False, "Failed to clone/pull repository"

            # Step 2: Read the current file
            full_file_path = repo_path / file_path
            if not full_file_path.exists():
                return False, f"File not found: {file_path}"

            self.logger.log(f"Reading file: {file_path}")
            # Read in binary mode to detect and preserve line endings
            raw_bytes = full_file_path.read_bytes()
            current_content = raw_bytes.decode('utf-8')

            # Detect original line ending style
            original_line_ending = '\r\n' if b'\r\n' in raw_bytes else '\n'
            self.logger.log(f"📝 Detected line endings: {'CRLF' if original_line_ending == '\\r\\n' else 'LF'}")

            # Normalize everything to LF for consistent processing
            normalized_content = current_content.replace('\r\n', '\n')
            normalized_old = old_text.replace('\r\n', '\n')
            normalized_new = new_text.replace('\r\n', '\n')

            # Step 3: Make TARGETED change
            updated_content = None

            # Strategy 1: Very conservative direct replacement (only for exact, specific content)
            # Only use this for replacements where old_text is substantial and very specific
            use_direct_replacement = (
                normalized_old.strip() and
                len(normalized_old.strip()) > 20 and  # Must be substantial content
                normalized_old.strip().count('\n') >= 2 and  # Must be multi-line
                normalized_old.strip() in normalized_content and
                normalized_content.count(normalized_old.strip()) == 1  # Must be unique match
            )

            if use_direct_replacement:
                self.logger.log("✅ Making very targeted direct replacement")
                updated_content = normalized_content.replace(normalized_old.strip(), normalized_new.strip())
                
                # Verify the replacement worked and was targeted
                original_lines = normalized_content.split('\n')
                updated_lines = updated_content.split('\n')

                import difflib
                diff = list(difflib.unified_diff(original_lines, updated_lines, lineterm=''))
                changed_lines = len([line for line in diff if line.startswith('+') or line.startswith('-')])

                if changed_lines > 20:  # If too many changes, something went wrong
                    self.logger.log(f"⚠️ Direct replacement affected {changed_lines} lines - falling back to AI")
                    updated_content = None  # Fall back to AI
                else:
                    self.logger.log(f"✅ Direct replacement successful ({changed_lines} lines changed)")

            # Strategy 2: Use AI to generate complete updated document
            if not updated_content:
                self.logger.log("Using AI to modify complete document...")
                self.logger.log(f"AI Provider type: {type(ai_provider).__name__}")
                self.logger.log(f"Old text preview: {normalized_old[:100]}...")
                self.logger.log(f"New text preview: {normalized_new[:100]}...")
                
                # Pass normalized versions to AI provider
                try:
                    updated_content = ai_provider.make_change(normalized_content, normalized_old, normalized_new, file_path, custom_instructions)
                    if not updated_content:
                        self.logger.log("❌ AI provider returned None or empty content")
                        return False, "AI failed to make the change - provider returned no content"
                    else:
                        self.logger.log(f"✅ AI provider returned content ({len(updated_content)} characters)")
                except Exception as e:
                    self.logger.log(f"❌ AI provider threw exception: {str(e)}")
                    return False, f"AI failed to make the change - error: {str(e)}"

            # Step 4: Apply changes directly using file write method
            # Restore original line endings in the updated content before writing
            if original_line_ending == '\r\n':
                updated_content_with_endings = updated_content.replace('\n', '\r\n')
            else:
                updated_content_with_endings = updated_content

            if not self.create_branch_and_commit(repo_path, branch_name, file_path,
                                                 updated_content_with_endings, commit_message):
                return False, "Failed to apply changes using direct file write method"

            self.logger.log("✅ Changes applied using direct file write method")

            # Step 5: Push to remote
            if not self.push_branch(repo_path, branch_name):
                return False, "Failed to push branch to remote"

            self.logger.log("✅ AI-assisted changes completed successfully")
            return True, None

        except Exception as e:
            error_msg = f"Error in AI-assisted change workflow: {str(e)}"
            self.logger.log(f"❌ {error_msg}")
            return False, error_msg
    
    def get_last_diff_content(self) -> str:
        """Get the last generated diff content for display in the UI"""
        return self.last_diff_content
    
    def clear_diff_content(self):
        """Clear the stored diff content"""
        self.last_diff_content = ""

    def get_git_diff_from_repo(self, repo_path: str, branch_name: str) -> str:
        """Get the actual git diff from the repository for the specified branch"""
        try:
            import subprocess
            import os

            self.logger.log(f"🔍 Getting git diff from: {repo_path}")
            self.logger.log(f"🔍 Branch: {branch_name}")
            
            # Change to repo directory
            original_dir = os.getcwd()
            
            if not os.path.exists(repo_path):
                self.logger.log(f"❌ Repository path does not exist: {repo_path}")
                return ""
                
            os.chdir(repo_path)
            self.logger.log(f"🔍 Changed to directory: {os.getcwd()}")

            try:
                diff_content = ""
                
                # Check current git status first
                try:
                    result = subprocess.run(['git', 'status', '--porcelain'], 
                                          capture_output=True, text=True, check=True, encoding='utf-8', errors='replace')
                    if result.stdout.strip():
                        self.logger.log(f"🔍 Git status shows changes: {result.stdout.strip()[:100]}...")
                    else:
                        self.logger.log("🔍 Git status shows no uncommitted changes")
                except Exception as e:
                    self.logger.log(f"⚠️ Could not check git status: {e}")
                
                # Check current branch
                try:
                    result = subprocess.run(['git', 'branch', '--show-current'], 
                                          capture_output=True, text=True, check=True, encoding='utf-8', errors='replace')
                    current_branch = result.stdout.strip()
                    self.logger.log(f"🔍 Current branch: {current_branch}")
                except Exception as e:
                    self.logger.log(f"⚠️ Could not get current branch: {e}")
                
                # First, try to get diff from the current commit against main/master
                try:
                    self.logger.log("🔍 Trying: git diff main HEAD")
                    result = subprocess.run(['git', 'diff', 'main', 'HEAD'], 
                                            capture_output=True, text=True, check=True, encoding='utf-8', errors='replace')
                    diff_content = result.stdout
                    if diff_content:
                        self.logger.log(f"✅ Retrieved git diff against main ({len(diff_content)} characters)")
                    else:
                        self.logger.log("🔍 No diff found against main")
                except subprocess.CalledProcessError as e:
                    self.logger.log(f"🔍 git diff main HEAD failed: {e}")
                    try:
                        self.logger.log("🔍 Trying: git diff master HEAD")
                        result = subprocess.run(['git', 'diff', 'master', 'HEAD'], 
                                                capture_output=True, text=True, check=True, encoding='utf-8', errors='replace')
                        diff_content = result.stdout
                        if diff_content:
                            self.logger.log(f"✅ Retrieved git diff against master ({len(diff_content)} characters)")
                        else:
                            self.logger.log("🔍 No diff found against master")
                    except subprocess.CalledProcessError as e:
                        self.logger.log(f"🔍 git diff master HEAD failed: {e}")

                # If still no diff, try against previous commit (only if it exists)
                if not diff_content:
                    try:
                        self.logger.log("🔍 Trying: git rev-parse --verify HEAD~1")
                        subprocess.run(['git', 'rev-parse', '--verify', 'HEAD~1'], 
                                     capture_output=True, check=True, encoding='utf-8', errors='replace')
                        # If we get here, HEAD~1 exists
                        self.logger.log("🔍 Trying: git diff HEAD~1 HEAD")
                        result = subprocess.run(['git', 'diff', 'HEAD~1', 'HEAD'], 
                                                capture_output=True, text=True, check=True, encoding='utf-8', errors='replace')
                        diff_content = result.stdout
                        if diff_content:
                            self.logger.log(f"✅ Retrieved git diff against HEAD~1 ({len(diff_content)} characters)")
                        else:
                            self.logger.log("🔍 No diff found against HEAD~1")
                    except subprocess.CalledProcessError as e:
                        self.logger.log(f"🔍 HEAD~1 doesn't exist or diff failed: {e}")

                # If still no diff, try to get the diff of all changes in the current commit
                if not diff_content:
                    try:
                        self.logger.log("🔍 Trying: git show --format= HEAD")
                        result = subprocess.run(['git', 'show', '--format=', 'HEAD'], 
                                                capture_output=True, text=True, check=True, encoding='utf-8', errors='replace')
                        diff_content = result.stdout
                        if diff_content:
                            self.logger.log(f"✅ Retrieved git show for HEAD commit ({len(diff_content)} characters)")
                        else:
                            self.logger.log("🔍 No content from git show HEAD")
                    except subprocess.CalledProcessError as e:
                        self.logger.log(f"🔍 git show HEAD failed: {e}")

                # If we have diff content, save it to a .diff file
                if diff_content:
                    self._save_diff_to_file(diff_content, repo_path, branch_name)
                else:
                    self.logger.log("❌ No diff content found using any method")
                
                return diff_content

            finally:
                os.chdir(original_dir)
                self.logger.log(f"🔍 Changed back to: {os.getcwd()}")

        except Exception as e:
            self.logger.log(f"❌ Error getting git diff from repository: {str(e)}")
            import traceback
            self.logger.log(f"❌ Traceback: {traceback.format_exc()}")
            return ""

    def _save_diff_to_file(self, diff_content: str, repo_path: str, branch_name: str) -> None:
        """Save the diff content to a .diff file in the repository"""
        try:
            import os
            from datetime import datetime
            
            # Create a filename with timestamp and branch name
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            safe_branch_name = branch_name.replace('/', '_').replace(':', '_')
            diff_filename = f"changes_{safe_branch_name}_{timestamp}.diff"
            diff_filepath = os.path.join(repo_path, diff_filename)
            
            # Write the diff content to file
            with open(diff_filepath, 'w', encoding='utf-8') as f:
                f.write(diff_content)
            
            self.logger.log(f"💾 Saved diff to: {diff_filename}")
            
        except Exception as e:
            self.logger.log(f"❌ Error saving diff to file: {str(e)}")


def create_ai_provider(provider_name: str, api_key: str, logger: Logger, ollama_url: str = None, ollama_model: str = None) -> Optional[AIProvider]:
    """Factory function to create AI provider instances"""
    if provider_name.lower() == 'claude':
        return ClaudeProvider(api_key, logger)
    elif provider_name.lower() in ['chatgpt', 'openai', 'gpt']:
        return ChatGPTProvider(api_key, logger)
    elif provider_name.lower() in ['github-copilot', 'copilot', 'github_copilot']:
        return GitHubCopilotProvider(api_key, logger)
    elif provider_name.lower() == 'ollama':
        # For Ollama, api_key is optional (can be empty string)
        return OllamaProvider(api_key or "", logger, ollama_url, ollama_model)
    else:
        logger.log(f"⚠️ Unknown AI provider: {provider_name}")
        return None


def get_detailed_python_environment_info() -> dict:
    """Get detailed information about the current Python environment
    
    Returns:
        dict: Environment information including venv status, Python version, etc.
    """
    import sys
    import os
    
    # Detect virtual environment
    in_venv = (hasattr(sys, 'real_prefix') or 
               (hasattr(sys, 'base_prefix') and sys.base_prefix != sys.prefix) or
               os.environ.get('VIRTUAL_ENV') is not None)
    
    env_info = {
        'in_venv': in_venv,
        'python_version': f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
        'python_executable': sys.executable,
    }
    
    if in_venv:
        venv_path = os.environ.get('VIRTUAL_ENV', sys.prefix)
        env_info['venv_name'] = os.path.basename(venv_path)
        env_info['venv_path'] = venv_path
    else:
        env_info['venv_name'] = None
        env_info['venv_path'] = None
    
    return env_info


def install_ai_packages_enhanced(packages: List[str], parent_window=None) -> bool:
    """Enhanced AI provider package installation with better error handling
    
    Args:
        packages: List of package names to install
        parent_window: Parent tkinter window for dialog (optional)
        
    Returns:
        bool: True if installation successful or user declined, False if failed
    """
    import subprocess
    import sys
    import os
    
    if not packages:
        return True

    # Detect virtual environment
    in_venv = (hasattr(sys, 'real_prefix') or 
               (hasattr(sys, 'base_prefix') and sys.base_prefix != sys.prefix) or
               os.environ.get('VIRTUAL_ENV') is not None)
    
    venv_info = ""
    install_location = ""
    
    if in_venv:
        venv_path = os.environ.get('VIRTUAL_ENV', sys.prefix)
        venv_name = os.path.basename(venv_path)
        install_location = f"virtual environment '{venv_name}'"
        venv_info = f"\n🌐 Virtual environment detected: {venv_name}"
    else:
        install_location = "system-wide (may require administrator rights)"
        venv_info = f"\n⚠️ No virtual environment detected - installing system-wide"
    
    # Create confirmation message
    package_list = ', '.join(packages)
    message = (f"The following packages are required for AI functionality:\n\n"
              f"{package_list}\n\n"
              f"Installation location: {install_location}"
              f"{venv_info}\n\n"
              f"Would you like to install them now?\n\n"
              f"This will run: pip install {' '.join(packages)}")
    
    # Show confirmation dialog
    try:
        import tkinter as tk
        from tkinter import messagebox
        
        # If we have a parent window, use it; otherwise create a temporary root
        if parent_window:
            result = messagebox.askyesno("Install AI Packages", message, parent=parent_window)
        else:
            # Create temporary root window for the dialog
            temp_root = tk.Tk()
            temp_root.withdraw()  # Hide the temporary window
            result = messagebox.askyesno("Install AI Packages", message)
            temp_root.destroy()
            
        if not result:
            print("User declined to install AI packages")
            return True  # User declined, but this isn't a failure
            
    except Exception as e:
        print(f"Could not show dialog, proceeding with installation: {e}")
        # If dialog fails, ask in console
        response = input(f"Install AI packages ({package_list})? [y/N]: ").lower()
        if response not in ['y', 'yes']:
            return True
    
    # Install packages
    try:
        if in_venv:
            print(f"Installing packages to virtual environment: {package_list}")
        else:
            print(f"Installing packages system-wide: {package_list}")
        
        for package in packages:
            print(f"Installing {package}...")
            
            # Build pip command
            pip_cmd = [sys.executable, '-m', 'pip', 'install', package]
            
            # First attempt: Direct installation
            result = subprocess.run(pip_cmd, capture_output=True, text=True, timeout=300)
            
            # If direct install fails and we're not in venv, try with --user flag
            if result.returncode != 0 and not in_venv:
                print(f"  Direct installation failed, trying with --user flag...")
                pip_cmd_user = [sys.executable, '-m', 'pip', 'install', '--user', package]
                result = subprocess.run(pip_cmd_user, capture_output=True, text=True, timeout=300)
                
                if result.returncode == 0:
                    print(f"✅ Successfully installed {package} (user-local)")
                    continue
            
            if result.returncode != 0:
                print(f"❌ Failed to install {package}:")
                print(f"Error: {result.stderr}")
                
                # Show more helpful error message
                if "permission" in result.stderr.lower() or "access" in result.stderr.lower():
                    print("  This appears to be a permissions issue.")
                    if not in_venv:
                        print("  Consider:")
                        print("  1. Running as administrator")
                        print("  2. Using a virtual environment")
                        print("  3. Installing with --user flag")
                
                return False
            else:
                install_type = "to virtual environment" if in_venv else "system-wide"
                print(f"✅ Successfully installed {package} ({install_type})")
        
        success_msg = "✅ AI packages installed successfully!"
        if in_venv:
            success_msg += f" (installed to virtual environment)"
        else:
            success_msg += f" (installed system-wide)"
            
        print(success_msg)
        print("Please restart the application to use the new AI features.")
        return True
        
    except subprocess.TimeoutExpired:
        print("❌ Installation timed out")
        return False
    except Exception as e:
        print(f"❌ Error installing packages: {e}")
        return False


def validate_ai_provider_setup(config: dict, parent_window=None) -> bool:
    """Validate AI provider setup and offer to install missing modules
    
    Args:
        config: Configuration dictionary
        parent_window: Parent tkinter window for dialogs
        
    Returns:
        bool: True if setup is valid or user handled the issue
    """
    ai_provider = config.get('AI_PROVIDER', '').lower()
    
    if not ai_provider or ai_provider == 'none':
        return True  # No AI provider selected, nothing to validate
    
    # Create a temporary AI manager to check modules
    temp_manager = AIManager()
    
    # Check if modules are available
    available, missing = temp_manager.check_ai_module_availability(ai_provider)
    
    if available:
        return True  # All modules available
    
    print(f"⚠️ AI Provider '{ai_provider}' selected but missing required packages: {', '.join(missing)}")
    
    # Offer to install missing packages using enhanced installer
    success = install_ai_packages_enhanced(missing, parent_window)
    
    if success:
        # Re-check availability after installation
        available, still_missing = temp_manager.check_ai_module_availability(ai_provider)
        if available:
            print(f"✅ AI Provider '{ai_provider}' is now ready to use")
            return True
        else:
            print(f"⚠️ Some packages may still be missing: {', '.join(still_missing)}")
            print("Please restart the application after installation completes")
            return False
    
    return False


class OllamaProvider(AIProvider):
    """Ollama AI provider for self-hosted models"""

    def __init__(self, api_key: str, logger: Logger, ollama_url: str = None, model: str = None):
        super().__init__(api_key, logger)
        self.ollama_url = ollama_url or "http://localhost:11434"
        self.model = model or "llama2"

        # Normalize URL
        if not self.ollama_url.startswith('http'):
            self.ollama_url = f"http://{self.ollama_url}"

    def make_change(self, file_content: str, old_text: str, new_text: str, file_path: str, custom_instructions: str = None) -> Optional[str]:
        """Make targeted changes using Ollama"""

        # Step 1: Try direct string replacement first
        if old_text and old_text.strip() in file_content:
            self.logger.log("✅ Making direct string replacement (reference text found exactly)")
            updated_content = file_content.replace(old_text.strip(), new_text.strip())
            if updated_content != file_content:
                original_lines = file_content.split('\n')
                updated_lines = updated_content.split('\n')
                import difflib
                diff = list(difflib.unified_diff(original_lines, updated_lines, lineterm=''))
                changed_lines = len([line for line in diff if line.startswith('+') or line.startswith('-')])
                self.logger.log(f"✅ Direct replacement successful ({changed_lines} lines changed)")
                return updated_content

        # Step 2: Use Ollama to generate full document with targeted changes
        self.logger.log(f"📝 Using Ollama ({self.model}) to modify the document...")
        return self._generate_updated_document(file_content, old_text, new_text, file_path, custom_instructions)

    def _generate_updated_document(self, file_content: str, old_text: str, new_text: str, file_path: str, custom_instructions: str = None) -> Optional[str]:
        """Generate updated document content using Ollama"""

        try:
            import requests

            # Build custom instructions text
            if custom_instructions and custom_instructions.strip():
                custom_instructions_text = f"""
**Additional Custom Instructions:**
{custom_instructions.strip()}

"""
            else:
                custom_instructions_text = ""

            # Handle case where new_text is empty or just guidance
            if new_text and new_text.strip() and not new_text.strip().lower().startswith('<blank'):
                # We have specific replacement text
                guidance_text = f"""
**Reference text to find:**
```
{old_text}
```

**Replace with this specific content:**
```
{new_text}
```

Please find the reference text and replace it with the suggested content."""
            else:
                # new_text is empty or just guidance - use old_text as instructions
                guidance_text = f"""
**Task Instructions:**
{old_text}

**Note:** No specific replacement text provided. Use the task instructions above to determine what changes to make to improve the document. Add appropriate content based on the instructions."""

            prompt = f"""**Instructions:**

Task: Update the documentation file with the changes requested.

Steps to complete:

1. Review the current file content below
2. Follow the guidance provided to determine what changes to make
3. Make appropriate improvements while maintaining existing formatting
4. Return the complete updated file content

> [!IMPORTANT]
> OUTPUT REQUIREMENTS:
> - Return ONLY the complete file content - no explanatory text, dialog, or commentary
> - Do NOT add any text before or after the file content
> - Do NOT wrap output in markdown code blocks (```), just return the raw content
> - Return the ENTIRE document - no truncation, no placeholders like [Rest of the document here...]
> - Every single line of the original document must be present in your response
> - Preserve all markdown formatting, links, and code blocks exactly
> - Only make changes that fulfill the specified request

{custom_instructions_text}

**Current File Content:**
```
{file_content}
```

{guidance_text}

Return the complete updated file content now (NO explanatory text):"""

            # Prepare request headers
            headers = {
                "Content-Type": "application/json"
            }
            if self.api_key:
                headers["Authorization"] = f"Bearer {self.api_key}"

            # Prepare request payload
            payload = {
                "model": self.model,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": 0.3,  # Lower temperature for more consistent output
                    "num_predict": -1,   # Generate as many tokens as needed
                }
            }

            # Make request to Ollama
            self.logger.log(f"🔄 Sending request to Ollama at {self.ollama_url}...")
            response = requests.post(
                f"{self.ollama_url}/api/generate",
                json=payload,
                headers=headers,
                timeout=300  # 5 minute timeout for large documents
            )
            response.raise_for_status()

            result = response.json()
            updated_content = result.get("response", "").strip()

            if not updated_content:
                self.logger.log("❌ Ollama returned empty response")
                return None

            # Clean up response
            updated_content = self._clean_ai_response(updated_content)

            # Validate that we got the full document back
            original_line_count = len(file_content.split('\n'))
            updated_line_count = len(updated_content.split('\n'))

            if updated_line_count < original_line_count * 0.5:  # Less than 50% of original lines
                self.logger.log(f"⚠️ Warning: Updated document seems truncated ({updated_line_count} vs {original_line_count} lines)")
                self.logger.log("❌ AI may have truncated the document - using fallback")
                return None

            self.logger.log(f"✅ Successfully generated updated document ({updated_line_count} lines)")
            return updated_content

        except requests.exceptions.ConnectionError:
            self.logger.log(f"❌ Could not connect to Ollama server at {self.ollama_url}")
            self.logger.log("   Make sure Ollama is running and the URL is correct")
            return None
        except requests.exceptions.Timeout:
            self.logger.log("❌ Request to Ollama server timed out")
            return None
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 401:
                self.logger.log("❌ Authentication failed - check your Ollama API key")
            elif e.response.status_code == 404:
                self.logger.log(f"❌ Model '{self.model}' not found on Ollama server")
                self.logger.log(f"   Use 'ollama pull {self.model}' to download it")
            else:
                self.logger.log(f"❌ HTTP error from Ollama: {e}")
            return None
        except Exception as e:
            self.logger.log(f"❌ Error calling Ollama: {str(e)}")
            import traceback
            traceback.print_exc()
            return None

    def _clean_ai_response(self, response: str) -> str:
        """Clean up AI response by removing markdown code blocks and explanatory text"""

        # Remove markdown code blocks if present
        if response.startswith('```'):
            lines = response.split('\n')
            # Remove first line if it's a code fence
            if lines[0].startswith('```'):
                lines = lines[1:]
            # Remove last line if it's a code fence
            if lines and lines[-1].strip() == '```':
                lines = lines[:-1]
            response = '\n'.join(lines)

        return response.strip()


# AI Providers availability flag - now always True since they're included
AI_PROVIDERS_AVAILABLE = True


class AIManager:
    """Manages AI providers and module installations"""
    
    def __init__(self, logger=None):
        self.logger = logger
        self.last_diff_content = ""  # Store the last generated diff content
    
    def log(self, message: str) -> None:
        """Log a message with Unicode support"""
        if self.logger:
            self.logger.log(message)
        else:
            try:
                print(message)
            except UnicodeEncodeError:
                # Fallback: replace Unicode emojis with ASCII equivalents
                safe_message = message.replace('✅', '[SUCCESS]').replace('❌', '[ERROR]').replace('⚠️', '[WARNING]').replace('📋', '[INFO]').replace('📄', '[FILE]').replace('📍', '[LOCATION]').replace('📝', '[EDIT]')
                print(safe_message)
    
    def check_ai_module_availability(self, provider_name: str) -> Tuple[bool, List[str]]:
        """Check if AI provider modules are available and return missing packages

        Args:
            provider_name: 'chatgpt', 'claude', 'anthropic', 'github-copilot', or 'ollama'

        Returns:
            tuple: (all_available, missing_packages)
        """
        missing_packages = []

        # Common packages needed for AI providers
        required_common = ['GitPython']

        # Provider-specific packages
        if provider_name.lower() == 'chatgpt':
            required_packages = required_common + ['openai']
        elif provider_name.lower() in ['claude', 'anthropic']:
            required_packages = required_common + ['anthropic']
        elif provider_name.lower() in ['github-copilot', 'copilot', 'github_copilot']:
            required_packages = required_common + ['requests']
        elif provider_name.lower() == 'ollama':
            required_packages = required_common + ['requests']
        else:
            return True, []  # Unknown provider, assume no check needed

        for package in required_packages:
            try:
                if package == 'GitPython':
                    import git
                elif package == 'openai':
                    import openai
                elif package == 'anthropic':
                    import anthropic
                elif package == 'requests':
                    import requests
            except ImportError:
                missing_packages.append(package)

        all_available = len(missing_packages) == 0
        return all_available, missing_packages
    
    def get_python_environment_info(self) -> dict:
        """Get information about the current Python environment"""
        return get_detailed_python_environment_info()
    
    def install_ai_packages(self, packages: List[str], parent_window=None) -> bool:
        """Install AI packages using pip"""
        try:
            env_info = self.get_python_environment_info()
            install_location = f"virtual environment '{env_info['venv_name']}'" if env_info['in_venv'] else "system-wide"
            
            # Show confirmation dialog
            if parent_window:
                install_choice = messagebox.askyesno(
                    "Install AI Packages",
                    f"🐍 Python {env_info['python_version']}\n"
                    f"📦 Location: {install_location}\n\n"
                    f"The following packages will be installed:\n"
                    f"• {', '.join(packages)}\n\n"
                    f"This will run: pip install {' '.join(packages)}\n\n"
                    f"Continue with installation?",
                    parent=parent_window
                )
                
                if not install_choice:
                    return False
            
            self.log(f"Installing packages: {', '.join(packages)}")
            self.log(f"Installation location: {install_location}")
            
            # Run pip install
            cmd = [sys.executable, '-m', 'pip', 'install'] + packages
            self.log(f"Running: {' '.join(cmd)}")
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
            
            if result.returncode == 0:
                self.log("✅ Installation completed successfully!")
                if parent_window:
                    messagebox.showinfo(
                        "Installation Complete",
                        f"✅ Successfully installed: {', '.join(packages)}\n\n"
                        f"Location: {install_location}",
                        parent=parent_window
                    )
                return True
            else:
                error_msg = f"❌ Installation failed!\n\nError: {result.stderr}"
                self.log(error_msg)
                if parent_window:
                    messagebox.showerror("Installation Failed", error_msg, parent=parent_window)
                return False
                
        except subprocess.TimeoutExpired:
            error_msg = "❌ Installation timed out (>5 minutes)"
            self.log(error_msg)
            if parent_window:
                messagebox.showerror("Installation Timeout", error_msg, parent=parent_window)
            return False
        except Exception as e:
            error_msg = f"❌ Installation error: {str(e)}"
            self.log(error_msg)
            if parent_window:
                messagebox.showerror("Installation Error", error_msg, parent=parent_window)
            return False
    
    def check_and_install_ai_modules(self, provider_name: str, parent_window=None) -> bool:
        """Check AI modules and offer to install if missing"""
        if not provider_name or provider_name.lower() in ['none', '']:
            return True
        
        if provider_name.lower() not in ['chatgpt', 'claude', 'anthropic', 'github-copilot', 'copilot', 'github_copilot']:
            return True
        
        # Check module availability
        available, missing = self.check_ai_module_availability(provider_name)
        
        if available:
            self.log(f"✅ All required modules for {provider_name} are available")
            return True
        
        # Modules are missing, offer to install
        self.log(f"⚠️ Missing modules for {provider_name}: {', '.join(missing)}")
        
        return self.install_ai_packages(missing, parent_window)

    async def check_and_install_ai_modules_async(self, provider_name: str, page=None) -> bool:
        """Async wrapper for check_and_install_ai_modules for Flet integration

        Args:
            provider_name: AI provider name
            page: Flet page instance for showing dialogs

        Returns:
            bool: True if modules are available or successfully installed
        """
        import asyncio

        # Run the sync method in a thread pool
        result = await asyncio.to_thread(
            self.check_and_install_ai_modules,
            provider_name,
            page
        )
        return result

    def show_ai_modules_info(self, provider_name: str, parent_window=None) -> None:
        """Show detailed AI modules information"""
        try:
            # Get environment information
            env_info = self.get_python_environment_info()
            env_status = f"🐍 Python {env_info['python_version']}"
            
            if env_info['in_venv']:
                env_status += f" (venv: {env_info['venv_name']})"
            else:
                env_status += " (system-wide)"
            
            if not provider_name or provider_name.lower() in ['none', '']:
                messagebox.showinfo("AI Modules Check",
                                  f"{env_status}\n\n"
                                  f"No AI provider selected.\n\n"
                                  f"Available providers:\n"
                                  f"• ChatGPT (requires 'openai' package)\n"  
                                  f"• Claude/Anthropic (requires 'anthropic' package)\n"
                                  f"• GitHub Copilot (requires 'requests' package)\n"
                                  f"• All require 'GitPython' package",
                                  parent=parent_window)
                return
            
            if provider_name.lower() not in ['chatgpt', 'claude', 'anthropic', 'github-copilot', 'copilot', 'github_copilot']:
                messagebox.showinfo("AI Modules Check",
                                  f"AI provider '{provider_name}' is not recognized.\n\n"
                                  f"Supported providers: ChatGPT, Claude/Anthropic, GitHub Copilot",
                                  parent=parent_window)
                return
            
            # Check module availability
            available, missing = self.check_ai_module_availability(provider_name)
            
            if available:
                messagebox.showinfo("AI Modules Status",
                                  f"{env_status}\n\n"
                                  f"✅ All required modules for '{provider_name}' are installed!\n\n"
                                  f"AI-assisted features are ready to use.",
                                  parent=parent_window)
                return
            
            # Modules are missing, show detailed info and offer to install
            missing_list = '\n'.join(f"• {pkg}" for pkg in missing)
            install_location = f"virtual environment '{env_info['venv_name']}'" if env_info['in_venv'] else "system-wide"
            
            install_choice = messagebox.askyesno("Missing AI Modules",
                                               f"{env_status}\n\n"
                                               f"AI provider '{provider_name}' requires the following packages:\n\n"
                                               f"{missing_list}\n\n"
                                               f"Installation location: {install_location}\n\n"
                                               f"Would you like to install them now?\n\n"
                                               f"This will run: pip install {' '.join(missing)}",
                                               parent=parent_window)
            
            if install_choice:
                success = self.install_ai_packages(missing, parent_window)
                
                if success:
                    messagebox.showinfo("Installation Complete",
                                      f"✅ AI modules installed successfully!\n\n"
                                      f"Provider: {provider_name}\n"
                                      f"Location: {install_location}\n\n"
                                      f"AI-assisted features are now ready to use.",
                                      parent=parent_window)
                else:
                    messagebox.showerror("Installation Failed",
                                       f"❌ Failed to install AI modules.\n\n"
                                       f"Please try installing manually:\n"
                                       f"pip install {' '.join(missing)}",
                                       parent=parent_window)
            else:
                messagebox.showinfo("Installation Skipped",
                                  f"AI modules were not installed.\n\n"
                                  f"You can install them later with:\n"
                                  f"pip install {' '.join(missing)}",
                                  parent=parent_window)
                
        except Exception as e:
            if parent_window:
                messagebox.showerror("Error",
                                   f"Error checking AI modules: {str(e)}",
                                   parent=parent_window)
            if self.logger:
                self.logger.log(f"Error in AI modules check: {str(e)}")
    
    def create_ai_provider(self, provider_name: str, api_key: str, ollama_url: str = None, ollama_model: str = None):
        """Create an AI provider instance"""
        if not AI_PROVIDERS_AVAILABLE:
            return None

        try:
            ai_logger = Logger(self.log)
            return create_ai_provider(provider_name, api_key, ai_logger, ollama_url, ollama_model)
        except Exception as e:
            self.log(f"Error creating AI provider: {e}")
            return None
    
    def create_local_git_manager(self, github_token: str):
        """Create a LocalGitManager instance"""
        if not AI_PROVIDERS_AVAILABLE:
            return None
        
        try:
            ai_logger = Logger(self.log)
            return LocalGitManager(ai_logger, github_token)
        except Exception as e:
            self.log(f"Error creating LocalGitManager: {e}")
            return None
    
    def get_last_diff_content(self) -> str:
        """Get the last generated diff content for display in the UI"""
        return self.last_diff_content
    
    def clear_diff_content(self):
        """Clear the stored diff content"""
        self.last_diff_content = ""