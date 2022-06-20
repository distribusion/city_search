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

# Start single gunicorn worker
uvicorn city_search.main:app \
	--host 0.0.0.0 \
	--port 5000 \
	--log-level info \
	--access-log \
	--no-use-colors
