package com.tianyi.radar;

import android.Manifest;
import android.app.Notification;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.PendingIntent;
import android.app.Service;
import android.content.Context;
import android.content.Intent;
import android.content.pm.PackageManager;
import android.location.Location;
import android.location.LocationListener;
import android.location.LocationManager;
import android.os.Build;
import android.os.Bundle;
import android.os.Handler;
import android.os.HandlerThread;
import android.os.IBinder;
import android.os.Looper;
import android.util.Log;
import androidx.annotation.Nullable;
import androidx.core.app.NotificationCompat;
import androidx.core.content.ContextCompat;
import java.io.OutputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.text.SimpleDateFormat;
import java.util.Date;
import java.util.Locale;

public class LocationService extends Service {

    private static final String TAG = "TianyiRadar";
    private static final String CHANNEL_ID = "tianyi_radar";
    private static final int NOTIFY_ID = 1;

    private String serverUrl = "";
    private String secret = "";
    private int intervalMin = 15;
    private int failCount = 0;
    private boolean uploading = false;

    private LocationManager locManager;
    private Handler handler;
    private HandlerThread thread;
    private SimpleDateFormat sdf = new SimpleDateFormat("HH:mm:ss", Locale.getDefault());

    private LocationListener listener = new LocationListener() {
        @Override public void onLocationChanged(Location loc) { doUpload(loc); }
        @Override public void onStatusChanged(String p, int s, Bundle b) {}
        @Override public void onProviderEnabled(String p) { notifyStatus("GPS已开启"); }
        @Override public void onProviderDisabled(String p) { notifyStatus("GPS已关闭"); }
    };

    @Override
    public void onCreate() {
        super.onCreate();
        Log.d(TAG, "onCreate");
        createChannel();
        locManager = (LocationManager) getSystemService(LOCATION_SERVICE);
        thread = new HandlerThread("tianyi");
        thread.start();
        handler = new Handler(thread.getLooper());
    }

    @Override
    public int onStartCommand(Intent intent, int flags, int startId) {
        Log.d(TAG, "onStartCommand");

        // 1. 立刻前台化(Android 8+必须5秒内)
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            startForeground(NOTIFY_ID, buildNoti("初始化..."));
        }

        // 2. 读参数
        if (intent != null) {
            String s = intent.getStringExtra("server");
            if (s != null && !s.isEmpty()) serverUrl = s;
            s = intent.getStringExtra("secret");
            if (s != null) secret = s;
            intervalMin = intent.getIntExtra("interval", 15);
        }

        Log.d(TAG, "server=" + serverUrl + " interval=" + intervalMin);

        // 3. 没配地址就不跑
        if (serverUrl.isEmpty()) {
            Log.e(TAG, "未配置服务器");
            notifyStatus("请先设置服务器地址");
            stopSelf();
            return START_NOT_STICKY;
        }

        // 4. 没权限就停
        if (ContextCompat.checkSelfPermission(this, Manifest.permission.ACCESS_FINE_LOCATION)
                != PackageManager.PERMISSION_GRANTED) {
            notifyStatus("缺少定位权限");
            stopSelf();
            return START_NOT_STICKY;
        }

        // 5. 开定位
        startLocating();

        // 6. 先拿缓存位置传一次
        try {
            Location gps = locManager.getLastKnownLocation(LocationManager.GPS_PROVIDER);
            Location net = locManager.getLastKnownLocation(LocationManager.NETWORK_PROVIDER);
            Location best = gps != null ? gps : net;
            if (net != null && (best == null || net.getTime() > best.getTime())) best = net;
            if (best != null) {
                sendUi(best, "缓存位置");
                doUpload(best);
            }
        } catch (Exception e) {
            Log.w(TAG, "缓存位置失败: " + e.getMessage());
        }

        notifyStatus("等待定位...");
        return START_STICKY;
    }

    private void startLocating() {
        long intervalMs = intervalMin * 60L * 1000L;
        float minDist = 50f;

        try {
            if (locManager.isProviderEnabled(LocationManager.GPS_PROVIDER)) {
                locManager.requestLocationUpdates(LocationManager.GPS_PROVIDER,
                        intervalMs, minDist, listener, Looper.getMainLooper());
            }
        } catch (Exception e) {
            Log.w(TAG, "GPS: " + e.getMessage());
        }

        try {
            if (locManager.isProviderEnabled(LocationManager.NETWORK_PROVIDER)) {
                locManager.requestLocationUpdates(LocationManager.NETWORK_PROVIDER,
                        intervalMs, minDist, listener, Looper.getMainLooper());
            }
        } catch (Exception e) {
            Log.w(TAG, "网络定位: " + e.getMessage());
        }
    }

    private void doUpload(Location loc) {
        if (uploading) return;
        uploading = true;

        handler.post(() -> {
            try {
                double lat = loc.getLatitude(), lng = loc.getLongitude();
                float acc = loc.getAccuracy();
                String body = String.format(Locale.US,
                        "{\"lat\":%.6f,\"lng\":%.6f,\"accuracy\":%.1f,\"secret\":\"%s\"}",
                        lat, lng, acc, secret);

                URL url = new URL(serverUrl);
                HttpURLConnection c = (HttpURLConnection) url.openConnection();
                c.setRequestMethod("POST");
                c.setRequestProperty("Content-Type", "application/json");
                c.setDoOutput(true);
                c.setConnectTimeout(10000);
                c.setReadTimeout(10000);
                OutputStream os = c.getOutputStream();
                os.write(body.getBytes("UTF-8"));
                os.flush(); os.close();
                int code = c.getResponseCode();
                c.disconnect();

                String time = sdf.format(new Date());
                if (code == 200) {
                    failCount = 0;
                    notifyStatus("已上传 " + time);
                    sendUi(loc, time);
                } else {
                    failCount++;
                    notifyStatus("上传失败 " + code + " x" + failCount);
                    sendUi(loc, "失败x" + failCount);
                }
            } catch (Exception e) {
                failCount++;
                Log.e(TAG, "上传异常: " + e.getMessage());
                notifyStatus("网络错误 x" + failCount);
                sendUi(null, "错误x" + failCount);
            }
            uploading = false;
        });
    }

    private void sendUi(Location loc, String msg) {
        Intent i = new Intent("com.tianyi.radar.UPDATE_UI");
        if (loc != null) {
            i.putExtra("loc", String.format(Locale.getDefault(), "%.5f, %.5f", loc.getLatitude(), loc.getLongitude()));
        }
        i.putExtra("time", msg);
        sendBroadcast(i);
    }

    private void notifyStatus(String text) {
        NotificationManager nm = (NotificationManager) getSystemService(NOTIFICATION_SERVICE);
        if (nm != null) nm.notify(NOTIFY_ID, buildNoti(text));
    }

    private Notification buildNoti(String text) {
        Intent i = new Intent(this, MainActivity.class);
        PendingIntent pi = PendingIntent.getActivity(this, 0, i,
                PendingIntent.FLAG_UPDATE_CURRENT | PendingIntent.FLAG_IMMUTABLE);
        return new NotificationCompat.Builder(this, CHANNEL_ID)
                .setContentTitle("天依雷达")
                .setContentText(text)
                .setSmallIcon(android.R.drawable.ic_menu_compass)
                .setContentIntent(pi)
                .setOngoing(true)
                .setPriority(NotificationCompat.PRIORITY_LOW)
                .build();
    }

    private void createChannel() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            NotificationChannel ch = new NotificationChannel(
                    CHANNEL_ID, "后台定位", NotificationManager.IMPORTANCE_LOW);
            ch.setShowBadge(false);
            ((NotificationManager) getSystemService(NOTIFICATION_SERVICE)).createNotificationChannel(ch);
        }
    }

    @Override
    public void onDestroy() {
        Log.d(TAG, "onDestroy");
        try { locManager.removeUpdates(listener); } catch (Exception e) {}
        if (thread != null) thread.quitSafely();
        super.onDestroy();
    }

    @Nullable @Override
    public IBinder onBind(Intent intent) { return null; }
}
