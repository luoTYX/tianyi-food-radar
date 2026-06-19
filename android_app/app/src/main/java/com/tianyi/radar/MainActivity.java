package com.tianyi.radar;

import android.Manifest;
import android.app.AlertDialog;
import android.content.Intent;
import android.content.SharedPreferences;
import android.content.pm.PackageManager;
import android.net.Uri;
import android.os.Build;
import android.os.Bundle;
import android.provider.Settings;
import android.view.View;
import android.widget.Button;
import android.widget.EditText;
import android.widget.LinearLayout;
import android.widget.TextView;
import android.widget.ToggleButton;
import androidx.annotation.NonNull;
import androidx.appcompat.app.AppCompatActivity;
import androidx.core.app.ActivityCompat;
import androidx.core.content.ContextCompat;

public class MainActivity extends AppCompatActivity {

    private ToggleButton toggle;
    private Button btnTest, btnSettings;
    private TextView tvStatus, tvLocation, tvLastUpload;
    private SharedPreferences prefs;
    private static final int REQ_PERM = 100;
    private boolean serviceRunning = false;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_main);

        prefs = getSharedPreferences("tianyi_radar", MODE_PRIVATE);

        toggle = findViewById(R.id.toggle_service);
        btnTest = findViewById(R.id.btn_test);
        btnSettings = findViewById(R.id.btn_settings);
        tvStatus = findViewById(R.id.tv_status);
        tvLocation = findViewById(R.id.tv_location);
        tvLastUpload = findViewById(R.id.tv_last_upload);

        // 首次使用没有配置的话，弹出设置
        if (prefs.getString("server", "").isEmpty()) {
            showSettings();
        }

        // 广播
        android.content.IntentFilter filter = new android.content.IntentFilter("com.tianyi.radar.UPDATE_UI");
        android.content.BroadcastReceiver receiver = new android.content.BroadcastReceiver() {
            @Override
            public void onReceive(android.content.Context c, Intent i) {
                String loc = i.getStringExtra("loc");
                String time = i.getStringExtra("time");
                if (loc != null && !loc.isEmpty()) tvLocation.setText("位置: " + loc);
                if (time != null && !time.isEmpty()) {
                    tvLastUpload.setText("上次: " + time);
                }
            }
        };
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
            registerReceiver(receiver, filter, ContextCompat.RECEIVER_NOT_EXPORTED);
        } else {
            registerReceiver(receiver, filter);
        }

        toggle.setOnClickListener(v -> {
            boolean on = toggle.isChecked();
            if (on) {
                if (prefs.getString("server", "").isEmpty()) {
                    showSettings();
                    toggle.setChecked(false);
                    return;
                }
                if (!hasLocationPerm()) {
                    requestPerms();
                    toggle.setChecked(false);
                    return;
                }
                if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q && !hasBgPerm()) {
                    tvStatus.setText("请授权后台定位");
                    requestBgPerm();
                    toggle.setChecked(false);
                    return;
                }
                startSvc();
            } else {
                stopSvc();
            }
        });

        btnTest.setOnClickListener(v -> {
            if (!hasLocationPerm()) { requestPerms(); return; }
            if (prefs.getString("server", "").isEmpty()) { showSettings(); return; }
            startSvc();
        });

        btnSettings.setOnClickListener(v -> showSettings());
    }

    private void showSettings() {
        AlertDialog.Builder b = new AlertDialog.Builder(this);
        b.setTitle("服务器设置");

        LinearLayout ll = new LinearLayout(this);
        ll.setOrientation(LinearLayout.VERTICAL);
        ll.setPadding(50, 24, 50, 16);

        TextView tv1 = new TextView(this);
        tv1.setText("定位上传地址\n部署server.py的服务器URL");
        tv1.setTextSize(12);
        tv1.setTextColor(0xFF666666);
        ll.addView(tv1);
        final EditText etServer = new EditText(this);
        etServer.setHint("http://你的IP/api/location");
        etServer.setText(prefs.getString("server", ""));
        etServer.setSingleLine(true);
        ll.addView(etServer);

        TextView tv2 = new TextView(this);
        tv2.setText("\n共享密钥\n跟server.py里的SECRET保持一致");
        tv2.setTextSize(12);
        tv2.setTextColor(0xFF666666);
        ll.addView(tv2);
        final EditText etSecret = new EditText(this);
        etSecret.setHint("你的密钥");
        etSecret.setText(prefs.getString("secret", "tianyi_food_radar_2024"));
        etSecret.setSingleLine(true);
        ll.addView(etSecret);

        TextView tv3 = new TextView(this);
        tv3.setText("\n上传间隔(分钟)\n建议15-60，越久越省电");
        tv3.setTextSize(12);
        tv3.setTextColor(0xFF666666);
        ll.addView(tv3);
        final EditText etInterval = new EditText(this);
        etInterval.setHint("15");
        etInterval.setText(String.valueOf(prefs.getInt("interval", 15)));
        etInterval.setInputType(android.text.InputType.TYPE_CLASS_NUMBER);
        etInterval.setSingleLine(true);
        ll.addView(etInterval);

        b.setView(ll);
        b.setPositiveButton("保存", (d, w) -> {
            String srv = etServer.getText().toString().trim();
            String sec = etSecret.getText().toString().trim();
            if (sec.isEmpty()) sec = "tianyi_food_radar_2024";
            int iv;
            try { iv = Integer.parseInt(etInterval.getText().toString().trim()); if (iv < 1) iv = 15; }
            catch (Exception e) { iv = 15; }
            prefs.edit().putString("server", srv)
                    .putString("secret", sec)
                    .putInt("interval", iv).apply();
            tvStatus.setText(srv.isEmpty() ? "请配置服务器地址" : "设置已保存~");
        });
        b.setNegativeButton("取消", null);
        b.show();
    }

    private boolean hasLocationPerm() {
        return ContextCompat.checkSelfPermission(this, Manifest.permission.ACCESS_FINE_LOCATION)
                == PackageManager.PERMISSION_GRANTED;
    }

    private boolean hasBgPerm() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
            return ContextCompat.checkSelfPermission(this, Manifest.permission.ACCESS_BACKGROUND_LOCATION)
                    == PackageManager.PERMISSION_GRANTED;
        }
        return true;
    }

    private void requestPerms() {
        String[] perms;
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
            perms = new String[]{Manifest.permission.ACCESS_FINE_LOCATION,
                    Manifest.permission.ACCESS_COARSE_LOCATION, Manifest.permission.POST_NOTIFICATIONS};
        } else {
            perms = new String[]{Manifest.permission.ACCESS_FINE_LOCATION,
                    Manifest.permission.ACCESS_COARSE_LOCATION};
        }
        ActivityCompat.requestPermissions(this, perms, REQ_PERM);
        tvStatus.setText("请授权定位权限");
    }

    private void requestBgPerm() {
        ActivityCompat.requestPermissions(this,
                new String[]{Manifest.permission.ACCESS_BACKGROUND_LOCATION}, 101);
    }

    @Override
    public void onRequestPermissionsResult(int code, @NonNull String[] perms, @NonNull int[] results) {
        super.onRequestPermissionsResult(code, perms, results);
        boolean allOk = true;
        for (int r : results) if (r != PackageManager.PERMISSION_GRANTED) allOk = false;

        if (code == REQ_PERM && allOk) {
            tvStatus.setText("定位OK");
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q && !hasBgPerm()) {
                requestBgPerm();
            } else {
                tvStatus.setText("可以开始了~");
            }
        } else if (code == 101 && allOk) {
            tvStatus.setText("可以开始了~");
        } else if (!allOk) {
            tvStatus.setText("请去设置开启权限");
            Intent i = new Intent(Settings.ACTION_APPLICATION_DETAILS_SETTINGS);
            i.setData(Uri.parse("package:" + getPackageName()));
            startActivity(i);
        }
    }

    private void startSvc() {
        String srv = prefs.getString("server", "");
        if (srv.isEmpty()) { showSettings(); return; }

        Intent intent = new Intent(this, LocationService.class);
        intent.putExtra("server", srv);
        intent.putExtra("secret", prefs.getString("secret", "tianyi_food_radar_2024"));
        intent.putExtra("interval", prefs.getInt("interval", 15));

        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            startForegroundService(intent);
        } else {
            startService(intent);
        }
        serviceRunning = true;
        tvStatus.setText("雷达已启动~");
        btnTest.setVisibility(View.VISIBLE);
    }

    private void stopSvc() {
        stopService(new Intent(this, LocationService.class));
        serviceRunning = false;
        tvStatus.setText("已停止");
        tvLocation.setText("");
        tvLastUpload.setText("");
        btnTest.setVisibility(View.GONE);
    }

    @Override
    protected void onResume() {
        super.onResume();
        if (!hasLocationPerm()) tvStatus.setText("未授权定位");
        else if (serviceRunning) tvStatus.setText("雷达运行中");
    }
}
