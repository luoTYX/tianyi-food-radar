# 天依美食雷达 🍜

> 「不知道吃啥……雷达扫一下！」—— 洛天依

手机常驻上传定位 → 群聊里喊一声 → 天依帮你用高德地图找附近好吃的，带评分、人均、距离、导航链接。

---

## 怎么工作的

```
手机(App/Tasker) ──定时POST位置──→ 服务器(Python HTTP)
                                      │
群友：/找吃的 /想吃火锅 ────────────→ AstrBot 插件
                                      │
                                      ├── 拉取最新定位（或群友指定地点）
                                      ├── 调高德 API 搜周边餐厅
                                      └── 天依语气回复，带导航链接
```

---

## 项目结构

```
├── server/server.py           # 位置接收服务 (Python 零依赖)
├── plugin/food_recommend/     # AstrBot 插件
│   ├── main.py
│   ├── metadata.yaml
│   ├── _conf_schema.json
│   └── requirements.txt
├── android_app/               # Android 定位上传 App
│   └── app/src/main/java/com/tianyi/radar/
├── tasker/                    # Tasker 备选方案
└── README.md
```

---

## 一、部署定位服务器

### 环境要求
- Linux 服务器（Ubuntu 20.04+ / CentOS 7+ / Alibaba Cloud Linux 均可）
- Python 3.6+
- 80/443 端口已开放（云服务器需在安全组放行）

### 步骤

**1. 上传 server.py**

```bash
# SSH 登录服务器
ssh your-server

# 创建目录
mkdir -p /home/admin/tianyi_radar
cd /home/admin/tianyi_radar

# 把 server.py 传上去（在你本地执行）
scp server/server.py admin@你的服务器IP:/home/admin/tianyi_radar/
```

**2. 修改密钥（可选）**

编辑 `server.py`，把 `SECRET` 改成你自己的字符串：

```python
SECRET = "你的随机密钥"  # 改成自己的
```

**3. 启动服务**

```bash
cd /home/admin/tianyi_radar
nohup python3 server.py > /tmp/tianyi.log 2>&1 &
```

验证：

```bash
curl http://localhost:8899/api/health
# 返回 {"ok": true, "msg": "天依的美食雷达运行中~"}
```

**4. 配置 nginx 反代**

找到 nginx 站点配置文件（宝塔面板在 `/www/server/panel/vhost/nginx/` 下，手动安装一般在 `/etc/nginx/sites-enabled/`），在 `server` 块里加上：

```nginx
location /api/ {
    proxy_pass http://127.0.0.1:8899/api/;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
}
```

重载 nginx：

```bash
sudo nginx -t          # 测试配置
sudo nginx -s reload   # 重载
```

验证外网可访问：

```bash
curl http://你的服务器IP/api/health
```

**5. 设置开机自启（可选）**

```bash
sudo tee /etc/systemd/system/tianyi-radar.service << 'EOF'
[Unit]
Description=天依美食雷达定位服务
After=network.target

[Service]
Type=simple
User=admin
WorkingDirectory=/home/admin/tianyi_radar
ExecStart=/usr/bin/python3 /home/admin/tianyi_radar/server.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable tianyi-radar
sudo systemctl start tianyi-radar
```

### 接口说明

| 接口 | 方法 | 请求/参数 | 说明 |
|------|------|-----------|------|
| `/api/location` | POST | `{"lat":31.23,"lng":121.47,"accuracy":15,"secret":"xxx"}` | 上传位置 |
| `/api/location/latest?secret=xxx` | GET | `secret` 密钥 | 获取最新位置 |
| `/api/health` | GET | 无 | 健康检查 |

> 服务只存最新一条位置，不保留历史足迹。

---

## 二、安装 AstrBot 插件

### 方式 A：插件市场安装（推荐）

1. AstrBot WebUI → 插件管理 → 插件市场
2. 搜索「天依美食雷达」
3. 点击安装

### 方式 B：Git 克隆

```bash
cd AstrBot/data/plugins
git clone https://github.com/你的用户名/tianyi-food-recommend.git
# 重载插件 或 重启AstrBot
```

### 方式 C：手动放置

把 `plugin/food_recommend/` 下四个文件放到 `AstrBot/data/plugins/tianyi_food_recommend/` 目录：

```bash
mkdir -p AstrBot/data/plugins/tianyi_food_recommend
cp main.py metadata.yaml _conf_schema.json requirements.txt \
   AstrBot/data/plugins/tianyi_food_recommend/
```

然后重启 AstrBot。

### 配置插件

WebUI → 插件管理 → 天依美食雷达 → 设置：

| 配置项 | 说明 | 示例值 |
|--------|------|--------|
| `amap_key` | 高德「Web服务」API Key | `1b92db8e...` |
| `location_server` | 定位服务器地址 | `http://你的服务器IP` |
| `location_secret` | 密钥，和 server.py 一致 | `你的随机密钥` |
| `search_radius` | 搜索半径(米) | `1500` |
| `result_count` | 返回几条结果 | `5` |

> **高德 Key 申请：**
> 1. 打开 https://console.amap.com/dev/key/app
> 2. 创建应用 → 应用名称随便填
> 3. 添加 Key → 服务平台选 **「Web服务」**（不是 Web端 JS API）
> 4. 复制生成的 Key 填到插件配置里

---

## 三、手机端定位上传

### 推荐：天依雷达 App

使用 Android Studio 打开 `android_app/` 目录，`Build → Build APK`，安装到手机。

**首次使用：**
1. 打开 App → 点击底部齿轮「⚙ 设置」
2. 填入你的服务器地址（如 `http://8.130.43.250/api/location`）
3. 填密钥（和 server.py 一致）
4. 调上传间隔（默认15分钟，建议15-60）
5. 保存 → 打开开关 → 授予定位权限（需选「始终允许」）
6. 通知栏出现「天依雷达」即运行中
7. 点击「测试上传」可立刻验证

**App 特性：**
- 零 Google 服务依赖，华为/鸿蒙完美运行
- Android 后台前台服务，不会被杀
- 配置自动保存，重启 App 还在
- GPS + 网络双路定位，室内也能用

**省电技巧：**
- 间隔调到 30-60 分钟
- 可删除 `server.py` 里的 `GPS_PROVIDER` 只用网络定位

### 备选：Tasker

1. 手机上安装 Tasker
2. 导入 `tasker/UploadLocation.tsk.xml`（任务）和 `TimedTrigger.prf.xml`（触发器）
3. 修改 HTTP 请求的 URL 和密钥为你的服务器信息

### 备选：GPSLogger

| 设置 | 值 |
|------|-----|
| 记录到自定义URL | 开启 |
| URL | `http://你的服务器/api/location` |
| HTTP方法 | POST |
| Content-Type | `application/json` |
| 请求体 | `{"lat":%LAT,"lng":%LON,"accuracy":%ACC,"secret":"你的密钥"}` |
| 信任所有SSL证书 | 开启 |

---

## 四、群聊使用

所有命令支持 `/` 前缀，防止误触发：

| 命令 | 效果 |
|------|------|
| `/找吃的` | 用手机定位搜附近美食 |
| `/找吃的 徐家汇` | 搜徐家汇附近美食 |
| `/想吃火锅` | 搜附近火锅 |
| `/想吃奶茶 静安寺` | 搜静安寺附近奶茶 |
| `/我在哪` | 查看定位状态 |

群友不需要装 App，带地点参数就能搜。每条推荐包含：

```
1. 小昆山奥面馆  [中餐厅]  ⭐4.4  287m
   人均¥17  南浦东路283号
   https://uri.amap.com/navigation?to=121.0,31.2,小昆山奥面馆
```

点链接直接跳高德地图导航。

---

## 五、开发

```bash
# 服务端本地调试
cd server && python3 server.py

# 插件放 AstrBot 的 plugins 目录即可热加载

# Android App 编译（需 JDK 21 + Android SDK）
cd android_app
# Windows
set JAVA_HOME=C:\path\to\jdk && gradlew.bat assembleDebug
# macOS/Linux
JAVA_HOME=/path/to/jdk ./gradlew assembleDebug
```

---

## 六、常见问题

**Q: App 打开开关闪退？**
A: 先去设置里填好服务器地址。首次打开会自动弹设置。

**Q: 华为/鸿蒙手机 App 没反应？**
A: 去「设置→应用→天依雷达→权限」→ 位置信息选「始终允许」。华为需要手动开后台定位。

**Q: 上传失败？**
A: 点测试上传看通知栏错误。检查：1) 服务器地址格式是否正确（带 `http://`）2) 密钥是否一致 3) 服务器端口是否放行。

**Q: 群友搜到的都是我的位置？**
A: 加上地点参数就行，比如 `/找吃的 上海虹桥`。群友不需要装 App。

**Q: 高德 API 收费吗？**
A: Web服务 API 每日免费 5000 次调用，个人用绰绰有余。

**Q: 定位不准？**
A: 室内可能偏几百米，室外 GPS 一般 10 米内。App 同时用 GPS + 网络定位提高精度。

---

## 免责声明

1. **隐私**：本系统仅存储最新一条定位数据，不记录历史轨迹。定位数据仅用于美食搜索，不会用于其他用途。
2. **数据准确性**：餐厅信息、评分、价格均来自高德地图开放平台，本站不对其真实性、准确性负责。
3. **食品安全**：推荐的餐厅与本站无关，请自行判断食品卫生安全。
4. **位置权限**：手机端 App 仅在使用期间获取定位，用户可随时关闭开关停止上传。
5. **使用责任**：使用本软件即表示您同意自行承担所有风险，开发者不对因使用本软件产生的任何直接或间接损失负责。

---

## License

MIT © 依一壹1

---

<p align="center">
  <span style="color:#66CCFF"><b>华风夏韵 · 洛水天依</b></span>
</p>
