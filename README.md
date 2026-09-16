# Planly Plugin

Planly 的场景求解插件，通过 Planly工作台（Gateway）分析派单、路径规划、排程与资源规划需求，构建参数、创建和跟踪求解任务，并解释公开结果摘要。

| 项目 | 当前值 |
| --- | --- |
| Plugin 标识 | `planly` |
| Skill 标识 | `planly-solver` |
| 展示名称 | Planly 场景求解 |
| Plugin / Skill 版本 | **1.2.1** |

## 安装与使用

```bash
codex plugin marketplace add shanhaibuci/planly-plugin --ref v1.2.1
```

私有仓库需要本机 Git 已获得对应 GitHub 仓库的读取权限。然后在支持 Plugins Directory 的客户端中找到 **Planly 场景求解**并安装，开启新会话后使用：

```text
$planly-solver 帮我分析配送与工程师派单场景
```

旧版 `dfst-planning-solver` 不会被自动卸载或覆盖；迁移后请在宿主中停用旧版，避免同时启用两份同功能 Skill。已有 Gateway MCP 配置与 OAuth 授权不因更名自动重置。

## 接入与安全边界

- Codex 在使用 Skill 时先检查只读工具；确实缺少配置时由 Agent 检查宿主能力并添加缺失配置，按需发起原生 OAuth。用户自行完成登录和授权，不在聊天中发送密码或 Token。
- 系统地址仍以 Skill 的 `config/system-endpoint.json` 为唯一事实源。现有域名、MCP Server 名 `gateway`、tool 名、公开 OAuth Client ID、回调和 scope 均未更改。
- ChatGPT 沿用 `.app.json` 中已有 App ID 和连接键；其服务端仍可能显示旧名称。仓库更名不等于已重新发布 App、通过商店审核或适配所有宿主。
- 不新增直接 MCP 配置来绕过现有 OAuth 注册流程；PAT 仅在用户明确选择兼容模式时使用，OAuth 失败不自动降级。
- 所有任务经 Gateway 创建，创建前必须取得用户确认。插件不包含求解引擎、Gateway 服务端、管理员接口或生产数据。
- 自动化测试不代替真实账号登录、授权及只读 MCP 调用的端到端验收；本次品牌发布没有完成该项验收。

## 1.2.1 变更

- 从原 1.1.3 工作流升级，统一 Planly 品牌、Plugin/Skill 标识和版本。
- 接入用户提供的 Planly Logo，并保留字标字体许可。
- 建立独立 Plugin 仓库、版本标签和隔离验证；求解流程及认证绑定保持不变。

## 本地验证

```bash
python3 -m unittest discover -s tests -p 'test_*.py' -v
```

测试使用临时目录、模拟认证和 HTTP 结果，不连接真实认证服务，不创建求解任务，也不写用户的 Codex 配置。

包采用受支持的 `.codex-plugin/plugin.json` 兼容布局，结构参考 [OpenAI 插件打包文档](https://developers.openai.com/plugins/build/plugins)。独立仓库根的 `.agents/plugins/marketplace.json` 提供安装目录；技术 marketplace 名沿用脚手架默认的 `personal`，展示名为 `Planly Plugins`。

## 品牌与许可

`plugins/planly/assets/` 中的图片原样来自正式 Planly 品牌包。横排字标使用 DM Serif Display，许可证随包位于 `assets/OFL-DMSerifDisplay.txt`；字体许可不意味着 Planly 商标或整套软件采用相同许可。
