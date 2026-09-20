# Plugin OAuth scope 规范与回归

版本：修复纳入 v1.3.1；不代表 GPT Desktop 已更新或登录已验收。

## 单一配置来源

`plugins/planly/skills/planly-solver/config/oauth-client.json` 的 `scopes` 是必需业务权限的唯一配置来源，当前严格限定为 `gateway:mcp`。身份、组织和管理权限不因客户端兼容问题自动加入，不修改 Logto 应用授权或 Gateway required scopes。

生成器将该列表写入 **`mcpServers.planly.scopes`**，与 `url`、`oauth` 同级，不写入 `oauth.scopes`：

```json
{
  "mcpServers": {
    "planly": {
      "type": "http",
      "url": "<由 system-endpoint.json 生成>",
      "scopes": ["gateway:mcp"],
      "oauth": {
        "clientId": "<由 oauth-client.json 生成>",
        "callbackUrl": "http://127.0.0.1/callback"
      }
    }
  }
}
```

这是结构说明，不是另一份可安装配置。构建校验仍拒绝缺失、空列表、额外 scope、秘密字段、非 HTTPS 端点或不匹配回调；不引入第二个配置源。

## 实测支持与限制

2026-09-20 使用已有 Codex 0.155.0 二进制、隔离 HOME/CODEX_HOME 和本地模拟 MCP/OAuth 端点进行了 A/B 验证。Protected Resource Metadata 始终声明 `gateway:mcp`，授权服务器发现文档则模拟真实 Logto 的 13 项 scope（不含 `gateway:mcp`）：

| 配置位置 | 授权 URL 中实际 scope |
| --- | --- |
| 未显式配置 | 采用授权服务器的 13 项 scope，遗漏业务权限 |
| `mcpServers.planly.scopes` | 仅 `gateway:mcp` |
| `mcpServers.planly.oauth.scopes` | 未限制，仍采用 13 项 scope |

官方 [插件 MCP/OAuth 说明](https://developers.openai.com/codex/mcp#plugin-provided-mcp-servers) 与 [OIDC scope 行为说明](https://developers.openai.com/zh-Hans/plugins/build/auth#oidc-作用域) 不足以单独证明目标桌面版本接受所有字段；上述服务器级字段以实际原生解析、授权请求测试为证，不用“配置文件可解析”冒充生效。

这证明已测原生运行时具备所需能力，不证明用户的 GPT Desktop 版本相同、已经安装改动或已经登录成功。不支持该字段的宿主必须报告不兼容，不能回退到扩大 Logto 权限、PAT 或第二条用户级 MCP。

## 验证门槛

1. 构建：`.mcp.json` 的服务器级 scopes 与公开源严格一致，检查模式只读，不写用户配置。
2. 回归：同时覆盖最小发现列表、真实 Logto 式宽列表和缺失 `scopes_supported`；通过实际原生 OAuth 方法生成授权 URL，不显式向 login RPC 传入 scopes，以验证字段确实来自 Plugin。
3. 所有成功请求必须同时包含正确 Client ID、resource、回调、S256 和恰好 `gateway:mcp`；宽列表中的 profile、phone、roles、组织等不得进入请求。
4. 测试在用户登录、同意和换码前停止；不创建任务、不写真实 Token、不读取用户凭据缓存。
5. 发布并更新目标桌面客户端后，重新核对脱敏的授权请求，再单独验收登录、换码、只读工具、刷新和撤销。不要记录完整授权 URL、state、nonce、code、Cookie 或 Token。

历史 v1.3.0 的原生测试将授权服务器与 Protected Resource Metadata 的 scopes 都设为 `gateway:mcp`，未覆盖真实发现列表差异；原记录不能作为该场景已通过的证据。
