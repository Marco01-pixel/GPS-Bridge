#!/bin/bash

echo "======================================================================"
echo "ACTIVADOR COMPLETO DEL SISTEMA GPS SYMBIOSIS"
echo "======================================================================"

# 1. Verificar que termux-api funciona
echo ""
echo "[1/4] Verificando termux-api..."
if ! command -v termux-location &> /dev/null; then
    echo "  ✗ termux-api no instalado"
    echo "  Ejecuta: pkg install termux-api"
    exit 1
fi
echo "  ✓ termux-api disponible"

# 2. Probar GPS manualmente
echo ""
echo "[2/4] Probando GPS (puede tardar 20s en cold start)..."
timeout 20 termux-location -p gps > /tmp/gps_test.json 2>/dev/null
if [ $? -eq 0 ] && [ -s /tmp/gps_test.json ]; then
    echo "  ✓ GPS funcionando"
    cat /tmp/gps_test.json | python3 -c "import sys,json; d=json.load(sys.stdin); print(f'    Lat: {d[\"latitude\"]:.6f}, Lon: {d[\"longitude\"]:.6f}')"
else
    echo "  ⚠ GPS no responde, intentando network..."
    timeout 10 termux-location -p network > /tmp/gps_test.json 2>/dev/null
    if [ $? -eq 0 ] && [ -s /tmp/gps_test.json ]; then
        echo "  ✓ Network location funcionando (fallback)"
    else
        echo "  ✗ Ningún proveedor de ubicación funciona"
        echo "    Verifica permisos de Termux: Ajustes → Apps → Termux → Permisos → Ubicación"
    fi
fi

# 3. Matar procesos anteriores
echo ""
echo "[3/4] Deteniendo procesos anteriores..."
pkill -f "sistema_uber_unificado.py" 2>/dev/null
sleep 1
echo "  ✓ Procesos detenidos"

# 4. Iniciar sistema
echo ""
echo "[4/4] Iniciando sistema GPS Symbiosis..."
echo "  Puerto Flask: 8080"
echo "  Puerto Bridge: 9877 (requiere APK iniciada)"
echo ""
echo "======================================================================"
echo "ACCESO WEB:"
echo "  Mapa Pro: http://localhost:8080/mapa_pro"
echo "  Mining:   http://localhost:8080/mining_demo"
echo "======================================================================"
echo ""
echo "Presiona Ctrl+C para detener"
echo ""

python3 sistema_uber_unificado.py

