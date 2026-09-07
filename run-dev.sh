#!/bin/bash
# Start ProMo14 dev server (kills any existing instance first)

cd "$(dirname "$0")"

echo "Killing any existing vite servers..."
pkill -f "vite" 2>/dev/null
pkill -f "node.*vite" 2>/dev/null
sleep 1

echo "Starting dev server..."
npm run dev
