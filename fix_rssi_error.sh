#!/bin/bash
set -e
echo "=== DIAGNÓSTICO ==="
echo "Problema: signal?.rssi no existe en CellSignalStrengthWcdma"
echo "Solución: Reemplazar por signal?.dbm"
echo ""
KOTLIN_FILE="app/src/main/java/com/uberbridge/UberBridgeService.kt"
if [ ! -f "$KOTLIN_FILE" ]; then
    echo "ERROR: No se encontró $KOTLIN_FILE"
    exit 1
fi
echo "=== APLICANDO CORRECCIÓN ==="
cp "$KOTLIN_FILE" "${KOTLIN_FILE}.bak"
echo "Backup creado: ${KOTLIN_FILE}.bak"
sed -i 's/signal?.rssi/signal?.dbm/g' "$KOTLIN_FILE"
echo "Corrección aplicada: signal?.rssi -> signal?.dbm"
echo ""
echo "=== VERIFICANDO CAMBIOS ==="
echo "Líneas modificadas:"
grep -n "signal?.dbm" "$KOTLIN_FILE" || echo "No se encontraron coincidencias"
echo ""
echo "=== LIMPIEZA Y RECONSTRUCCIÓN ==="
./gradlew clean
./gradlew build --no-daemon
echo ""
echo "=== RESULTADO ==="
if [ -f "app/build/outputs/apk/debug/app-debug.apk" ]; then
    echo "✓ BUILD EXITOSO"
    echo "APK generado: app/build/outputs/apk/debug/app-debug.apk"
    ls -lh app/build/outputs/apk/debug/app-debug.apk
else
    echo "✗ BUILD FALLIDO"
    echo "Revisa los logs arriba para más detalles"
fi
