#!/data/data/com.termux/files/usr/bin/bash
# GhostTrace auto-restart wrapper
cd ~/ghosttrace
termux-wake-lock
while true; do
    echo "[*] $(date) starting server"
    python web.py
    echo "[!] $(date) died — restart in 5s"
    sleep 5
done
