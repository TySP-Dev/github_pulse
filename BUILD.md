# Build Instructions

## Prerequisites

- [Node.js](https://nodejs.org/) (v18+)
- [Git](https://git-scm.com/)
- Flet v0.28.0
- Flutter SDK v3.29.0 (Use FVM for managing Flutter versions)
- [Visual Studio 2016 (Windows Users)](https://aka.ms/vs/16/release/vs_community.exe)
- Android Studio (for Android builds)
- Xcode (for iOS builds)
- Any required package managers (e.g., npm, yarn)

## Clone the Repository

```bash
git clone https://github.com/TySP-Dev/github_pulse.git
cd github_pulse/GitHub_Pulse
```

## Python Virtual Environment

```bash
# Create virtual environment
python -m venv venv

# Activate virtual environment
# On Windows:
venv\Scripts\activate

# On macOS/Linux:
source venv/bin/activate
```

## Install Dependencies

```bash
pip install -r requirements.txt
```

```bash
# Linux Dependencies (Ubuntu/Debian)
sudo apt update
sudo apt upgrade
sudo apt install clang cmake ninja-build pkg-config libgtk-3-dev liblzma-dev
```

## Setup Flutter

```bash
# Install FVM
dart pub global activate fvm
```

```bash
# Add to path
export PATH="$PATH":"$HOME/.pub-cache/bin"
```

```bash
# Set ICU data file path (Windows example)
$env:FLUTTER_ICU_DATA_FILE="C:\Users\micro\fvm\versions\3.29.0\bin\cache\artifacts\engine\windows-x64\icudtl.dat"
```

```bash
# Install Flutter version 3.29.0
fvm install 3.29.0
```

```bash
fvm use 3.29.0 --force
```

```bash
# Get cached Flutter versions
fvm list
```

```bash
# Create a temporary alias for Flutter (Windows example)
function flutter { fvm flutter $args }
```

```bash
# Create a temporary alias for Flutter (Linux / MacOS example)
alias flutter="fvm flutter"
```

```bash
# Verify Flutter installation
flutter --version
# Should show Flutter 3.29.0
```

```bash
# Run Flutter doctor
flutter doctor
```

```bash
# Flet doctor
python -m flet.cli doctor
```

```bash
# Accept Android licenses (if building for Android)
flutter doctor --android-licenses
```

```bash
# Precache Flutter artifacts (All platforms)
flutter precache --all
```

```bash
# precache Flutter artifacts (Windows example)
flutter precache --windows
```

```bash
# precache Flutter artifacts (Linux example)
flutter precache --linux
```

```bash
# precache Flutter artifacts (MacOS example)
flutter precache --macos
```

```bash
# precache Flutter artifacts (iOS example)
flutter precache --ios
```

```bash
# precache Flutter artifacts (Android example)
flutter precache --android
```

>[!NOTE]
> Only precache the platforms you intend to build for.

## Build the Application

```bash
# Windows
python -m flet.cli build windows
```

```bash
# Linux
python -m flet.cli build linux
```

```bash
# Android
python -m flet.cli build apk
```

```bash
# macOS
python -m flet.cli build macos
```

```bash
# iOS
python -m flet.cli build ios
```
## Additional Notes

- See `README.md` for more details.
- For troubleshooting, check the logs or open an issue.
- Customize build scripts in `package.json` as needed.