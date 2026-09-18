# Planly 独立 MCP 与 MCP Apps 验收

版本：1.3.0。发布包内实现与真实宿主体验分开验收，未验证不算通过。

## 自动化范围

- Manifest 不再引用 App，恰好声明 Planly HTTP MCP；Logo 与 Skill 完整。
- 品牌采用已确认的线条骑士 A 版与 Outfit Bold 700 字标；小图标和两种 Logo 按基线校验 SHA-256、尺寸及 RGBA 通道，随包交付 Outfit 许可。
- `.mcp.json` 与公开源一致且可重复生成；端点和 OAuth 源文件指纹未变。
- 不允许静态凭据、秘密字段、任意端点、非 HTTPS 地址或不支持的回调配置。
- Skill 区分插件与独立安装，不硬编码插件命名空间、不静默切换连接、不自动创建第二条用户级 MCP。
- UI 使用实际展示提示和当前工具目录，选择不创建任务，不拼工具/资源名；无 UI、错误版本、权限变化时安全降级。
- 这些是配置和 Skill 合约检查，不证明模型在每个真实会话中都已执行正确，更不等于图形宿主验收。

## 本轮验证记录（2026-09-18）

| 验证 | 结果与边界 |
| --- | --- |
| Python 配置/包/Skill 合约测试 | 51 项通过；含新版 Logo 基线校验，不访问真实 Gateway |
| 品牌源与插件副本 | 3 张 PNG 及 Outfit 许可与 Gateway 已确认品牌源逐字节一致；品牌源只读测试 15 项通过；不代表客户端缓存已更新 |
| Plugin 与 Skill 结构校验 | 通过；端点/OAuth 源指纹保持不变，生成配置一致 |
| 原生客户端解析、安装和协议 | Codex 0.155.0，隔离 HOME/CODEX_HOME；插件独立 MCP 为 planly，apps 为空 |
| 原生 OAuth 授权请求 | 本地模拟授权服务器；预注册 Client ID、S256、发现的 gateway:mcp scope、resource 和 loopback callback 正确，未走 DCR；在用户同意和换码前停止 |
| 原生 MCP UI 资源传输 | 本地模拟 MCP；UI resourceUri 元数据保留、HTML 与 MIME 读取一致；不是 iframe 渲染验证 |
| 上述原生客户端回归 | 2 项通过；临时工具不替换用户的全局客户端 |
| Gateway 源 Skill 回归 | 54 项 Python 通过，打包及 MCP Apps 相关 JVM 26 项通过；未修改业务服务实现 |

重跑原生客户端隔离测试（必须指定待验证的客户端，不自动安装或升级）：

```bash
PLANLY_CODEX_BIN=/path/to/codex python3 -m unittest discover -s tests -p 'test_codex_plugin_runtime.py' -v
```

未设置环境变量时常规测试跳过这两项。它们仅将临时复制的插件连接到本机假服务，正式 `.mcp.json` 仍为原 HTTPS 端点。桌面 GUI、真实 OAuth 登录与地图数据均未验证。

## 真实目标客户端验收（全部待验证）

| 项目 | 操作及通过条件 | 当前状态 |
| --- | --- | --- |
| 安装与品牌 | 从本版本安装，显示 Planly 名称和图标；无历史远端 App 依赖 | 未验证 |
| 独立连接 | 插件提供一条 Planly MCP；无重复用户级连接或错误账号切换 | 未验证 |
| OAuth 授权请求 | 使用既有公开 client_id、S256、登记回调、正确 resource 与 gateway:mcp scope；不误走 DCR | 未验证 |
| OAuth 完整流程 | 用户登录/同意、换 Token、只读工具调用、刷新与撤销均正常；无凭据泄漏 | 未验证 |
| UI 能力协商 | 宿主 initialize 声明正确的 UI 扩展/MIME，Gateway 返回协商能力 | 未验证 |
| 公共 UI | 真实镜像、积分或任务卡能从 resources/read 获取 HTML 并完成桥接渲染 | 未验证 |
| 版本化结果 | 真实成功任务与生效 ImageVersion 匹配；显示实际地图/Gantt/单工程师列表 | 未验证 |
| 全屏/刷新 | inline 精简、全屏请求及拒绝处理、只读刷新、选择和游标保持 | 未验证 |
| 地图/规划回放 | 真实 CSP、图商 browser key/网络通过，规划回放不伪装实时位置 | 未验证 |
| 降级与隔离 | 无 UI、失效版本、认证/权限失效、多卡隔离及迟到响应正确 | 未验证 |

使用用户有权访问的已有任务，不为验收额外创建求解任务。先确认 Gateway 中该 ImageVersion 的 UI 可用；插件无法修复上游 CSP 未审批或引擎产物缺失。

## 边界

- 插件无 App 依赖不代表 OAuth 不需要用户同意。
- 桌面端/Codex 的 MCP 工具可调用，不代表 CLI、IDE 和桌面 GUI 都具备相同 UI 能力。
- 导入直接声明 MCP 的 GitHub 插件当前为 Desktop only；ChatGPT 网页端接入不在本包验收声明中。
- 不为兼容测试修改 Logto 注册、Gateway 权限或 CSP；遇到不兼容应记录真实错误并停止。
