# Build Instructions

> [!NOTE]
> Building has only been tested for **linux**.
> Please report bugs with building on any other platform.

## Prerequisites

- [Node.js](https://nodejs.org/) (v18+)
- [Git](https://git-scm.com/)
- Flet v0.28.0
- Flutter SDK v3.29.0 (Flet will install this automatically, but you can also [install it manually](https://docs.flutter.dev/get-started/install))
- [Visual Studio 2016 (Windows Users)](https://aka.ms/vs/16/release/vs_community.exe) 
- Android Studio (for Android builds)
- Xcode (for iOS builds)
- Any required package managers (e.g., npm, yarn)

> [!IMPORTANT]
> Flet v0.28.9 only supports Flutter SDK v3.29.0. Using other versions may lead to build failures.
> Flutter SDK v3.29.0 only supports Visual Studio 2016 on Windows. Ensure you have the correct version installed.

## Clone the Repository

```bash
git clone https://github.com/TySP-Dev/github_pulse.git
cd github_pulse/src
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
# For dev dependencies
pip install -r requirements/requirements-dev.txt
```

```bash
# Linux Dependencies (Ubuntu/Debian)
sudo apt update
sudo apt upgrade
sudo apt install clang cmake ninja-build pkg-config libgtk-3-dev liblzma-dev
```

## Setup Flutte

```bash
# Set ICU data file path (Windows example)
$env:FLUTTER_ICU_DATA_FILE="C:\path\to\flutter\bin\cache\artifacts\engine\windows-x64\icudtl.dat" 
```

# Example path $env:FLUTTER_ICU_DATA_FILE="C:\Users\<username>\flutter\bin\cache\artifacts\engine\windows-x64\icudtl.dat"

```bash
# Verify Flutter installation
flutter --version
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

> [!NOTE]
> Ensure you are in the `src` directory of the project and the Python virtual environment is activated. `venv\Scripts\activate` (Windows) or `source venv/bin/activate` (macOS/Linux).

```bash
# Windows
flet build windows
```

```bash
# Linux
flet build linux
```

```bash
# Android
flet build apk
```

```bash
# macOS
flet build macos
```

```bash
# iOS
flet build ios
```
## Additional Notes

- See `README.md` for more details.
- For troubleshooting, check the logs or open an issue.
- Customize build scripts in `package.json` as needed.