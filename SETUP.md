# GitHub Pulse - Setup Guide

## Overview

A Python-based GUI application for GitHub automation workflows.

## Quick Start

### Prerequisites

- **Python 3.8+** installed on your system
- **Git** installed and configured
- **GitHub** account with repository access

### Installation

1. **Clone/Download the Repository**

   ```bash
   git clone https://github.com/TySP-Dev/github_automation.git
   cd github_automation/application
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
   pip install -r requirements.txt
   ```

4. **Run the Application**

   ```bash
   python app.py
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
├── application/              # Main application directory
│   ├── app.py               # Application entry point
│   ├── requirements.txt     # Python dependencies
│   └── app_components/      # Application modules
│       ├── ai_manager.py           # AI provider integration
│       ├── cache_manager.py        # Caching functionality
│       ├── config_manager.py       # Configuration management
│       ├── github_api.py           # GitHub API client
│       ├── main_gui.py             # Main GUI interface
│       ├── settings_dialog.py      # Settings dialog
│       └── utils.py                # Utility functions
├── media/                   # Images and assets
├── README.md               # Project overview
├── SETUP.md                # This setup guide
└── LICENSE                 # License information
```

## Configuration

### First-Time Setup

1. **Launch the application** and click "Settings" button
2. **Configure required fields** in the Settings dialog

#### GitHub Configuration (Required)

- **Personal Access Token**: GitHub PAT for repository access
  - Create at: `https://github.com/settings/tokens`
  - Required scopes: repo, workflow
- **Target Repository**: Format as `owner/repository`
  - Example: `microsoft/example-repo`
- **Forked Repository**: Your fork of the target repository (if applicable)
  - Example: `yourusername/example-repo`
- **Local Repo Path**: Directory where repositories will be/are cloned
  - Example: `C:\Users\yourname\repos\`

#### AI Provider Configuration (Optional)

- **Provider**: Choose from:
  - `none` - No AI assistance
  - `claude` - Anthropic Claude API
  - `chatgpt` - OpenAI ChatGPT API
  - `github-copilot` - GitHub Models API
- **API Keys**: Provide keys based on your chosen provider

### Configuration Tips

**Start Simple**: Configure only GitHub initially
**Test Connection**: Use "Test Connection" button to verify settings
**AI Enhancement**: Add AI provider later for automated processing

## Security Best Practices

### Token Security

- **Never commit** `.env` file to version control
- **Rotate tokens** regularly (90 days recommended)
- **Minimum permissions**: Use least privilege principle
- **Secure storage**: Store tokens in secure password manager

### Repository Access

- **Fork workflow**: Use personal forks for changes
- **Branch isolation**: Each task gets separate branch
- **Review process**: All changes go through pull requests

## Support

### Getting Help

1. **Check logs** in Processing Log tab for detailed errors
2. **Test connections** using Settings dialog test button
3. **Review configuration** for missing or incorrect values

### Common Resources

- [GitHub PAT Documentation](https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/creating-a-personal-access-token)
- [Git Configuration Guide](https://git-scm.com/book/en/v2/Getting-Started-First-Time-Git-Setup)
