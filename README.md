# aiskyhub

aiskyhub 的个人插件市场入口，维护 Codex 的 marketplace 元数据。具体插件源码放在独立插件仓库中。

## 当前插件

| 插件 | 用途 | 源码 |
|---|---|---|
| `codex-with-cc` | 让 Codex 主线程负责任务拆解、派工、审核的工作流插件。 | `https://github.com/aiskyhub/codex_with_cc` |
| `novel-to-comic` | 将小说或长篇故事忠实改编为完整漫画的工作流插件。 | `https://github.com/aiskyhub/novel_to_comic` |

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

## 通用技能与插件

所有通用技能与插件均已迁移至独立的开源仓库统一维护：

| 插件 / 技能 | 仓库链接 | 入口示例 | 用途 |
|---|---|---|---|
| `codex-with-cc` | [aiskyhub/codex_with_cc](https://github.com/aiskyhub/codex_with_cc) | `$codex-with-cc` | 让主线程负责规划派工、审核闭环的工作流插件。 |
| `novel-to-comic` | [aiskyhub/novel_to_comic](https://github.com/aiskyhub/novel_to_comic) | `$novel-to-comic 将我提供的小说忠实改编为完整漫画。` | 通用小说转完整漫画技能体系与流水线。 |

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

安装插件：

```text
codex plugin install codex-with-cc@aiskyhub
codex plugin install novel-to-comic@aiskyhub
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
$novel-to-comic
```

## 维护规则

- Codex marketplace 写在 `.agents/plugins/marketplace.json`。
- 插件源码使用 `source: url` 指向独立仓库，不在本仓库复制插件源码。
- 新增插件时同时补充本 README 的插件表，以及 Codex 的安装说明。
