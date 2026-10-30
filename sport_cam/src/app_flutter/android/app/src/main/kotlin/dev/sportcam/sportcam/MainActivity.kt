package dev.sportcam.sportcam

import android.content.Context
import android.net.wifi.WifiManager
import io.flutter.embedding.android.FlutterActivity

class MainActivity : FlutterActivity() {
    // Android drops inbound multicast unless an app holds this lock, so the
    // camera's mDNS answers never reach multicast_dns (lib/discovery.dart).
    // Held only while the app is on screen: it costs battery.
    private var multicastLock: WifiManager.MulticastLock? = null

    override fun onStart() {
        super.onStart()
        val wifi = applicationContext.getSystemService(Context.WIFI_SERVICE) as WifiManager
        multicastLock = wifi.createMulticastLock("sportcam-mdns").apply {
            setReferenceCounted(false)
            acquire()
        }
    }

    override fun onStop() {
        multicastLock?.release()
        multicastLock = null
        super.onStop()
    }
}
