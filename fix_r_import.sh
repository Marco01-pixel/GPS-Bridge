#!/bin/bash
set -e

echo "=== CORREGIENDO IMPORT DE R ==="

FILE="app/src/main/java/com/gpsbridge/MainActivity.kt"

if [ ! -f "$FILE" ]; then
    echo "Error: No se encuentra $FILE"
    exit 1
fi

# Verificar si ya existe un import de R
if grep -q "import.*\.R" "$FILE"; then
    echo "Ya existe un import de R, actualizándolo..."
    sed -i 's/import com\.uberbridge\.R/import com.gpsbridge.R/g' "$FILE"
else
    echo "Agregando import de R..."
    # Agregar después del package declaration
    sed -i '/^package com\.gpsbridge/a\import com.gpsbridge.R' "$FILE"
fi

echo "✓ Import de R corregido"
echo ""
echo "=== RECONSTRUYENDO ==="
./gradlew clean
./gradlew assembleDebug --no-daemon

if [ -f "app/build/outputs/apk/debug/app-debug.apk" ]; then
    echo ""
    echo "✓ BUILD EXITOSO"
    cp app/build/outputs/apk/debug/app-debug.apk ~/storage/downloads/
    echo "✓ APK copiada a ~/storage/downloads/"
    echo ""
    echo "Para instalar:"
    echo "  termux-open ~/storage/downloads/app-debug.apk"
else
    echo ""
    echo "✗ BUILD FALLIDO"
fi
