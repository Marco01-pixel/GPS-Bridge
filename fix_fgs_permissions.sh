#!/bin/bash
MANIFEST="app/src/main/AndroidManifest.xml"

if [ ! -f "$MANIFEST" ]; then
    echo "Error: No se encuentra AndroidManifest.xml"
    exit 1
fi

echo "=== APLICANDO CORRECCIÓN ==="
cp "$MANIFEST" "${MANIFEST}.bak"

# Agregar permiso FOREGROUND_SERVICE_LOCATION si no existe
if ! grep -q "FOREGROUND_SERVICE_LOCATION" "$MANIFEST"; then
    sed -i '/<uses-permission android:name="android.permission.FOREGROUND_SERVICE"/a\    <uses-permission android:name="android.permission.FOREGROUND_SERVICE_LOCATION" \/>' "$MANIFEST"
    echo "✓ Permiso FOREGROUND_SERVICE_LOCATION agregado"
else
    echo "✓ Permiso FOREGROUND_SERVICE_LOCATION ya existe"
fi

# Agregar foregroundServiceType="location" al servicio si no existe
if ! grep -q 'foregroundServiceType="location"' "$MANIFEST"; then
    sed -i 's/<service android:name="\.UberBridgeService"/<service android:name=".UberBridgeService" android:foregroundServiceType="location"/g' "$MANIFEST"
    echo "✓ foregroundServiceType agregado al servicio"
else
    echo "✓ foregroundServiceType ya existe"
fi

echo ""
echo "=== VERIFICANDO CAMBIOS ==="
grep -E "FOREGROUND_SERVICE|UberBridgeService" "$MANIFEST"

echo ""
echo "=== RECONSTRUYENDO APK ==="
./gradlew clean
./gradlew assembleDebug --no-daemon

if [ -f "app/build/outputs/apk/debug/app-debug.apk" ]; then
    echo ""
    echo "✓ BUILD EXITOSO"
    echo "APK: app/build/outputs/apk/debug/app-debug.apk"
    ls -lh app/build/outputs/apk/debug/app-debug.apk
else
    echo ""
    echo "✗ BUILD FALLIDO"
fi
