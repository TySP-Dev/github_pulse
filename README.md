# GitHub Pulse

A Python-based GUI application for GitHub automation workflows.

## Project Structure

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
├── README.md               # This file
├── SETUP.md                # Setup guide
└── LICENSE                 # License information
```

## Prerequisites

- Python 3.8 or higher
- Git installed and configured
- GitHub account with repository access

## Quick Start

1. **Clone the repository**
   ```bash
   git clone https://github.com/TySP-Dev/github_automation.git
   cd github_automation/application
   ```

2. **Create and activate virtual environment**
   ```bash
   # Create virtual environment
   python -m venv venv

   # Activate (Windows)
   venv\Scripts\activate

   # Activate (macOS/Linux)
   source venv/bin/activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Run the application**
   ```bash
   python app.py
   ```

## Configuration

Configuration is managed through a `.env` file or settings dialog in the application.

See [SETUP.md](SETUP.md) for detailed setup instructions.

## Contributing

This project welcomes contributions and suggestions. Most contributions require you to agree to a
Contributor License Agreement (CLA) declaring that you have the right to, and actually do, grant us
the rights to use your contribution.

## License

See [LICENSE](LICENSE) file for details.

## Trademarks

This project may contain trademarks or logos for projects, products, or services. Authorized use of Microsoft
trademarks or logos is subject to and must follow
[Microsoft's Trademark & Brand Guidelines](https://www.microsoft.com/legal/intellectualproperty/trademarks/usage/general).
Use of Microsoft trademarks or logos in modified versions of this project must not cause confusion or imply Microsoft sponsorship.
Any use of third-party trademarks or logos are subject to those third-party's policies.
