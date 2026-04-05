#!/bin/bash
# ═══════════════════════════════════════════════════════════════
#  POLY_TEX Setup
# ═══════════════════════════════════════════════════════════════
echo "Setting up POLY_TEX..."

# Create venv
python3 -m venv venv
source venv/bin/activate

# Install deps
pip install requests python-dotenv --quiet

# Create .env from example
if [ ! -f .env ]; then
    cp .env.example .env
    echo "Created .env — add your Polymarket API keys"
fi

# Create dirs
mkdir -p logs data signals models

echo ""
echo "Setup complete. Next steps:"
echo "  1. Add API keys to .env"
echo "  2. source venv/bin/activate"
echo "  3. python3 poly_tex.py"
echo ""
echo "DRY_RUN=True by default (no real bets until you set it False in config.py)"
