#!/bin/bash
#
# Kimi-PIMCP Installation Script for Linux/Mac
#

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
INSTALL_DIR="${HOME}/.local/share/kimi-pimcp"
VENV_DIR="${INSTALL_DIR}/venv"
CACHE_DIR="${HOME}/.kimi_cache"
BIN_DIR="${HOME}/.local/bin"
PYTHON_CMD=""

# Print functions
print_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check Python version
check_python() {
    print_info "Checking Python installation..."
    
    # Try different Python commands
    if command -v python3 &> /dev/null; then
        PYTHON_CMD="python3"
    elif command -v python &> /dev/null; then
        PYTHON_CMD="python"
    elif command -v python3.14 &> /dev/null; then
        PYTHON_CMD="python3.14"
    elif command -v python3.13 &> /dev/null; then
        PYTHON_CMD="python3.13"
    elif command -v python3.12 &> /dev/null; then
        PYTHON_CMD="python3.12"
    elif command -v python3.11 &> /dev/null; then
        PYTHON_CMD="python3.11"
    elif command -v python3.10 &> /dev/null; then
        PYTHON_CMD="python3.10"
    elif command -v python3.9 &> /dev/null; then
        PYTHON_CMD="python3.9"
    elif command -v python3.8 &> /dev/null; then
        PYTHON_CMD="python3.8"
    else
        print_error "Python is not installed. Please install Python 3.8 or higher."
        print_error "You can download it from: https://python.org"
        exit 1
    fi
    
    PYTHON_VERSION=$($PYTHON_CMD --version 2>&1 | awk '{print $2}')
    print_info "Found Python $PYTHON_VERSION at: $(which $PYTHON_CMD)"
    
    # Check version (need 3.8+)
    VERSION_MAJOR=$(echo $PYTHON_VERSION | cut -d. -f1)
    VERSION_MINOR=$(echo $PYTHON_VERSION | cut -d. -f2)
    
    if [ "$VERSION_MAJOR" -lt 3 ] || ([ "$VERSION_MAJOR" -eq 3 ] && [ "$VERSION_MINOR" -lt 8 ]); then
        print_error "Python 3.8 or higher is required. Found $PYTHON_VERSION"
        print_error "Please upgrade your Python installation."
        exit 1
    fi
    
    print_success "Python $PYTHON_VERSION is compatible (>= 3.8)"
}

# Create directories
create_directories() {
    print_info "Creating directories..."
    
    mkdir -p "$INSTALL_DIR"
    mkdir -p "$CACHE_DIR"
    mkdir -p "$BIN_DIR"
    
    print_success "Directories created"
}

# Copy project files
copy_files() {
    print_info "Copying project files..."
    
    SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    
    # Copy source files
    cp -r "$SCRIPT_DIR/src" "$INSTALL_DIR/"
    cp -r "$SCRIPT_DIR/data" "$INSTALL_DIR/" 2>/dev/null || true
    cp "$SCRIPT_DIR/config.yaml" "$INSTALL_DIR/" 2>/dev/null || true
    cp "$SCRIPT_DIR/requirements.txt" "$INSTALL_DIR/"
    
    print_success "Files copied to $INSTALL_DIR"
}

# Create virtual environment
create_venv() {
    print_info "Creating virtual environment with $PYTHON_CMD..."
    
    $PYTHON_CMD -m venv "$VENV_DIR"
    
    print_success "Virtual environment created at $VENV_DIR"
}

# Get Python path from venv
get_venv_python() {
    if [ -f "$VENV_DIR/bin/python" ]; then
        echo "$VENV_DIR/bin/python"
    elif [ -f "$VENV_DIR/bin/python3" ]; then
        echo "$VENV_DIR/bin/python3"
    else
        echo "$VENV_DIR/Scripts/python.exe"  # Windows fallback
    fi
}

# Install dependencies
install_dependencies() {
    print_info "Installing dependencies in virtual environment..."
    
    VENV_PYTHON=$(get_venv_python)
    
    # Upgrade pip
    "$VENV_PYTHON" -m pip install --upgrade pip
    
    # Install requirements
    "$VENV_PYTHON" -m pip install -r "$INSTALL_DIR/requirements.txt"
    
    print_success "Dependencies installed"
}

# Create launcher script
create_launcher() {
    print_info "Creating launcher script..."
    
    cat > "$BIN_DIR/kimi-pimcp" << EOF
#!/bin/bash
# Kimi-PIMCP Launcher

VENV_DIR="${HOME}/.local/share/kimi-pimcp/venv"
INSTALL_DIR="${HOME}/.local/share/kimi-pimcp"

# Activate virtual environment and run
if [ -f "\$VENV_DIR/bin/python" ]; then
    "\$VENV_DIR/bin/python" "\$INSTALL_DIR/src/server.py" "\$@"
elif [ -f "\$VENV_DIR/bin/python3" ]; then
    "\$VENV_DIR/bin/python3" "\$INSTALL_DIR/src/server.py" "\$@"
else
    echo "Error: Virtual environment not found"
    exit 1
fi
EOF
    
    chmod +x "$BIN_DIR/kimi-pimcp"
    
    print_success "Launcher created at $BIN_DIR/kimi-pimcp"
}

# Create Kimi-CLI configuration
create_kimi_config() {
    print_info "Creating Kimi-CLI configuration..."
    
    KIMI_CONFIG_DIR="${HOME}/.config/kimi"
    mkdir -p "$KIMI_CONFIG_DIR"
    
    cat > "$KIMI_CONFIG_DIR/mcp-servers.json" << EOF
{
  "mcpServers": {
    "kimi-pimcp": {
      "command": "$BIN_DIR/kimi-pimcp",
      "args": [],
      "env": {
        "PYTHONPATH": "$INSTALL_DIR/src"
      }
    }
  }
}
EOF
    
    print_success "Kimi-CLI configuration created"
}

# Add to PATH
add_to_path() {
    print_info "Checking PATH configuration..."
    
    SHELL_RC=""
    if [[ "$SHELL" == *"zsh"* ]]; then
        SHELL_RC="${HOME}/.zshrc"
    elif [[ "$SHELL" == *"bash"* ]]; then
        SHELL_RC="${HOME}/.bashrc"
    fi
    
    if [ -n "$SHELL_RC" ] && [ -f "$SHELL_RC" ]; then
        if ! grep -q "$BIN_DIR" "$SHELL_RC"; then
            print_info "Adding $BIN_DIR to PATH in $SHELL_RC"
            echo "export PATH=\"$BIN_DIR:\$PATH\"" >> "$SHELL_RC"
            print_warning "Please run: source $SHELL_RC"
        fi
    fi
}

# Download models
download_models() {
    print_info "Pre-downloading models (this may take a while)..."
    
    VENV_PYTHON=$(get_venv_python)
    
    "$VENV_PYTHON" << 'PYTHON_EOF'
from sentence_transformers import SentenceTransformer
print("Downloading embedding model...")
model = SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2')
print("Model downloaded successfully!")
PYTHON_EOF
    
    print_success "Models downloaded"
}

# Print final instructions
print_instructions() {
    VENV_PYTHON=$(get_venv_python)
    
    echo ""
    echo "========================================"
    print_success "Kimi-PIMCP Installation Complete!"
    echo "========================================"
    echo ""
    echo "Installation directory: $INSTALL_DIR"
    echo "Virtual environment: $VENV_DIR"
    echo "Python: $VENV_PYTHON"
    echo "Cache directory: $CACHE_DIR"
    echo ""
    echo "To use Kimi-PIMCP:"
    echo "  1. Run: kimi-pimcp"
    echo ""
    echo "Or manually:"
    echo "  $VENV_PYTHON $INSTALL_DIR/src/server.py"
    echo ""
    echo "The server will communicate via stdin/stdout using MCP protocol."
    echo ""
}

# Main installation
main() {
    echo "========================================"
    echo "  Kimi-PIMCP Installer"
    echo "========================================"
    echo ""
    
    check_python
    create_directories
    copy_files
    create_venv
    install_dependencies
    create_launcher
    create_kimi_config
    add_to_path
    download_models
    
    print_instructions
}

# Run main function
main "$@"
