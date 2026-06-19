# 天依美食雷达 🍜

群里说声饿了，天依帮你找附近好吃的。

## 怎么用

群里发 `/找吃的` 或者自然点说「好饿啊」「附近有啥好吃的」，天依会自动调高德地图搜附近的店，带上评分、人均、距离，还能点链接直接导航过去。

支持搜特定品类：`/想吃火锅`、`/想吃奶茶`。带地点也行：`/找吃的 徐家汇`。

## 项目结构

```
根目录          → 插件文件（给AstrBot插件市场用的）
server/       → 定位接收服务（Python，放服务器上跑）
android_app/  → 安卓定位App源码
tasker/       → Tasker备用方案
```

## 安装

### 1. 插件

AstrBot插件市场搜「天依美食雷达」安装。或者WebUI里填这个地址：

```
https://github.com/luoTYX/tianyi-food-radar
```

装完后去插件设置里填**高德Web服务API Key**（https://console.amap.com 免费申请），和**机主sid**（你自己的AstrBot用户ID，用来保护定位隐私）。

### 2. 服务端

服务器上一行搞定：

```bash
curl -fsSL https://raw.githubusercontent.com/luoTYX/tianyi-food-radar/main/server/install.sh | bash
```

这会把定位接收服务下载到 `~/tianyi_radar/` 并后台启动，监听8899端口。然后用nginx反代一下 `/api/` 路径就行——不用的话也直接 `http://你的IP:8899/api/` 访问。

### 3. 安卓App

去 [Releases](https://github.com/luoTYX/tianyi-food-radar/releases) 下载APK装手机上。打开后点设置填服务器地址和密钥，打开开关就自动上传定位了。默认15分钟一次，设置里能调。

也支持Tasker：tasker/ 里有配好的xml文件。

---

## 配置项

插件设置里能改这些：

| 配置 | 干啥的 | 默认 |
|------|--------|------|
| amap_key | 高德API密钥 | 必填 |
| location_server | 定位服务器地址 | http://localhost:8899 |
| owner_id | 机主sid，填了只有你能免地点搜 | 空 |
| search_radius | 搜多大范围(米) | 1500 |
| result_count | 一次推荐几家 | 5 |

---

## 隐私

- 服务器只存最新一条定位，不留历史
- 别人不带地点搜会被拦住，不会泄露你的位置
- 高德API不存用户数据

## License

MIT © 依一壹1

---

<p align="center"><span style="color:#66CCFF"><b>华风夏韵 · 洛水天依</b></span></p>
