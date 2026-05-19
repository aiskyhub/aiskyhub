# aiskyhub

aiskyhub 的个人插件市场入口，维护 Codex 的 marketplace 元数据。这个仓库只负责插件市场清单；具体插件源码放在独立插件仓库中。

## 当前插件

| 插件 | 用途 | 源码 |
|---|---|---|
| `codex-with-cc` | 让 Codex 主线程负责任务拆解、派工、审核的工作流插件。 | `https://github.com/aiskyhub/codex_with_cc` |

## 目录结构

```text
aiskyhub/
├── .agents/
│   └── plugins/
│       └── marketplace.json      # Codex marketplace
├── docs/
│   └── superpowers/
│       ├── plans/
│       └── specs/
└── README.md
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

- Codex marketplace 写在 `.agents/plugins/marketplace.json`。
- 插件源码使用 `source: url` 指向独立仓库，不在本仓库复制插件源码。
- 新增插件时同时补充本 README 的插件表，以及 Codex 的安装说明。
