"""
AI Action Planner
Generates and executes action plans for GitHub issues and PRs using AI
"""

import json
import re
import requests
from typing import List, Dict, Any, Optional, Callable
from pathlib import Path


class ActionPlan:
    """Represents an AI-generated action plan"""

    def __init__(self, title: str, steps: List[Dict[str, Any]], context: Dict[str, Any]):
        self.title = title
        self.steps = steps  # List of {description, file_path, changes, completed}
        self.context = context  # PR/Issue context
        self.completed_steps = []
        self.failed_steps = []

    def to_dict(self) -> Dict[str, Any]:
        """Convert plan to dictionary"""
        return {
            'title': self.title,
            'steps': self.steps,
            'context': self.context,
            'completed_steps': self.completed_steps,
            'failed_steps': self.failed_steps
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ActionPlan':
        """Create plan from dictionary"""
        plan = cls(data['title'], data['steps'], data['context'])
        plan.completed_steps = data.get('completed_steps', [])
        plan.failed_steps = data.get('failed_steps', [])
        return plan


class OllamaProvider:
    """Simple Ollama API provider for AI action planning"""

    def __init__(self, base_url: str, model: str, logger):
        self.base_url = base_url.rstrip('/')
        self.model = model
        self.logger = logger

    def generate(self, prompt: str) -> Optional[str]:
        """Generate a response from Ollama"""
        try:
            response = requests.post(
                f"{self.base_url}/api/generate",
                json={
                    "model": self.model,
                    "prompt": prompt,
                    "stream": False
                },
                timeout=120
            )
            response.raise_for_status()
            result = response.json()
            return result.get('response', '')
        except Exception as e:
            self.logger.log(f"❌ Ollama API error: {str(e)}")
            return None

    def make_change(self, file_content: str, old_text: str, new_text: str, file_path: str, custom_instructions: str = None) -> Optional[str]:
        """Make changes to file content using Ollama"""
        # Try direct replacement first
        if old_text and old_text.strip() in file_content:
            return file_content.replace(old_text.strip(), new_text.strip())

        # Use Ollama to make intelligent changes
        prompt = f"""You are a code modification assistant. Modify the following file according to the instructions.

File: {file_path}

Current Content:
```
{file_content}
```

Instructions: {new_text}
{f'Additional context: {custom_instructions}' if custom_instructions else ''}

Return ONLY the complete modified file content. Do not include explanations or markdown code blocks."""

        return self.generate(prompt)


class AIActionPlanner:
    """Generates and executes action plans using AI"""

    def __init__(self, ai_manager, logger, config_manager):
        self.ai_manager = ai_manager
        self.logger = logger
        self.config_manager = config_manager

    def generate_plan(self, item, custom_instructions: str = "") -> Optional[ActionPlan]:
        """
        Generate an action plan for a PR or Issue

        Args:
            item: The PR or Issue (WorkflowItem object or dict)
            custom_instructions: Optional user-provided instructions

        Returns:
            ActionPlan object or None if generation failed
        """
        # Handle both WorkflowItem objects and dictionaries
        if hasattr(item, 'item_type'):
            # It's a WorkflowItem object
            item_type = item.item_type
            item_number = item.number
            title = item.title
            body = item.body or ''
            repo = getattr(item, 'repo', None)
        else:
            # It's a dictionary
            item_type = item.get('type', 'unknown')
            item_number = item.get('number')
            title = item.get('title', 'Untitled')
            body = item.get('body', '')
            repo = item.get('repo')

        self.logger.log(f"🤖 Generating action plan for {item_type} #{item_number}...")

        # Get AI provider
        config = self.config_manager.get_config()
        ai_provider_name = config.get('AI_PROVIDER', 'none').lower()

        if ai_provider_name == 'none' or not ai_provider_name:
            self.logger.log("❌ No AI provider configured. Please configure in Settings.")
            return None

        # Get provider instance
        provider = self._get_ai_provider(ai_provider_name, config)
        if not provider:
            return None

        # Generate the plan using AI
        try:
            self.logger.log(f"📤 Calling AI provider: {type(provider).__name__}")
            plan_text = self._call_ai_for_plan(provider, item_type, title, body, custom_instructions)

            if not plan_text:
                self.logger.log("❌ AI did not generate a plan (empty response)")
                return None

            self.logger.log(f"📥 Received response from AI ({len(plan_text)} characters)")
            self.logger.log(f"📄 Response preview: {plan_text[:200]}...")

            # Parse the plan
            self.logger.log("🔍 Parsing AI response into steps...")
            steps = self._parse_plan(plan_text)

            if not steps:
                self.logger.log("❌ Could not parse action steps from AI response")
                return None

            # Get repo from item or config
            if repo is None:
                repo = config.get('GITHUB_REPO', '')

            plan = ActionPlan(
                title=f"Action Plan for {item_type.upper()} #{item_number}: {title}",
                steps=steps,
                context={
                    'item_type': item_type,
                    'item_number': item_number,
                    'item_title': title,
                    'item_body': body,
                    'repo': repo
                }
            )

            self.logger.log(f"✅ Generated plan with {len(steps)} steps")
            return plan

        except Exception as e:
            self.logger.log(f"❌ Error generating plan: {str(e)}")
            return None

    def _get_ai_provider(self, provider_name: str, config: Dict[str, Any]):
        """Get the AI provider instance"""
        try:
            if provider_name in ['claude', 'anthropic']:
                # Try both CLAUDE_API_KEY and ANTHROPIC_API_KEY for compatibility
                api_key = config.get('CLAUDE_API_KEY')
                if not api_key:
                    api_key = config.get('ANTHROPIC_API_KEY')
                if not api_key:
                    self.logger.log("❌ Claude API key not found in secure storage (tried both CLAUDE_API_KEY and ANTHROPIC_API_KEY)")
                    return None
                self.logger.log("ℹ️  Initializing Claude provider...")
                from . import ai_manager
                provider = ai_manager.ClaudeProvider(api_key, self.logger)
                self.logger.log("✅ Claude provider initialized successfully")
                return provider

            elif provider_name in ['chatgpt', 'openai']:
                api_key = config.get('OPENAI_API_KEY')
                if not api_key:
                    self.logger.log("❌ OpenAI API key not found in secure storage")
                    return None
                self.logger.log("ℹ️  Initializing ChatGPT provider...")
                from . import ai_manager
                provider = ai_manager.ChatGPTProvider(api_key, self.logger)
                self.logger.log("✅ ChatGPT provider initialized successfully")
                return provider

            elif provider_name == 'ollama':
                # Ollama doesn't need an API key, uses URL from config
                ollama_url = config.get('OLLAMA_URL', 'http://localhost:11434')
                ollama_model = config.get('OLLAMA_MODEL', 'llama2')
                self.logger.log(f"ℹ️  Using Ollama at {ollama_url} with model {ollama_model}")
                # Create a simple Ollama provider wrapper
                return OllamaProvider(ollama_url, ollama_model, self.logger)

            else:
                self.logger.log(f"❌ Unsupported AI provider: {provider_name}")
                return None

        except Exception as e:
            self.logger.log(f"❌ Error creating AI provider: {str(e)}")
            return None

    def _call_ai_for_plan(self, provider, item_type: str, title: str, body: str, custom_instructions: str) -> Optional[str]:
        """Call AI to generate an action plan"""

        prompt = f"""You are an expert software engineer tasked with creating an actionable plan to address a GitHub {item_type}.

{item_type.upper()} Title: {title}

{item_type.upper()} Description:
{body}

{"Additional Instructions: " + custom_instructions if custom_instructions else ""}

Please create a detailed action plan with specific, executable steps. For each step, specify:
1. What needs to be done (clear description)
2. Which file(s) need to be modified (if applicable)
3. What changes should be made (if applicable)

Format your response as a JSON array of steps, where each step has:
- "description": A clear description of what to do
- "file_path": Path to the file to modify (or null if not file-specific)
- "changes": Description of changes to make (or null if not applicable)
- "action_type": One of ["modify_file", "create_file", "delete_file", "investigate", "test", "document"]

Example format:
```json
[
  {{
    "description": "Fix the authentication bug in login handler",
    "file_path": "src/auth/login.py",
    "changes": "Update the password validation logic to handle special characters correctly",
    "action_type": "modify_file"
  }},
  {{
    "description": "Add unit tests for authentication",
    "file_path": "tests/test_auth.py",
    "changes": "Add test cases for special characters in passwords",
    "action_type": "create_file"
  }}
]
```

IMPORTANT: Return ONLY the JSON array, no other text before or after."""

        try:
            if isinstance(provider, OllamaProvider):
                # Use Ollama
                self.logger.log(f"🤖 Calling Ollama AI to generate plan...")
                return provider.generate(prompt)

            elif hasattr(provider, '_generate_updated_document'):
                # Use Claude's document generation
                self.logger.log(f"🤖 Calling Claude AI to generate plan...")
                import anthropic
                client = anthropic.Anthropic(api_key=provider.api_key)

                message = client.messages.create(
                    model="claude-sonnet-4-5",
                    max_tokens=4096,
                    messages=[{"role": "user", "content": prompt}]
                )

                return message.content[0].text

            elif hasattr(provider, 'client'):
                # Use OpenAI/ChatGPT
                self.logger.log(f"🤖 Calling ChatGPT AI to generate plan...")
                response = provider.client.chat.completions.create(
                    model="gpt-4",
                    messages=[{"role": "user", "content": prompt}],
                    max_tokens=4096
                )

                self.logger.log(f"✅ ChatGPT response received")
                return response.choices[0].message.content

            else:
                self.logger.log(f"❌ Unknown provider type: {type(provider).__name__}")
                return None

        except Exception as e:
            self.logger.log(f"❌ AI API call failed: {str(e)}")
            import traceback
            self.logger.log(f"❌ Traceback: {traceback.format_exc()}")
            return None

    def _parse_plan(self, plan_text: str) -> List[Dict[str, Any]]:
        """Parse the AI-generated plan text into structured steps"""

        try:
            # Extract JSON from response (might be wrapped in markdown)
            json_match = re.search(r'```json\s*(\[.*?\])\s*```', plan_text, re.DOTALL)
            if json_match:
                json_text = json_match.group(1)
            else:
                # Try to find JSON array directly
                json_match = re.search(r'\[.*\]', plan_text, re.DOTALL)
                if json_match:
                    json_text = json_match.group(0)
                else:
                    self.logger.log("⚠️  Could not find JSON in AI response")
                    return []

            # Parse JSON
            steps = json.loads(json_text)

            # Validate and clean up steps
            validated_steps = []
            for i, step in enumerate(steps):
                if isinstance(step, dict):
                    validated_step = {
                        'step_number': i + 1,
                        'description': step.get('description', f'Step {i+1}'),
                        'file_path': step.get('file_path'),
                        'changes': step.get('changes'),
                        'action_type': step.get('action_type', 'investigate'),
                        'completed': False,
                        'status': 'pending'
                    }
                    validated_steps.append(validated_step)

            self.logger.log(f"✅ Successfully parsed {len(validated_steps)} steps from AI response")
            return validated_steps

        except json.JSONDecodeError as e:
            self.logger.log(f"❌ Failed to parse JSON: {str(e)}")
            self.logger.log(f"Response was: {plan_text[:500]}...")
            return []
        except Exception as e:
            self.logger.log(f"❌ Error parsing plan: {str(e)}")
            return []

    def execute_plan(
        self,
        plan: ActionPlan,
        local_repo_path: str,
        progress_callback: Optional[Callable[[int, int, str], None]] = None,
        log_callback: Optional[Callable[[str], None]] = None
    ) -> Dict[str, Any]:
        """
        Execute an action plan

        Args:
            plan: The ActionPlan to execute
            local_repo_path: Path to local git repository
            progress_callback: Callback function(current_step, total_steps, message)
            log_callback: Callback function for logging thought process

        Returns:
            Dictionary with execution results
        """
        def log(message):
            """Helper to log to both logger and callback"""
            self.logger.log(message)
            if log_callback:
                log_callback(message)

        log(f"▶️  Starting execution of plan: {plan.title}")

        if not local_repo_path or not Path(local_repo_path).exists():
            log(f"❌ Local repository path not found: {local_repo_path}")
            return {'success': False, 'error': 'Invalid local repository path'}

        total_steps = len(plan.steps)
        completed = 0
        failed = 0

        for i, step in enumerate(plan.steps):
            step_num = step['step_number']

            # Mark step as in-progress
            step['status'] = 'in_progress'
            if progress_callback:
                progress_callback(i + 1, total_steps, f"Executing step {step_num}...")

            log(f"\n📍 Step {step_num}/{total_steps}: {step['description']}")

            try:
                result = self._execute_step(step, local_repo_path, plan.context, log)

                if result['success']:
                    step['completed'] = True
                    step['status'] = 'completed'
                    plan.completed_steps.append(step_num)
                    completed += 1
                    log(f"✅ Step {step_num} completed")
                else:
                    step['status'] = 'failed'
                    step['error'] = result.get('error', 'Unknown error')
                    plan.failed_steps.append(step_num)
                    failed += 1
                    log(f"❌ Step {step_num} failed: {result.get('error')}")

            except Exception as e:
                step['status'] = 'failed'
                step['error'] = str(e)
                plan.failed_steps.append(step_num)
                failed += 1
                log(f"❌ Step {step_num} failed with exception: {str(e)}")

        log(f"\n📊 Execution complete: {completed}/{total_steps} steps successful, {failed} failed")

        # If we made changes successfully, commit and push them
        if completed > 0:
            try:
                log("\n🔧 Committing and pushing changes...")

                # Get PR/Issue info from context
                item_type = plan.context.get('item_type', 'item')
                item_number = plan.context.get('item_number', 'unknown')
                item_title = plan.context.get('item_title', 'changes')

                # Commit message
                commit_msg = f"AI: Execute action plan for {item_type} #{item_number}\n\n{item_title}\n\nAutomated changes by GitHub Pulse AI"

                # Get current branch (should be the PR branch)
                import subprocess
                result = subprocess.run(
                    ['git', 'rev-parse', '--abbrev-ref', 'HEAD'],
                    cwd=local_repo_path,
                    capture_output=True,
                    text=True,
                    timeout=10
                )
                current_branch = result.stdout.strip() if result.returncode == 0 else 'main'
                log(f"📍 Current branch: {current_branch}")

                # Stage all changes
                log("📝 Staging changes...")
                subprocess.run(['git', 'add', '-A'], cwd=local_repo_path, check=True, timeout=10)

                # Check if there are changes to commit
                result = subprocess.run(
                    ['git', 'diff', '--cached', '--quiet'],
                    cwd=local_repo_path,
                    timeout=10
                )

                if result.returncode != 0:  # There are changes
                    # Commit
                    log("💾 Committing changes...")
                    subprocess.run(
                        ['git', 'commit', '-m', commit_msg],
                        cwd=local_repo_path,
                        check=True,
                        timeout=10
                    )

                    # Push
                    log(f"🚀 Pushing to {current_branch}...")
                    subprocess.run(
                        ['git', 'push', 'origin', current_branch],
                        cwd=local_repo_path,
                        check=True,
                        timeout=30
                    )
                    log(f"✅ Changes pushed to {current_branch}")
                else:
                    log("ℹ️  No changes to commit")

            except subprocess.TimeoutExpired:
                log("⚠️  Git operation timed out")
            except subprocess.CalledProcessError as e:
                log(f"⚠️  Git operation failed: {e}")
            except Exception as e:
                log(f"⚠️  Error during git commit/push: {str(e)}")

        return {
            'success': failed == 0,
            'completed': completed,
            'failed': failed,
            'total': total_steps,
            'plan': plan
        }

    def _execute_step(self, step: Dict[str, Any], local_repo_path: str, context: Dict[str, Any], log=None) -> Dict[str, Any]:
        """Execute a single step of the plan"""

        action_type = step.get('action_type', 'investigate')
        file_path = step.get('file_path')
        changes = step.get('changes')

        # Use log function if provided, otherwise fall back to logger
        log_func = log if log else self.logger.log

        if action_type == 'modify_file' and file_path:
            return self._modify_file(file_path, changes, local_repo_path, log_func)

        elif action_type == 'create_file' and file_path:
            return self._create_file(file_path, changes, local_repo_path, log_func)

        elif action_type == 'delete_file' and file_path:
            return self._delete_file(file_path, local_repo_path, log_func)

        else:
            # For investigate, test, document actions, just mark as completed
            # (requires manual intervention)
            log_func(f"ℹ️  Manual action required: {step['description']}")
            return {'success': True, 'message': 'Manual action logged'}

    def _modify_file(self, file_path: str, changes: str, local_repo_path: str, log=None) -> Dict[str, Any]:
        """Modify a file using AI"""

        log_func = log if log else self.logger.log
        full_path = Path(local_repo_path) / file_path

        if not full_path.exists():
            return {'success': False, 'error': f'File not found: {file_path}'}

        try:
            log_func(f"📝 Reading file: {file_path}")
            # Read current content
            with open(full_path, 'r', encoding='utf-8') as f:
                current_content = f.read()

            # Get AI provider to make changes
            config = self.config_manager.get_config()
            provider_name = config.get('AI_PROVIDER', 'none').lower()
            provider = self._get_ai_provider(provider_name, config)

            if not provider:
                return {'success': False, 'error': 'AI provider not available'}

            # Use AI to make the changes
            log_func(f"🤖 Using AI to modify {file_path}...")
            log_func(f"🔍 Analyzing changes needed...")
            updated_content = provider.make_change(
                file_content=current_content,
                old_text=current_content[:200] + "...",  # Context
                new_text=changes,  # What to change
                file_path=str(full_path),
                custom_instructions=changes
            )

            if updated_content and updated_content != current_content:
                log_func(f"💾 Writing changes to {file_path}...")
                # Write updated content
                with open(full_path, 'w', encoding='utf-8') as f:
                    f.write(updated_content)

                log_func(f"✅ Successfully modified {file_path}")
                return {'success': True, 'file': file_path}
            else:
                return {'success': False, 'error': 'AI could not generate changes'}

        except Exception as e:
            return {'success': False, 'error': f'Error modifying file: {str(e)}'}

    def _create_file(self, file_path: str, content: str, local_repo_path: str, log=None) -> Dict[str, Any]:
        """Create a new file"""

        log_func = log if log else self.logger.log
        full_path = Path(local_repo_path) / file_path

        if full_path.exists():
            return {'success': False, 'error': f'File already exists: {file_path}'}

        try:
            log_func(f"📄 Creating new file: {file_path}")
            # Create parent directories if needed
            full_path.parent.mkdir(parents=True, exist_ok=True)

            # Create file with content
            with open(full_path, 'w', encoding='utf-8') as f:
                f.write(content or f"# TODO: Implement {file_path}\n")

            log_func(f"✅ Created {file_path}")
            return {'success': True, 'file': file_path}

        except Exception as e:
            return {'success': False, 'error': f'Error creating file: {str(e)}'}

    def _delete_file(self, file_path: str, local_repo_path: str, log=None) -> Dict[str, Any]:
        """Delete a file"""

        log_func = log if log else self.logger.log
        full_path = Path(local_repo_path) / file_path

        if not full_path.exists():
            return {'success': False, 'error': f'File not found: {file_path}'}

        try:
            log_func(f"🗑️  Deleting file: {file_path}")
            full_path.unlink()
            log_func(f"✅ Deleted {file_path}")
            return {'success': True, 'file': file_path}

        except Exception as e:
            return {'success': False, 'error': f'Error deleting file: {str(e)}'}
