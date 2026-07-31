# Project Rules Bootstrap

[English](README.md)

Project Rules Bootstrap 用于从现有仓库的真实代码中生成可执行的 AI 编码规则，
包含两个 Skill：

- `project-rules-init`：建立第一版可信规则；
- `project-rules-update`：代码变化后更新已经通过校验的 v2 规则集。

最终规则不是技术栈简介。Skill 会读取真实代码正文，追踪完整调用链，对比重复
实现，并明确告诉新 AI：改动应该放在哪里、应复用哪个现有实现、会经过哪些边界
和数据流、影响哪些调用方，以及如何使用项目已有命令验证。

## 核心流程

1. 只读扫描仓库，不执行目标项目代码；
2. 为每个主要模块追踪有代表性的完整代码链；
3. 将稳定证据整理为包含 Action、Scope、Project anchor、Verification 的规则；
4. 只对会影响结果的模糊点和冲突渐进式提问；
5. 每条新增或发生语义变化的强约束单独确认；
6. 展示完整规则和准确文件计划，再进行一次最终写入确认；
7. 只写入已授权路径，最后安装精简 Manifest，并校验全部输出。

敏感文件只记录“存在”，不读取内容。路径穿越、敏感输出路径、符号链接、所有权
哈希不一致和覆盖未托管文件都会被拒绝。已有但不属于本插件的助手规则文件保持
不变，并标记为 `manual-only`。已退休的生成文件只能通过精确哈希保护的
`delete-owned` 计划删除。Skill 不生成或保留 `.ai/rules.analysis.md`。

## 生成结构

规则按项目实际关注点分组，不强制生成固定十类文件：

```text
<target-project>/
├── .ai/
│   ├── rules-manifest.json
│   └── rules/
│       ├── index.md
│       ├── <实际规则分组>.md
│       └── <其他实际分组>.md
├── AGENTS.md
├── CLAUDE.md
├── .cursor/rules/project-rules.mdc
├── .trae/rules/project-rules.md
├── .codebuddy/rules/project-rules/RULE.mdc
└── RULES.md
```

`.ai/rules/` 是唯一规则语义来源。`index.md` 只列出实际生成的规则分组；adapter
只负责跳转，不复制或改变规则。

v2 Manifest 仅保存项目/扫描来源、托管文件路径与哈希，以及已明确确认的强约束。
它不保存分析过程、普通规则正文、共享 consumer 元数据或第二份规则账本。

## Adapter

| ID | 工具 | 输出路径 | 支持方式 |
| --- | --- | --- | --- |
| `codex` | Codex | `AGENTS.md` | `native` |
| `claude-code` | Claude Code | `CLAUDE.md` | `native` |
| `cursor` | Cursor | `.cursor/rules/project-rules.mdc` | `native` |
| `trae` | Trae | `.trae/rules/project-rules.md` | `native` |
| `codebuddy` | CodeBuddy | `.codebuddy/rules/project-rules/RULE.mdc` | `native` |
| `workbuddy` | WorkBuddy | `RULES.md` | `manual` |

未登记的工具不生成 adapter。路径依据见[兼容性说明](docs/compatibility.md)。

## 命令

在 Skill 根目录运行扫描器和校验器：

```text
python scripts/scan_project.py <project-root>
python scripts/validate_outputs.py <project-root>
```

运行测试：

```text
python -m unittest discover -s tests -v
```

输出校验包含真实文件锚点、源码中可核验的代码符号、显式多段调用链和命令形式
验证候选的质量门禁；Skill 仍需对照项目配置核验所选命令。固定版本的五技术栈
对比结果见 [benchmark](benchmarks/README.md)。

扫描器对目录、文件数量、内容字节、Git 记录和子进程时间设置了上限。未读取、
截断或无法核验的范围会明确报告，不会把局部结果写成完整结论。

## 许可证

本项目采用 [Apache License 2.0](LICENSE)。
