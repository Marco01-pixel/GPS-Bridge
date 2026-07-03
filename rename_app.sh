#!/bin/bash
set -e

echo "=== CAMBIANDO NOMBRE DE UBER BRIDGE A GPS BRIDGE ==="
echo ""

# 1. Cambiar nombre visible en strings.xml
echo "1. Cambiando nombre en strings.xml..."
sed -i 's/Uber Bridge/GPS Bridge/g' app/src/main/res/values/strings.xml
sed -i 's/UberBridge/GPSBridge/g' app/src/main/res/values/strings.xml
echo "✓ Nombre visible actualizado"

# 2. Cambiar package name en build.gradle
echo "2. Cambiando namespace en build.gradle..."
sed -i 's/namespace "com.uberbridge"/namespace "com.gpsbridge"/g' app/build.gradle
sed -i 's/applicationId "com.uberbridge"/applicationId "com.gpsbridge"/g' app/build.gradle
echo "✓ Namespace actualizado"

# 3. Cambiar package en AndroidManifest.xml
echo "3. Cambiando package en AndroidManifest.xml..."
sed -i 's/package="com.uberbridge"/package="com.gpsbridge"/g' app/src/main/AndroidManifest.xml
echo "✓ Package actualizado"

# 4. Renombrar carpeta de código fuente
echo "4. Renombrando carpeta de código fuente..."
if [ -d "app/src/main/java/com/uberbridge" ]; then
    mkdir -p app/src/main/java/com/gpsbridge
    mv app/src/main/java/com/uberbridge/* app/src/main/java/com/gpsbridge/
    rmdir app/src/main/java/com/uberbridge
    echo "✓ Carpeta renombrada: com/uberbridge -> com/gpsbridge"
else
    echo "⚠ La carpeta com/uberbridge no existe (puede que ya esté renombrada)"
fi

# 5. Actualizar referencias en archivos Kotlin
echo "5. Actualizando referencias en código Kotlin..."
find app/src/main/java/com/gpsbridge/ -name "*.kt" -exec sed -i 's/com\.uberbridge/com.gpsbridge/g' {} +
find app/src/main/java/com/gpsbridge/ -name "*.kt" -exec sed -i 's/UberBridgeService/GPSBridgeService/g' {} +
find app/src/main/java/com/gpsbridge/ -name "*.kt" -exec sed -i 's/Uber Bridge/GPS Bridge/g' {} +
echo "✓ Referencias actualizadas"

# 6. Renombrar archivo del servicio
echo "6. Renombrando archivo del servicio..."
if [ -f "app/src/main/java/com/gpsbridge/UberBridgeService.kt" ]; then
    mv app/src/main/java/com/gpsbridge/UberBridgeService.kt app/src/main/java/com/gpsbridge/GPSBridgeService.kt
    echo "✓ Archivo renombrado: UberBridgeService.kt -> GPSBridgeService.kt"
else
    echo "⚠ El archivo UberBridgeService.kt no existe (puede que ya esté renombrado)"
fi

# 7. Actualizar referencia al servicio en AndroidManifest.xml
echo "7. Actualizando referencia al servicio en AndroidManifest.xml..."
sed -i 's/\.UberBridgeService/.GPSBridgeService/g' app/src/main/AndroidManifest.xml
echo "✓ Referencia al servicio actualizada"

# 8. Actualizar MainActivity si existe
echo "8. Actualizando MainActivity..."
if [ -f "app/src/main/java/com/gpsbridge/MainActivity.kt" ]; then
    sed -i 's/UberBridgeService/GPSBridgeService/g' app/src/main/java/com/gpsbridge/MainActivity.kt
    echo "✓ MainActivity actualizada"
fi

echo ""
echo "=== LIMPIEZA Y RECONSTRUCCIÓN ==="
./gradlew clean
./gradlew assembleDebug --no-daemon

echo ""
echo "=== RESULTADO ==="
if [ -f "app/build/outputs/apk/debug/app-debug.apk" ]; then
    echo "✓ BUILD EXITOSO"
    echo "APK generado: app/build/outputs/apk/debug/app-debug.apk"
    ls -lh app/build/outputs/apk/debug/app-debug.apk
    
    # Copiar a descargas
    cp app/build/outputs/apk/debug/app-debug.apk ~/storage/downloads/
    echo "✓ APK copiada a ~/storage/downloads/"
    echo ""
    echo "Para instalar:"
    echo "  termux-open ~/storage/downloads/app-debug.apk"
else
    echo "✗ BUILD FALLIDO"
    echo "Revisa los errores arriba"
fi
