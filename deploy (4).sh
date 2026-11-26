#!/usr/bin/env bash
# One-time Azure setup: resource group, container registry, Linux Web App for Containers.
# Prereqs: Azure CLI logged in (`az login`). Not executed in the authoring sandbox: review first.
set -euo pipefail
: "${AZ_LOCATION:=centralindia}"
: "${AZ_RG:=aurum-rg}"
: "${AZ_ACR:?choose a globally unique registry name, e.g. aurumacr123}"
: "${AZ_APP:?choose a globally unique app name, e.g. aurum-parking-123}"

az group create -n "$AZ_RG" -l "$AZ_LOCATION"
az acr create -g "$AZ_RG" -n "$AZ_ACR" --sku Basic --admin-enabled true
az acr build -r "$AZ_ACR" -t aurum:latest .
az appservice plan create -g "$AZ_RG" -n "$AZ_APP-plan" --is-linux --sku B1
az webapp create -g "$AZ_RG" -p "$AZ_APP-plan" -n "$AZ_APP" \
  --deployment-container-image-name "$AZ_ACR.azurecr.io/aurum:latest"
az webapp config appsettings set -g "$AZ_RG" -n "$AZ_APP" --settings \
  WEBSITES_PORT=8501 MQTT_HOST="${MQTT_HOST:-}" MQTT_PORT="${MQTT_PORT:-8883}" \
  MQTT_USERNAME="${MQTT_USERNAME:-}" MQTT_PASSWORD="${MQTT_PASSWORD:-}" DATABASE_URL="${DATABASE_URL:-}"
echo "Deployed: https://$AZ_APP.azurewebsites.net"
