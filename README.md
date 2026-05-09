# aiskyhub

aiskyhub 的个人插件市场入口，同时维护 Codex 和 Claude Code 的 marketplace 元数据。这个仓库只负责插件市场清单；具体插件源码放在独立插件仓库中。

## 当前插件

| 插件 | 用途 | 源码 |
|---|---|---|
| `codex-with-cc` | 让 Codex 主线程负责任务拆解、派工、审核，并把高 token 消耗执行委派给 Claude Code CLI 的工作流插件。 | `https://github.com/xdd666t/codex_with_cc` |

## 目录结构

```text
aiskyhub/
├── .claude-plugin/
│   └── marketplace.json          # Claude Code marketplace
├── .agents/
│   └── plugins/
│       └── marketplace.json      # Codex marketplace
├── docs/
│   └── superpowers/
│       ├── plans/
│       └── specs/
└── README.md
```

## Claude Code

添加 marketplace：

```text
/plugin marketplace add aiskyhub/aiskyhub
```

安装插件：

```text
/plugin install codex-with-cc@aiskyhub
/reload-plugins
```

## Codex

Codex 可以通过 marketplace source 管理插件市场。

添加 marketplace：

```text
codex plugin marketplace add aiskyhub/aiskyhub
```

也可以使用 Git URL、SSH URL 或本地 marketplace 根目录：

```text
codex plugin marketplace add https://github.com/aiskyhub/aiskyhub
codex plugin marketplace add git@github.com:aiskyhub/aiskyhub.git
codex plugin marketplace add /path/to/aiskyhub
```

刷新 Git-backed marketplace：

```text
codex plugin marketplace upgrade aiskyhub
```

移除 marketplace：

```text
codex plugin marketplace remove aiskyhub
```

Codex marketplace 文件位于：

```text
.agents/plugins/marketplace.json
```

安装后常用入口：

```text
$codex-with-cc
```

## 维护规则

- Claude Code marketplace 写在 `.claude-plugin/marketplace.json`。
- Codex marketplace 写在 `.agents/plugins/marketplace.json`。
- 两份 marketplace 的插件列表应保持一致。
- 插件源码使用 `source: url` 指向独立仓库，不在本仓库复制插件源码。
- 新增插件时同时补充本 README 的插件表，以及 Codex / Claude Code 的安装说明。
