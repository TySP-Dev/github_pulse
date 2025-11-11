# MicrosoftDocFlow Tool - Setup Guide

## Overview

This tool automates the process of converting Azure DevOps work items into GitHub pull requests with AI assistance. It fetches work items, processes documentation changes, and creates pull requests with proper diffs.

## Quick Start

### Prerequisites

- **Python 3.8+** installed on your system
- **Git** installed and configured
- **Azure DevOps** account with work items
- **GitHub** account with repository access
- **AI Provider** account (optional, for enhanced processing)

### Installation

1. **Clone/Download the Repository**

   ```bash
   git clone https://github.com/yourusername/github_automation.git
   cd github_automation
   ```

2. **Create Virtual Environment** (Recommended)

   ```bash
   # Create virtual environment
   python -m venv venv
   
   # Activate virtual environment
   # On Windows:
   venv\Scripts\activate
   
   # On macOS/Linux:
   source venv/bin/activate
   ```

    To deactivate the environment when done:

    ```bash
    deactivate
    ```

3. **Install Dependencies**

   ```bash
   pip install -r application/requirements.txt
   ```

4. **Run the Application**

   ```bash
   python application/app.py
   ```

### Virtual Environment Management

**Activating the environment** (when returning to the project):

- Windows: `venv\Scripts\activate`
- macOS/Linux: `source venv/bin/activate`

**Deactivating the environment** (when done working):

```bash
deactivate
```

**Why use a virtual environment?**

- **Isolation**: Keeps project dependencies separate from system Python
- **Clean installs**: Prevents conflicts with other Python projects
- **Reproducible**: Ensures consistent dependency versions
- **Safe updates**: Won't affect other projects when updating packages

## Project Structure

The project is organized as follows:

```text
github_automation/
├── application/              # Main application 
│   ├── app.py               # Application entry point
│   ├── requirements.txt     # Python dependencies
│   └── app_components/      # Application modules
│       ├── ai_manager.py           # AI provider 
│       ├── azure_devops_api.py     # Azure DevOps API 
│       ├── cache_manager.py        # Work item caching
│       ├── config_manager.py       # Configuration 
│       ├── dataverse_api.py        # Dataverse API 
│       ├── github_api.py           # GitHub API client
│       ├── main_gui.py             # Main GUI interface
│       ├── settings_dialog.py      # Settings dialog
│       ├── utils.py                # Utility functions
│       └── work_item_processor.py  # Work item 
├── media/                   # Images and assets
├── README.md               # Project overview
├── SETUP.md                # This setup guide
└── LICENSE                 # License information
```

## Configuration

### First-Time Setup

1. **Launch the application** and click "Settings" button
2. **Configure required fields** in the Settings dialog:

#### Azure DevOps Configuration (Required)

- **Query URL**: Your Azure DevOps query URL
  - Example: `https://dev.azure.com/yourorg/project/_queries/query/12345678-1234-1234-1234-123456789abc/`
  - Get this from Azure DevOps by creating/opening a query and copying the URL
- **Personal Access Token**: Azure DevOps PAT with work item read permissions
  - Create at: `https://dev.azure.com/yourorg/_usersSettings/tokens`
  - Required scopes: Work Items (Read/Write)

#### GitHub Configuration (Required)

- **Personal Access Token**: GitHub PAT for repository access
  - Create at: `https://github.com/settings/tokens`
  - Required scopes: repo, workflow
- **Target Repository**: Format as `owner/repository`
  - Example: `microsoft/fabric-docs`
- **Forked Repository**: Your fork of the target repository
  - Example: `yourusername/fabric-docs`
- **Local Repo Path**: Directory where repositories will be/are cloned
  - Example: `C:\Users\yourname\repos\`

#### AI Provider Configuration (Optional)

- **Provider**: Choose from:
  - `none` - GitHub Copilot via a automatic comment on the PR
  - `claude` - Anthropic Claude API
  - `chatgpt` - OpenAI ChatGPT API  
  - `github-copilot` - GitHub Models API
- **API Keys**: Provide keys based on your chosen provider
  - GitHub Token: Auto-defaults to GitHub PAT if left empty

### Configuration Tips

**Start Simple**: Configure only Azure DevOps and GitHub initially  
**Test Connection**: Use "Test Connection" button to verify settings  
**Cache Benefits**: Work items are cached for faster subsequent loads  
**AI Enhancement**: Add AI provider later for automated text processing  

## Usage Guide

### Basic Workflow

1. **Load Work Items**
   - Click "Fetch Work Items" to load work items from your query
   - Items are displayed in the "All Work Items" tab
   - Cached items load automatically on subsequent launches

2. **Select Work Item**
   - Navigate to "All Work Items" tab
   - **Double-click** any work item to select it as current
   - OR click "Set as Current Item" button
   - Selected item appears in "Current Work Item" tab

3. **Review Work Item Details**
   - **Work Item ID**: Click to open in Azure DevOps
   - **Nature of Request**: Description of required changes
   - **Document URL**: Target documentation URL
   - **Text to Change**: Current text that needs modification
   - **Proposed New Text**: Replacement text (editable)

4. **Process Changes**
   - **With AI**: If AI provider is configured and the AI provider is not `none`, click "Create PR" and the selected AI will be used
   - **Manual**: Click "Create PR" or "Create Issue" for manual processing / GitHub Copilot comment
   - **Dry Run**: Enable for testing without actual changes (Located in settings)

### Advanced Features

#### Work Item Navigation

- **Next/Previous**: Navigate through multiple work items
- **Edit Mode**: Click "Edit" to modify proposed text

#### Git Diff Viewer

- View file changes in the "Git Diff" tab
- Shows before/after comparison
- Automatic diff generation from repository changes

#### Processing Log

- Real-time activity logging in "Processing Log" tab
- Track API calls, file operations, and errors
- Detailed workflow visibility

## Advanced Configuration

### AI Provider Setup

#### Claude (Anthropic)

1. Get API key from [console.anthropic.com](https://console.anthropic.com)
2. Set provider to `claude`
3. Enter API key in settings
4. Cost: ~$0.01-0.05 per work item

#### ChatGPT (OpenAI)

1. Get API key from [platform.openai.com/api-keys](https://platform.openai.com/api-keys)
1. Set provider to `chatgpt`  
1. Enter API key in settings
1. Cost: ~$0.01-0.05 per work item

#### GitHub Copilot

1. Ensure GitHub account has Copilot access
2. Set provider to `github-copilot`
3. GitHub Token auto-defaults to GitHub PAT
4. Uses GitHub Models API

### Repository Management

#### Local Repository Setup

- **Automatic Cloning**: Repositories are cloned automatically to Local Repo Path if AI provider is used
- **Branch Management**: Creates feature branches for each work item
- **Sync Handling**: Keeps repositories updated with upstream changes

#### Forked Repository Workflow

1. **Fork** the target repository to your GitHub account
2. **Configure** both target and forked repositories in settings
3. **Automatic**: Tool manages branch creation and PR submission

### Custom Instructions

Add custom AI instructions in settings to guide processing:

```AI Prompt
Focus on technical accuracy and clear documentation.
Ensure all code examples are properly formatted.
Include relevant cross-references to related topics.
```

## 🛠️ Troubleshooting

### Common Issues

**"No work items found"**

- Verify Azure DevOps query URL is correct
- Check PAT has work item read permissions
- Ensure query returns results in Azure DevOps

**"Repository not found"**  

- Verify GitHub repository name format (`owner/repo`)
- Check GitHub PAT has repository access
- Ensure repository exists and is accessible

**"AI processing failed"**

- Verify API key is correct and has credits
- Check internet connection
- Review processing log for specific errors

**"Git operations failed"**

- Ensure Git is installed and configured
- Check Local Repo Path exists and is writable
- Verify GitHub authentication is working

### Performance Tips

**Use Cache**: Let items load from cache for faster startup  
**Dry Run**: Test changes before committing  
**Batch Processing**: Process multiple items in sequence  
**Monitor Logs**: Watch processing log for issues  

## Security Best Practices

### Token Security

- **Never commit** `.env` file to version control
- **Rotate tokens** regularly (90 days recommended)
- **Minimum permissions**: Use least privilege principle
- **Secure storage**: Store tokens in secure password manager

### Repository Access

- **Fork workflow**: Use personal forks for changes
- **Branch isolation**: Each work item gets separate branch
- **Review process**: All changes go through pull requests

## Support

### Getting Help

1. **Check logs** in Processing Log tab for detailed errors
2. **Test connections** using Settings dialog test button
3. **Review configuration** for missing or incorrect values
4. **Consult documentation** for API-specific issues

### Common Resources

- [Azure DevOps PAT Documentation](https://docs.microsoft.com/en-us/azure/devops/organizations/accounts/use-personal-access-tokens-to-authenticate)
- [GitHub PAT Documentation](https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/creating-a-personal-access-token)
- [Git Configuration Guide](https://git-scm.com/book/en/v2/Getting-Started-First-Time-Git-Setup)
