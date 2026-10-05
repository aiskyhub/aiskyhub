# aiskyhub

aiskyhub 的个人插件市场入口，维护 Codex 的 marketplace 元数据，以及独立目录中的通用技能。具体插件源码放在独立插件仓库中。

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
├── novel_to_comic_skills/         # 通用小说转完整漫画技能、脚本及测试
├── docs/
│   └── superpowers/
│       ├── plans/
│       └── specs/
└── README.md
```

## 通用技能

| 技能 | 入口 | 用途 |
|---|---|---|
| `novel-to-comic` | [novel_to_comic_skills/SKILL.md](novel_to_comic_skills/SKILL.md) | 先完成通篇剧本与多轮校验，再按原生像素和细节需求紧凑合图、逐格验收、排版和导出完整漫画。 |

调用示例：`$novel-to-comic 将我提供的小说忠实改编为完整漫画。`

美术规范与连载漫画参考方法见 [art-direction.md](novel_to_comic_skills/references/art-direction.md)，支持整宽重点画格与双格行组合、统一线条配色及跨页风格检查。

技能目录包含 `agents/`、`references/`、`scripts/`、`assets/` 和 `tests/`，作品资料及图像保存在各自作品项目中。作品项目顶层统一以《书名》命名，原始小说文本移动至 `source_texts/` 集中归档，切割文本统一存放于 `split_texts/`，顶层 `README.md` 引导 `docs/` 模块化介绍文档；分卷作为书名下的子文件夹进行独立制作管理（如 `<书名>/第1卷/`），每卷为一个独立完整的制作工程。

新版为角色记录身份特征卡、设计层级和形态版本，画格显式绑定参考，新增参考不会替换旧画格。支持过期尝试结算、原稿归档、章节更新和影响查询。固定页漫与按行分段条漫均支持不等宽双格、字体内容指纹、独立文字带及可编辑气泡。数据统一使用 schema_version=4，不提供旧结构转换或旧图重验收接口。

生成批次不设固定格数上限，按必填 canvas_pixels、各格 min_pixels 与归一化格区检查规划容量，可跨成品页面组合。规划尺寸不是工具能力保证；正式输出仍无损分格并逐格验收原生细节，不能放大、降低成品尺寸或删镜头换取更多格数。设定图合并适合的角度、表情和对象，复用已通过参考作角色对照；合格格直接复用，剩余格须重排，适合的失败格可合并返修。每格三次尝试和原有质量门槛保持不变。

人物美感、男女外观和辨识度由主代理实际看图确认。自动化测试中的色块与模拟报告只检查结构和状态；`tests/fixtures` 中的原创短篇用于隔离验收，不作为其他作品的人设。

使用含 Pillow、reportlab、pypdf 等依赖的 Python 运行回归测试：

```text
python -B -m unittest discover -s novel_to_comic_skills/tests -v
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
