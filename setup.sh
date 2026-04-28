#!/usr/bin/env bash
set -euo pipefail

# Ask for the bot token
read -s -p "Enter bot token: " TOKEN
echo
read -s -p "Confirm token: " TOKEN_CONFIRM
echo

# Ask for the DB Password
read -s -p "Enter password for PostgreSQL user 'botuser': " DB_PASS
echo
read -s -p "Confirm password: " DB_PASS_CONFIRM
echo

if [[ "$TOKEN" != "$TOKEN_CONFIRM" ]]; then
  echo "Tokens do not match."
  exit 1
fi

if [[ "$DB_PASS" != "$DB_PASS_CONFIRM" ]]; then
  echo "Passwords do not match."
  exit 1
fi

read -p "Enter gamemode for Bot: " GAMEMODE

# Variables
REPO_URL="http://192.168.178.217/felix/ztt-bot-full"
INSTALL_DIR="/opt/ztt-leaderboard-bot-$GAMEMODE"
ENV_DIR="/etc/ztt-leaderboard-bot-$GAMEMODE"
SERVICE_USER="botuser"
SERVICE_FILE="/etc/systemd/system/ztt-lb.service"

echo "Updating system and upgrading packages..."
apt update
apt full-upgrade -y

echo "Installing required packages..."
apt install -y \
  postgresql postgresql-contrib postgresql-client postgresql-common \
  python3 python3-pip python3-venv rsync

echo "Creating application directories..."
mkdir -p "$INSTALL_DIR"

echo "Moving application files to $INSTALL_DIR..."
git clone https://github.com/henogiMC/ztt-leaderboard-bot.git
mv ztt-leaderboard-bot/*.json $INSTALL_DIR
mv ztt-leaderboard-bot/*.py $INSTALL_DIR
mv ztt-leaderboard-bot/cogs/ $INSTALL_DIR

echo "Installing systemd service file from repository..."
mv ztt-bot.service "$SERVICE_FILE"

rm -rf ztt-leaderboard-bot/

echo "Creating Python virtual environment..."
cd "$INSTALL_DIR"
python3 -m venv .venv

echo "Installing Python dependencies in venv..."
bash -c "source $INSTALL_DIR/.venv/bin/activate && \
  pip install --upgrade pip && \
  pip install discord.py asyncpg"

echo "Creating environment directory and env file..."
mkdir -p "$ENV_DIR"
tee "$ENV_DIR/env" >/dev/null <<EOF
DATABASE_URL=postgresql://ztt-bot:$DB_PASS@127.0.0.1:5432/ztt
BOT_TOKEN=$TOKEN
EOF

echo "Setting permissions on application directory and env file..."
chown -R "botuser:botuser" "$INSTALL_DIR"
find "$INSTALL_DIR" -type d -exec chmod 755 {} +
find "$INSTALL_DIR" -type f -exec chmod 644 {} +
chmod +x "$INSTALL_DIR/.venv/bin/"*
chmod 600 "$ENV_DIR/env"

echo "Reloading systemd, enabling and starting service..."
systemctl daemon-reload
systemctl enable --now ztt-bot.service

echo "Service status:"
systemctl status ztt-bot.service --no-pager
