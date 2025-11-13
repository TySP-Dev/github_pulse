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
   git clone https://github.com/TySP-Dev/github_pulse.git
   cd github_pulse/src
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

3. **Install Dependencies**

   ```bash
   pip install -r requirements.txt
   ```

4. **Run the Application**

   ```bash
   python main.py
   ```

> [!NOTE]
> It is highly recommended to use a virtual environment to manage dependencies and avoid conflicts with other Python projects on your system.
> Ensure you activate the virtual environment each time you work on or start this application.

### Virtual Environment Management

**Activating the environment** (when returning to the project):

```bash
- Windows: `venv\Scripts\activate`
- macOS/Linux: `source venv/bin/activate`
```

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
github_pulse/
├── src/             # Main application directory
│   ├── app.py               # Application entry point
│   ├── requirements.txt     # Python dependencies
│   ├── assets               # Images for build
│   │   ├── icon.png         # Application icon
│   │   └── splash_android.png # Splash screen image
│   └── app_components/      # Application modules
│       ├── assets/          # Images and assets
│       │   ├── flow-diagram.png              # Workflow diagram              
│       │   ├── github_pulse_img.png          # GitHub Pulse image
│       │   ├── pulse_logo_gray_no_bkg.png  # GitHub Pulse logo
│       │   ├── pulse_logo_white_no_bkg_github.png          # Pulse logo
│       │   ├── pulse_logo_white_no_bkg.png               # Pulse logo with background
│       │   └── pulse_logo_white_w_black_bkg.png      # GitHub Pulse logo with background
│       ├── __init__.py          # Package initializer
│       ├── ai_manager.py           # AI provider integration
│       ├── cache_manager.py        # Caching functionality
│       ├── config_manager.py       # Configuration management
│       ├── github_api.py           # GitHub API client
│       ├── main_gui.py             # Main GUI interface
│       ├── processing_log_dialog.py  # Processing log dialog
│       ├── settings_dialog.py      # Settings dialog
│       ├── settings_manager.py     # Settings management
│       ├── utils.py                # Utility functions
│       └── workflow.py             # Workflow processing
├── assets/                   # Images and assets
├── README.md               # Readme file
├── SETUP.md                # This file
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
  - `ollama` - Ollama Local Models
- **Ollama Model**: Select model based on local availability
- **Ollama API Endpoint**: URL for Ollama AI server
- **API Keys**: Provide keys based on your chosen provider

### Configuration Tips

**Start Simple**: Configure only GitHub initially
**Test Connection**: Use "Test Connection" button to verify settings
**AI Enhancement**: Add AI provider later for automated processing
**Configuration File**: Settings are saved in `config.json` for persistence

## Security Best Practices

### Token Security

- **Use PATs** instead of passwords
- **Rotate tokens** regularly (90 days recommended)
- **Minimum permissions**: Use least privilege principle
- **Secure storage**: Store tokens in secure password manager
- **Avoid hardcoding**: Never hardcode tokens in source code
- **Secret management**: This project uses `keyring` for secure storage

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
