# 项目与数据契约（版本 1）

`project.json` 由 helper 创建和更新，包含 source、script、reviews、script_lock、art、layout、exports、final_review。不要直接更改 source、锁、尝试号或完成记录来放行。编剧时在当前状态目录的 `scripts/` 中写完整 script JSON，通过 set-script 导入；报告保存到 `reports/`。统一项目布局见 [commands.md](commands.md)，原文新版本的内部状态目录见 [recovery.md](recovery.md)。schema_version 不匹配时保留项目并显式迁移。

## Source

files 记录输入绝对路径、格式、编码和 SHA256；chapters 使用顺序 ID（不以原章号为唯一键），保留标题、正文存在性、阅读记录；units 记录 id、chapter_id、kind、text、locator。TXT 用行号，DOCX 用段落/注释位置，PDF 用页与行，EPUB 用 spine/member/段落。

读取 `chapter` 的输出获取真实 unit ID，不猜编号。所有正文 unit 均需映射，章标题本身不用绘制。source_index_hash 覆盖不可变来源索引，阅读笔记不改变它。issues 需要逐项查明；空章可通过注明确实无正文解决，不代表补画该章。

## Script

使用 assets/script-template.json 的结构。以下为必填字段：

| 对象 | 字段与要求 |
|---|---|
| 全书 | outline：全书结构；ending：实际原文收尾 |
| style | genre、look、palette、selection_reason；format=pages/strip；reading_direction=ltr/rtl；可配 width、height、font_size、max_segment_height、font_path；新项目使用 art_direction 记录具体美术规范，references 保存实际参考记录 |
| character | id、name、aliases 数组、importance=major/supporting/minor；narrative 含 goal/motivation/voice/arc；visual 含 face_shape/eyes/brows/nose_mouth/body/posture/hair/age；source_facts、design_notes 数组 |
| source_fact | text 与非空 source_unit_ids；设计注记不能写成原作事实 |
| setting | id、description；可补空间布局、道具、参考路径/指纹与设计注记 |
| event | id、description、非空 source_unit_ids；每个事件必须在画格中出现 |
| scene | id、chapter_id、setting_id；可补时刻、读者/人物知情状态、叙事层级 |
| panel | id、chapter_id、scene_id、source_unit_ids、event_ids、cast、action、shot、space、expression、state_before、state_after、dialogue；可补 visual_plan 对象记录视觉中心、层次与局部色彩等 |
| page | id、chapter_id、按阅读顺序排列的 panel_ids；columns=1/2；可用 rows 指定每行一格或两格，混合整宽和双格行 |
| source_disposition | unit_id、kind=context/repetition/paratext、reason；context 还需真实 panel_ids |

panels 数组就是全书镜头顺序；pages 按此顺序覆盖每格恰好一次，不能遗漏、重复或改变顺序。相同章号的不同卷使用不同内部 chapter_id。

art_direction 的字段及决策方法见 [art-direction.md](art-direction.md)；模板的默认规范需按本作调整。references 的建议记录为 `{work,url,scope,access,observations,adaptation}`，access=viewed/metadata_only/unavailable；仅在实际看过画页时填写具体观察，不要求为了锁定剧本额外上网。已有项目可以沿用原来的 style，补美术规范时通过 set-script 正常重审。

rows 为画格 ID 数组的数组，例如 `[["p1"],["p2","p3"],["p4"]]`；每行一格占满可用宽度，两格平分宽度；展平后必须与 panel_ids 完全一致。rtl 仅改变一行的物理摆放，JSON 保持阅读顺序。省略 rows 时按 columns 自动分行，末行只有一格则使用整宽。

状态按角色 ID 保存对象，例如 `{ "form":"base", "costume":"coat-a", "injuries":[], "items":[], "location":"room-a", "knowledge":[] }`。各 cast 都有 state_before/after。相邻出场的已记录状态发生变化时，在当前格 state_transitions 填 `{character_id,fields,reason,source_unit_ids}`，解释状态间变化；直接呈现的变化仍要在 action/events 中有依据。

dialogue 为 `{kind,speaker,text,anchor?}`。kind 是 speech/thought/caption/sfx；speech/thought 的 speaker 必须在本格 cast 中。anchor 是 0..1 画面坐标，对应图中该说话人的位置；默认排版器使用其水平分量。文字原样保留，脚本自动添加说话人标识不改变对白正文。

ID 使用稳定、短且适合文件名的字母数字/连字符，避免路径符号。角色形式扩展、关系、道具与阶段设定可作为额外字段保存在相应对象；明确它们的来源与生效范围。

## Reports

审查/视觉报告不自动生成 pass。编剧或制作模型实际完成检查后保存 JSON；程序核验完整性与版本。

剧本报告：
```json
{
  "script_hash": "使用 check-script 输出的实际指纹",
  "reviewed_chapter_ids": ["全部有正文的实际章节 ID"],
  "checks": {"该审查类型的每个检查项": true},
  "evidence": "实际对照位置、发现、修订和复查结果",
  "issues": [{"severity":"major", "description":"具体问题", "resolved":true}]
}
```

coverage 检查项：all_source_read/events_preserved/arcs_preserved/ending_preserved。
continuity：causality/timeline/identity/states/knowledge_and_reveals。
comic：drawable_panels/dialogue_and_speakers/reading_order/pacing/text_density。

参考图报告检查项：identity/distinctiveness/angles_and_expressions/source_faithfulness。
画格报告：identity/continuity/composition/drawing_quality/no_unwanted_text。
以上视觉报告共同需要非空 evidence。

页面报告另外需要 `input_hash` 和全部实际 `reviewed_page_ids`；检查项 text_accuracy/reading_order/speaker_assignment/face_visibility。
最终报告需要 `input_hash`；检查项 source_scope/story_complete/visual_consistency/exports_opened。

## Artifacts 与版本

参考图绑定角色设计与画风指纹，保留真实文件 SHA256 和 QA。画格尝试绑定视觉输入（含 visual_plan）、实际提示词、人物参考、尝试号和生成时全书指纹。只更改对白可以复用视觉输入相同的图；参考/状态/动作等改变则不能复用。

layout 保存全部实际页面/分段、画格顺序、字体和 PNG 指纹；exports 保存各格式文件的指纹。final_review 与实际输入一致且文件仍完整时 status 才会给 complete=true。

页面指纹包含排版器版本；更新排版实现后需要重新 compose、实际看页、review-layout 和 export。画格输入不变时复用有效绘图，无需重新生成。

额外场景/道具图片参考写入对应对象的 reference_paths/reference_hashes；改变该对象会使关联绘图失效。发出提示词前核验这些参考文件的实际哈希并记录到提示词。
