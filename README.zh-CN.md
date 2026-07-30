# Project Rules Bootstrap

[English](README.md)

Project Rules Bootstrap 是一个面向智能编码 Agent 的 Skill，用于根据现有仓库中的
证据，生成可审阅的 AI 编码规则。它适合需要维护统一规则源的项目负责人、维护者、
项目成员和新加入者，并能为实际使用的编码助手生成精简入口。

这个 Skill 不会把目录结构、缺少某个文件或通用工程经验直接当成项目规则。它先
收集本地证据，将内容区分为事实、惯例、约束候选、未知项和冲突项，再由用户决定
哪些内容可以进入正式规则。

## 安全与确认机制

发现阶段只读。此时 Skill 不执行目标项目代码、测试、构建、钩子或包脚本，不安装
依赖、不拉取远程内容、不读取敏感文件正文，也不会跟随指向项目根目录之外的符号
链接。敏感路径只记录“存在”这一事实。

整个流程有两个相互独立的写入关口：

1. **Gate 1 — 分析文件：** Skill 先展示证据、待确认问题、所选 adapter，以及
   `.ai/rules.analysis.md` 的准确路径，然后停止。只有用户明确同意后，才可写入
   这个分析文件。
2. **Gate 2 — canonical 文件与 adapter：** 候选内容确定后，每项冲突必须已经
   解决，或明确保留并排除在正式规则之外。随后 Skill 会列出准确的 Create、
   Modify、Unchanged、Manual-only 清单，并逐文件给出合并结论，然后再次停止。
   只有用户明确同意后，才可按该计划写入正式文件。

即使用户要求“立即全部生成”，也不能绕过任一关口，不能视为用户已经确认新的强
约束。除非能确认某段内容属于可安全合并的托管区块，否则保留已有文件不变。更新
计划必须把每次写入标为 `create`、`replace-owned` 或 `managed-block`；只有准确
路径、完整且已验证的 prior Manifest/output tree 所证明的所有权和当前 SHA-256
前置条件全部匹配，才能更新已有分析文件、Manifest、canonical 文件或 adapter；
SHA-256 只用于并发检查，不能自行证明所有权。初始化时写入托管区块，还必须由
已验证的新 Manifest 和权威 adapter registry 授权。全部获批输出会先完成同目录
暂存；任何提交步骤失败都会恢复替换项并删除本次新建项。POSIX 所需的 no-follow
标志或句柄相对能力只要缺失一项就会拒绝操作；便携路径会拒绝 `:`，避免 Windows
备用数据流。Gate 2 会持续固定并复核已批准的分析文件，最后才安装 Manifest。
全部计划输出安装后即越过提交点；此后的备份清理失败会保留已提交结果，发出警告
并写入不含正文的清理日志。托管区块更新会保留
UTF-8 BOM、LF/CRLF 换行方式以及 marker 外的全部字节。

完整的停写示例见[初始化示例](docs/examples/init-example.md)和
[更新示例](docs/examples/update-example.md)。

## 作为插件安装

将本仓库作为一个 Codex 插件安装。一个安装包提供两个 Skill，同时让
`assets/`、`references/` 和 `scripts/` 继续作为唯一共享核心：

```text
project-rules-bootstrap/
├── .codex-plugin/plugin.json
├── skills/
│   ├── project-rules-init/SKILL.md
│   └── project-rules-update/SKILL.md
├── assets/
├── references/
└── scripts/
```

`project-rules-init` 负责建立第一版可信规则集；`project-rules-update` 负责维护
已经存在并通过校验的规则基线。安装插件本身不会在目标项目中安装、选择或加载
任何 adapter；adapter 的加载方式以本文后面的 compatibility level 为准。

## 使用方法

项目还没有可信规则集时使用 Init：

```text
请从这个仓库的现有代码模式中初始化可执行的 AI 编码规则，
使用 Codex、Cursor 和 Trae adapter。
```

代码或项目惯例发生变化后使用 Update：

```text
请根据当前 Git 差异和受影响的完整代码链更新现有 AI 编码规则，
保留不属于插件托管的文件，并展示规则语义变化。
```

## 目标项目中的生成结构

准确输出由已确认的证据、适用规则域和所选编码助手共同决定。完整计划可能包含：

```text
<target-project>/
├── .ai/
│   ├── rules.analysis.md
│   ├── rules-manifest.json
│   └── rules/
│       ├── project.md
│       ├── architecture.md
│       ├── coding-style.md
│       ├── frontend.md
│       ├── backend.md
│       ├── api.md
│       ├── database.md
│       ├── testing.md
│       ├── security.md
│       └── restrictions.md
├── AGENTS.md
├── CLAUDE.md
├── .cursor/rules/<rule>.mdc
├── .trae/rules/<rule>.md
├── .codebuddy/rules/<rule>/RULE.mdc
└── RULES.md
```

只生成实际适用的 canonical 规则文件和用户选中的 adapter。`.ai/rules/` 是唯一的
canonical 语义来源；adapter 只负责精简地指向相关规则，不复制或改变规则语义。
每个 canonical `rule-id` marker 必须独占一行，并与其紧随的单条列表正文绑定；
行内 marker 或嵌入标题的 marker 无效。仅折叠确定性的空白后，正文必须与
Manifest `rule.text` 精确一致。标题和正文中的 `MUST`、`NEVER`、`必须`、`禁止`
都会被检测；这些指令只能作为 marker 绑定项出现在明确的“已确认的强约束”
section 中，并且必须有唯一的单规则确认记录、相同 scope 和关联确认 evidence。
`RULES.md` 是所选 WorkBuddy 或 Generic `manual-reference` adapter 的登记入口，
必须由用户导入或显式引用。如果两者同时选中，registry 的 shared-output 契约只
渲染一次该文件，以 WorkBuddy 为具体 owner，并在一个 Manifest adapter 记录中
列出两个 consumer。

## 工具兼容性

兼容性结论原样来自
[`references/adapters.json`](references/adapters.json)，不会根据经验推断。

| Adapter ID | 工具 | Registry 中的准确路径 | Compatibility level |
| --- | --- | --- | --- |
| `codex` | Codex | `AGENTS.md` | `native-auto` |
| `claude-code` | Claude Code | `CLAUDE.md` | `native-auto` |
| `cursor` | Cursor | `.cursor/rules/*.mdc` | `native-auto` |
| `trae` | Trae | `.trae/rules/*.md` | `native-auto` |
| `codebuddy` | CodeBuddy | `.codebuddy/rules/<rule>/RULE.mdc` | `native-auto` |
| `workbuddy` | WorkBuddy | `RULES.md` | `manual-reference` |
| `generic` | Generic | `RULES.md` | `manual-reference` |

使用 WorkBuddy 时，需要导入根目录的 `RULES.md`，或通过 `@` 显式引用它。Generic
工具也必须使用该工具提供的机制显式引用 `RULES.md`。这两项都不是自动加载。未
登记在 registry 中的工具属于 `unverified`：Skill 不虚构路径或加载行为，也不为
其生成 adapter。

Claude Code 生成的 `CLAUDE.md` 使用不带代码 span 的
`@.ai/rules/project.md` 导入 canonical project router。

各 compatibility level 的定义、核验日期和官方来源见
[兼容性说明](docs/compatibility.md)。

## 无 Python 时的回退方式

建议使用 Python 运行内置的确定性扫描器和输出校验器。请在已安装的 Skill 根目录
执行：

```text
python scripts/scan_project.py <project-root>
python scripts/validate_outputs.py <project-root>
```

扫描器限制目录 entry 数、文件数、单文件字节数、内容总字节数、Git 记录与字节数，
并对 subprocess 使用真实超时。每个 inventory 记录都会区分已读取、跳过、截断或
未核验；敏感路径仍只记录存在性。语言或 toolchain 信号会单独报告，不能独自推导
backend 结论。当 `max_depth` 省略 entry（包括 `max_depth=0`）时，扫描器会设置
`limits.depth_truncated`、返回 `complete: false`，并在不读取被省略正文的前提下
记录有界的 `unverified` 路径；路径证据本身也受目录 entry 和内容字节预算限制，
无法容纳的证据仍会计入 `unverified_summary` 的有界原因计数。

如果没有 Python，Skill 会改用只读文件搜索和本地 Git 检查，并保持与扫描器一致
的有界证据结构和排除规则。被中断或无法访问的区域会标记为 `unverified`，且不会
执行目标项目命令。内置校验器无法在无 Python 环境中运行，因此 Skill 会明确报告
这一限制，不会把“未校验”写成“已通过”。

## 测试与贡献

运行仓库单元测试和契约测试：

```text
python -m unittest discover -s tests -v
```

行为场景及其预期断言定义在 `evals/evals.json`；本仓库未内置 behavior-eval
runner。可以使用当前 Agent 环境提供的 Skill 评估流程；如果没有 runner，则逐项
人工检查 prompt 与 expectation，并确认每个写入关口在批准前停止时 fixture 目录
保持不变。

贡献 adapter 或修改文档前，请阅读 [CONTRIBUTING.md](CONTRIBUTING.md)。Adapter
metadata、模板、官方来源、单元测试和行为 eval 必须同步更新，并且不能改变
canonical 规则语义。

## 许可证

本项目采用 [Apache License 2.0](LICENSE)。
