#!/bin/bash
cd /ecobee/
export PATH="/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/root/bin"
refreshT=($(jq -r '.refresh_token' token.json))
curl -X POST "https://api.ecobee.com/token?grant_type=refresh_token&code=$refreshT&client_id=IIvMaBH7flX2YbqnoWj1qxTZ8TnCa4Ls" -o token.json
