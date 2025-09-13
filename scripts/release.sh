#!/bin/bash
# Quick release script for TaskPanel

set -e

echo "🚀 TaskPanel Release Script"
echo "=========================="

# Check if we're on main branch
CURRENT_BRANCH=$(git branch --show-current)
if [ "$CURRENT_BRANCH" != "main" ]; then
    echo "❌ Error: Must be on main branch. Current branch: $CURRENT_BRANCH"
    exit 1
fi

# Check if working directory is clean
if [ -n "$(git status --porcelain)" ]; then
    echo "❌ Error: Working directory is not clean. Please commit your changes."
    git status --short
    exit 1
fi

# Get current version
CURRENT_VERSION=$(python -c "import sys; sys.path.insert(0, 'src'); import taskpanel; print(taskpanel.__version__)" 2>/dev/null || echo "unknown")
echo "📍 Current version: $CURRENT_VERSION"

# Ask for new version
echo ""
echo "📝 Enter new version (e.g., 1.0.1):"
read -r NEW_VERSION

if [ -z "$NEW_VERSION" ]; then
    echo "❌ Error: Version cannot be empty"
    exit 1
fi

# Validate version format (basic check)
if [[ ! $NEW_VERSION =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
    echo "❌ Error: Version must be in format x.y.z (e.g., 1.0.1)"
    exit 1
fi

echo ""
echo "🔄 Creating release v$NEW_VERSION..."

# Run tests first
echo "🧪 Running tests..."
if ! make test; then
    echo "❌ Error: Tests failed. Please fix before releasing."
    exit 1
fi

# Build and check package
echo "📦 Building package..."
if ! make build-check; then
    echo "❌ Error: Package build failed."
    exit 1
fi

# Create and push tag
echo "🏷️  Creating and pushing tag..."
git tag "v$NEW_VERSION"
git push origin "v$NEW_VERSION"

echo ""
echo "✅ Success! Tag v$NEW_VERSION has been created and pushed."
echo ""
echo "📋 Next steps:"
echo "1. Go to: https://github.com/Wenutu/TaskPanel/releases/new"
echo "2. Select tag: v$NEW_VERSION"
echo "3. Write release notes"
echo "4. Click 'Publish release'"
echo "5. GitHub Actions will automatically push to PyPI"
echo ""
echo "🔗 Or use this direct link:"
echo "   https://github.com/Wenutu/TaskPanel/releases/new?tag=v$NEW_VERSION"
