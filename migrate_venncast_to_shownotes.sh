#!/bin/bash
# migrate_venncast_to_shownotes.sh
# Script to migrate shownotes → shownotes and update all references on a Raspberry Pi 4
# Usage: sudo ./migrate_venncast_to_shownotes.sh

set -e

# 1. Variables
OLD_DIR="/home/scott/shownotes"
NEW_DIR="/home/scott/shownotes"
SERVICE_FILE="/etc/systemd/system/shownotes.service"

# 2. Stop the running service (if exists)
echo "Stopping existing shownotes/shownotes service if running..."
systemctl stop shownotes.service || true
systemctl stop shownotes.service || true

# 3. Move/Rename the project directory
echo "Moving $OLD_DIR to $NEW_DIR..."
mv "$OLD_DIR" "$NEW_DIR"

# 4. Update references in service file and scripts
if [ -f "$SERVICE_FILE" ]; then
    echo "Updating service file paths..."
    sed -i 's/shownotes/shownotes/g' "$SERVICE_FILE"
    systemctl daemon-reload
    echo "Restarting shownotes.service..."
    systemctl restart shownotes.service
else
    echo "Service file $SERVICE_FILE not found. Please update manually if needed."
fi

# 5. Update references in scripts within the new project directory
find "$NEW_DIR" -type f -exec sed -i 's/shownotes/shownotes/g' {} +

# 6. Optionally, update .env or other config files if needed
if [ -f "$NEW_DIR/.env" ]; then
    sed -i 's/shownotes/shownotes/g' "$NEW_DIR/.env"
fi

# 7. Print completion message
echo "Migration complete!"
echo "Please verify the following manually:"
echo "- All systemd services are running (systemctl status shownotes.service)"
echo "- All scripts/configs reference shownotes, not shownotes"
echo "- The web app loads at its expected URL"
