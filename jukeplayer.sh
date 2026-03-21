#!/bin/bash

# Jukebox Service Management Script
# Provides easy commands to manage the jukebox service

case "$1" in
    start)
        echo "🚀 Starting jukebox service..."
        sudo systemctl start jukeplayer
        ;;
    stop)
        echo "🛑 Stopping jukebox service..."
        sudo systemctl stop jukeplayer
        ;;
    restart)
        echo "🔄 Restarting jukebox service..."
        sudo systemctl restart jukeplayer
        ;;
    status)
        echo "📊 Jukebox service status:"
        sudo systemctl status jukeplayer --no-pager -l
        ;;
    logs)
        echo "📜 Jukebox service logs (Ctrl+C to exit):"
        sudo journalctl -u jukeplayer -f
        ;;
    enable)
        echo "✅ Enabling jukebox service at startup..."
        sudo systemctl enable jukeplayer
        ;;
    disable)
        echo "❌ Disabling jukebox service at startup..."
        sudo systemctl disable jukeplayer
        ;;
    reload)
        echo "🔄 Reloading service configuration..."
        sudo systemctl daemon-reload
        sudo systemctl restart jukeplayer
        ;;
    uninstall)
        echo "🗑️  Uninstalling jukebox service..."
        sudo systemctl stop jukeplayer 2>/dev/null || true
        sudo systemctl disable jukeplayer 2>/dev/null || true
        sudo rm -f /etc/systemd/system/jukeplayer.service
        sudo systemctl daemon-reload
        echo "✅ Jukebox service uninstalled"
        ;;
    *)
        echo "🎵 Jukebox Service Manager"
        echo ""
        echo "Usage: $0 {start|stop|restart|status|logs|enable|disable|reload|uninstall}"
        echo ""
        echo "Commands:"
        echo "  start     - Start the jukebox service"
        echo "  stop      - Stop the jukebox service"
        echo "  restart   - Restart the jukebox service"
        echo "  status    - Show service status"
        echo "  logs      - Show live service logs"
        echo "  enable    - Enable service at startup"
        echo "  disable   - Disable service at startup"
        echo "  reload    - Reload service configuration"
        echo "  uninstall - Remove the service completely"
        echo ""
        exit 1
        ;;
esac
