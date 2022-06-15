#!/usr/bin/env sh

# Exit on first error
set -e

echo "  ___  ____  ____  _  _      ___  ____    __    ____   ___  _   _ "
echo " / __)(_  _)(_  _)( \/ )___ / __)( ___)  /__\  (  _ \ / __)( )_( )"
echo "( (__  _)(_   )(   \  /(___)\__ \ )__)  /(__)\  )   /( (__  ) _ ( "
echo " \___)(____) (__)  (__)     (___/(____)(__)(__)(_)\_) \___)(_) (_)"

echo "Initialize database"
city-search --verbose db-init

echo "Upgrade database"
city-search --verbose db-upgrade

echo "Service users"
city-search user-list

# Start single gunicorn worker
gunicorn -w 1 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000 --timeout 120 city_search.main:app
