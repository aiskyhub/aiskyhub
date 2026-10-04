# 辅助脚本调用

定位本技能 scripts/comic_pipeline.py，使用已发现的 Python。基本输入提取和关卡使用标准库；DOCX 需要 python-docx，PDF 提取需要 pdfplumber，排版/导出及字体覆盖检查需要 Pillow、reportlab、pypdf。先检查已提供的运行时依赖，不为了使用技能升级或改写全局环境。

Windows 命令形式：
```powershell
$comicPython = '实际发现的 Python 绝对路径'
$comicCli = '本技能 scripts/comic_pipeline.py 的绝对路径'
& $comicPython -X utf8 $comicCli status --project '作品目录绝对路径'
```

所有命令均带 `--project`。含空格、中文的路径始终作为单个参数传递，JSON 文件使用 UTF-8。程序输出 JSON；失败返回退出码 2。`check-script` 的 errors 非空同样返回 2。

| 命令 | 其他参数 | 行为 |
|---|---|---|
| init | --source 一个或多个文件 [--title 标题] | 新目录提取输入，创建空剧本与索引 |
| chapter | [--chapter ID] | 读取真实原文单元；长篇一次只读所需章节 |
| resolve-issue | --id 问题ID --evidence 证据 | 记录已经查明的提取问题 |
| confirm-source | --note 证据 [--scope 范围说明] | 确认获取范围；所有提取问题须解决 |
| mark-read | --chapter ID --note 实际阅读笔记 | 记录实际读完的章节 |
| set-script | --file 完整或工作中剧本JSON | 导入稿件，变化使锁失效 |
| check-script | 无 | 结构、引用、覆盖与状态检查，输出 script_hash |
| review | --kind coverage/continuity/comic --file 报告JSON | 记录实际通过且版本一致的全书审查 |
| lock-script | 无 | 三轮齐备且通过，冻结并输出 full-script.md |
| assert-art | 无 | 任何生成/编辑图像前的全书关卡 |
| register-reference | --characters 角色ID… --file 图像 --qa 报告JSON | 校验并复制已看图通过的基准 |
| begin-panel | --panel ID --prompt 实际提示词TXT | 检查关卡，登记尝试；返回号与参考路径 |
| finish-panel | --panel ID --attempt 尝试号 --file 图像 --qa 报告JSON | 校验并复制通过的画格 |
| fail-panel | --panel ID --attempt 尝试号 --reason 原因 | 登记生成/返修失败 |
| compose | [--font 字体路径] | 通过画格 → 图文排版 PNG |
| review-layout | --file 报告JSON | 全部页面实际看图后登记 |
| export | 无 | 导出离线阅读器、PDF、CBZ |
| verify-export | 无 | 验证实际交付内容与顺序 |
| complete | --file 最终报告JSON | 记录真实最终验收 |
| status | 无 | 核验实际进度、阻塞与下一格 |

`init` 不调用模型；`set-script` 不替你编剧；`review` 不代替阅读；`begin-panel` 不自动出图；`compose` 不重绘画面。模型负责这些创作与判断，脚本负责可靠的机械步骤。

生产队列：先跑 status，若下一格未完成则 begin-panel。一旦返回 already_accepted=true 就复用，不重复出图。pending 必须 finish/fail 后才能重试。

页面与交付文件有 input_hash。用 project.json 中最新 layout.input_hash 和 layout.pages[].id 填入对应报告；不要沿用旧报告或猜页数。
