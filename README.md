# AstrBot Bilibili Live Monitor

AstrBot 的 B站直播间开播/下播监控与提醒插件。支持多会话独立订阅、自定义通知模板。

## 📦 依赖要求

- **AstrBot** >= 4.9.2 (需支持 KV Storage)

## 🚀 快速使用

配置好本插件后，直接在聊天中发送指令即可进行订阅管理。

### 获取直播间 ID (`live_id`)
前往 B 站直播间，提取 URL 末尾的数字，例如：
`https://live.bilibili.com/21987615` 的房间号为 `21987615`。

### 直播监控功能

| 指令 | 说明 | 示例 |
| --- | --- | --- |
| `/live_sub <sid> <live_id> [主播名称]` | 将开播通知订阅到指定会话（`sid` 为 QQ 群号或私聊 ID） | `/live_sub 114514 21987615 原神` |
| `/live_unsub <sid> <live_id>` | 取消指定会话的订阅 | `/live_unsub 114514 21987615` |
| `/live_info [live_id]` | 查看所有/指定直播间的当前开播状态及订阅列表 | `/live_info` |

### 快捷切片记录功能 (Quick lamp)

本功能允许用户在观看直播时快捷记录有意思的片段（距离开播的时间点），以便后续回放或制作切片。记录数据会持久化保存，并且相互之间按会话(umo)隔离。

| 指令 | 说明 | 示例 |
| --- | --- | --- |
| `/qlamp_set <live_id>` | 设置当前会话默认记录的直播间ID | `/qlamp_set 21987615` |
| `/qlamp <描述>` | 在当前直播中记录一个切片时间点，并附带描述 | `/qlamp 这一段非常搞笑` |
| `/qlamp_list [页码]` | 查看本会话下的所有切片记录，按直播场次聚合展示，默认第1页 | `/qlamp_list 2` |
| `/qlamp_clear <场次ID或*>` | 删除指定场次(通过qlamp_list获取ID)的切片记录，使用 `*` 将清空本会话所有记录 | `/qlamp_clear 21987615_20240101120000` 或 `/qlamp_clear *` |

> **提示**：插件所有的推送文案及查询提示，均可在 **AstrBot 管理面板** 中通过修改文本模板自由定制。

---

## 🛠️ 开发环境部署

本项目使用 [uv](https://github.com/astral-sh/uv) 作为包管理器。

1. **克隆仓库**
   ```bash
   git clone https://github.com/Nanboom233/astrbot_bilibili_livemonitor.git
   cd astrbot_bilibili_livemonitor
   ```

2. **同步环境与依赖**
   使用 `uv` 自动创建虚拟环境并安装所需依赖：
   ```bash
   uv sync
   ```

3. **激活虚拟环境**
   - **Windows**:
     ```cmd
     .venv\Scripts\activate
     ```
   - **Linux / macOS**:
     ```bash
     source .venv/bin/activate
     ```
