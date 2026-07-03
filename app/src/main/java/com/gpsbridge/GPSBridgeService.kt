package com.gpsbridge

import android.Manifest
import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.Service
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.location.Location
import android.location.LocationManager
import android.net.wifi.WifiManager
import android.os.Build
import android.os.IBinder
import android.telephony.TelephonyManager
import android.util.Log
import androidx.core.app.ActivityCompat
import androidx.core.app.NotificationCompat
import androidx.localbroadcastmanager.content.LocalBroadcastManager
import com.google.gson.Gson
import java.io.BufferedReader
import java.io.InputStreamReader
import java.io.PrintWriter
import java.net.ServerSocket
import java.net.Socket

class GPSBridgeService : Service() {
    private val TAG = "GPSBridgeService"
    private val PORT = 9877
    private lateinit var serverSocket: ServerSocket
    private var isRunning = false
    private lateinit var gson: Gson
    private lateinit var locationManager: LocationManager
    private lateinit var wifiManager: WifiManager
    private lateinit var telephonyManager: TelephonyManager
    private val NOTIFICATION_ID = 1001

    override fun onCreate() {
        super.onCreate()
        gson = Gson()
        Log.d(TAG, "GPSBridgeService creado")
        
        locationManager = getSystemService(Context.LOCATION_SERVICE) as LocationManager
        wifiManager = applicationContext.getSystemService(Context.WIFI_SERVICE) as WifiManager
        telephonyManager = getSystemService(Context.TELEPHONY_SERVICE) as TelephonyManager
        
        startServer()
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        Log.d(TAG, "onStartCommand llamado")
        startForeground(NOTIFICATION_ID, createNotification())
        
        if (!isRunning) {
            startServer()
        }
        
        return START_STICKY
    }

    private fun createNotification(): Notification {
        val channelId = "uber_bridge_channel"
        val channelName = "GPS Bridge Service"
        
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            val channel = NotificationChannel(
                channelId,
                channelName,
                NotificationManager.IMPORTANCE_LOW
            )
            val manager = getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager
            manager.createNotificationChannel(channel)
        }
        
        return NotificationCompat.Builder(this, channelId)
            .setContentTitle("GPS Bridge")
            .setContentText("Servidor activo en puerto $PORT")
            .setSmallIcon(android.R.drawable.ic_dialog_info)
            .setPriority(NotificationCompat.PRIORITY_LOW)
            .build()
    }

    private fun startServer() {
        if (isRunning) return
        
        isRunning = true
        Thread {
            try {
                serverSocket = ServerSocket(PORT)
                Log.d(TAG, "Servidor iniciado en puerto $PORT")
                broadcastStatus("Servidor iniciado en puerto $PORT")
                
                while (isRunning) {
                    try {
                        val client = serverSocket.accept()
                        Log.d(TAG, "Cliente conectado")
                        handleClient(client)
                    } catch (e: Exception) {
                        if (isRunning) {
                            Log.e(TAG, "Error aceptando cliente: ${e.message}")
                        }
                    }
                }
            } catch (e: Exception) {
                Log.e(TAG, "Error iniciando servidor: ${e.message}")
                isRunning = false
            }
        }.start()
    }

    private fun handleClient(client: Socket) {
        Thread {
            try {
                val input = BufferedReader(InputStreamReader(client.inputStream))
                val output = PrintWriter(client.outputStream, true)
                
                var line: String?
                while (client.isConnected && !client.isClosed) {
                    line = input.readLine()
                    if (line == null) break
                    
                    Log.d(TAG, "Comando recibido: $line")
                    val response = processCommand(line.trim())
                    output.println(response)
                }
            } catch (e: Exception) {
                Log.e(TAG, "Error manejando cliente: ${e.message}")
            } finally {
                try { client.close() } catch (e: Exception) {}
            }
        }.start()
    }

    private fun processCommand(command: String): String {
        return when (command.uppercase()) {
            "GET_GPS" -> getGPSData()
            "GET_BLUETOOTH" -> getBluetoothData()
            "GET_WIFI" -> getWiFiData()
            "GET_CELL" -> getCellData()
            "GET_ALL" -> getAllData()
            "PING" -> "PONG"
            "STATUS" -> """{"status":"ok","port":$PORT}"""
            else -> """{"error":"Comando desconocido: $command"}"""
        }
    }

    private fun getGPSData(): String {
        if (ActivityCompat.checkSelfPermission(
                this,
                Manifest.permission.ACCESS_FINE_LOCATION
            ) != PackageManager.PERMISSION_GRANTED
        ) {
            return """{"error":"Permiso de ubicación no concedido"}"""
        }
        
        try {
            var location = locationManager.getLastKnownLocation(LocationManager.GPS_PROVIDER)
            if (location == null) {
                location = locationManager.getLastKnownLocation(LocationManager.NETWORK_PROVIDER)
            }
            
            if (location != null) {
                return gson.toJson(mapOf(
                    "type" to "GPS",
                    "latitude" to location.latitude,
                    "longitude" to location.longitude,
                    "altitude" to location.altitude,
                    "accuracy" to location.accuracy,
                    "speed" to location.speed,
                    "bearing" to location.bearing,
                    "timestamp" to location.time
                ))
            } else {
                return """{"error":"No se pudo obtener ubicación"}"""
            }
        } catch (e: Exception) {
            return """{"error":"${e.message}"}"""
        }
    }

    private fun getBluetoothData(): String {
        if (ActivityCompat.checkSelfPermission(
                this,
                Manifest.permission.BLUETOOTH_SCAN
            ) != PackageManager.PERMISSION_GRANTED
        ) {
            return """{"error":"Permiso de Bluetooth no concedido"}"""
        }
        
        try {
            val bluetoothAdapter = android.bluetooth.BluetoothAdapter.getDefaultAdapter()
            if (bluetoothAdapter == null || !bluetoothAdapter.isEnabled) {
                return """{"error":"Bluetooth no disponible o desactivado"}"""
            }
            
            val devices = bluetoothAdapter.bondedDevices
            val deviceList = devices.map {
                mapOf(
                    "name" to (it.name ?: "Unknown"),
                    "mac" to it.address,
                    "type" to it.type
                )
            }
            
            return gson.toJson(mapOf(
                "type" to "BLUETOOTH",
                "devices" to deviceList,
                "count" to deviceList.size,
                "enabled" to true
            ))
        } catch (e: Exception) {
            return """{"error":"${e.message}"}"""
        }
    }

    private fun getWiFiData(): String {
        try {
            if (!wifiManager.isWifiEnabled) {
                return """{"error":"WiFi no disponible o desactivado"}"""
            }
            
            val scanResults = wifiManager.scanResults
            val networks = scanResults.map {
                mapOf(
                    "ssid" to (it.SSID ?: ""),
                    "bssid" to (it.BSSID ?: ""),
                    "rssi" to it.level,
                    "frequency_mhz" to it.frequency,
                    "timestamp" to it.timestamp
                )
            }
            
            return gson.toJson(mapOf(
                "type" to "WIFI",
                "networks" to networks,
                "count" to networks.size
            ))
        } catch (e: Exception) {
            return """{"error":"${e.message}"}"""
        }
    }

    private fun getCellData(): String {
        try {
            val cellList = mutableListOf<Map<String, Any>>()
            
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
                val cellInfo = telephonyManager.allCellInfo
                cellInfo.forEach { info ->
                    when (info) {
                        is android.telephony.CellInfoLte -> {
                            val cell = info.cellIdentity
                            val signal = info.cellSignalStrength
                            cellList.add(mapOf(
                                "type" to "lte",
                                "mcc" to (cell.mcc ?: 0),
                                "mnc" to (cell.mnc ?: 0),
                                "ci" to cell.ci,
                                "tac" to cell.tac,
                                "pci" to cell.pci,
                                "rsrp" to (signal?.rsrp ?: 0),
                                "rsrq" to (signal?.rsrq ?: 0),
                                "rssi" to (signal?.dbm ?: 0)
                            ))
                        }
                        is android.telephony.CellInfoGsm -> {
                            val cell = info.cellIdentity
                            val signal = info.cellSignalStrength
                            cellList.add(mapOf(
                                "type" to "gsm",
                                "mcc" to (cell.mcc ?: 0),
                                "mnc" to (cell.mnc ?: 0),
                                "lac" to cell.lac,
                                "cid" to cell.cid,
                                "rssi" to (signal?.dbm ?: 0)
                            ))
                        }
                        is android.telephony.CellInfoWcdma -> {
                            val cell = info.cellIdentity
                            val signal = info.cellSignalStrength
                            cellList.add(mapOf(
                                "type" to "wcdma",
                                "mcc" to (cell.mcc ?: 0),
                                "mnc" to (cell.mnc ?: 0),
                                "lac" to cell.lac,
                                "cid" to cell.cid,
                                "rssi" to (signal?.dbm ?: 0)
                            ))
                        }
                    }
                }
            }
            
            return gson.toJson(mapOf(
                "type" to "CELL",
                "cells" to cellList,
                "count" to cellList.size
            ))
        } catch (e: Exception) {
            return """{"error":"${e.message}"}"""
        }
    }

    private fun getAllData(): String {
        val gps = try { getGPSData() } catch (e: Exception) { """{"error":"GPS error"}""" }
        val bt = try { getBluetoothData() } catch (e: Exception) { """{"error":"BT error"}""" }
        val wifi = try { getWiFiData() } catch (e: Exception) { """{"error":"WiFi error"}""" }
        val cell = try { getCellData() } catch (e: Exception) { """{"error":"Cell error"}""" }
        
        return """{
            "type": "ALL",
            "gps": $gps,
            "bluetooth": $bt,
            "wifi": $wifi,
            "cellular": $cell,
            "timestamp": ${System.currentTimeMillis()}
        }"""
    }

    private fun broadcastStatus(message: String) {
        val intent = Intent("SENSOR_UPDATE")
        intent.putExtra("data", """{"type":"STATUS","message":"$message"}""")
        LocalBroadcastManager.getInstance(this).sendBroadcast(intent)
    }

    override fun onDestroy() {
        isRunning = false
        try {
            serverSocket.close()
        } catch (e: Exception) {}
        super.onDestroy()
    }

    override fun onBind(intent: Intent?): IBinder? = null
}
