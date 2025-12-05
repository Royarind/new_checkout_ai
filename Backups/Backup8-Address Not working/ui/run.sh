#!/bin/bash

echo "================================"
echo "🚀 Starting CHKout.ai"
echo "================================"
echo ""

# Check if virtual environment exists
if [ ! -d "../venv" ]; then
    echo "⚠️  Virtual environment not found"
    echo "Creating virtual environment..."
    python3 -m venv ../venv
fi

# Activate virtual environment
source ../venv/bin/activate

# Install dependencies
echo "📦 Installing dependencies..."
pip install -q -r requirements.txt

# Run the app
echo ""
echo "================================"
echo "✅ CHKout.ai is starting..."
echo "================================"
echo "📱 Open: http://localhost:8050"
echo "================================"
echo ""

python app.py
