# Project Rules 双 Skill 内容优先改造 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将现有单 Skill 改造成一个插件内的 Init/Update 两个 Skill，并让规则发现从技术栈识别升级为跨语言、完整代码链驱动的项目工作方式提炼。

**Architecture:** 保留现有 `scripts/`、`references/`、`assets/` 作为插件共享核心，新增两个独立 Skill 入口。扫描器只负责安全、分层地选出各模块代表源码及角色线索；Skill 读取这些候选代码并按统一内容契约提炼可执行规则。正常流程只保留一次内容确认，现有安全写入与回滚实现继续复用。

**Tech Stack:** Codex plugin manifest、Markdown Skills、Python 3 标准库、`unittest`、现有规则渲染与安全写入脚本。

## Global Constraints

- 一个安装包只暴露 `project-rules-init` 和 `project-rules-update` 两个 Skill。
- 规则内容优先于架构描述；只识别语言或框架不算完成。
- 稳定重复项目模式默认进入规则，不因通用最佳实践不同而询问。
- 每条正式规则包含适用范围、执行动作、项目锚点和验证方式。
- 正常 Init/Update 只有一次内容确认；冲突、安全风险和不安全覆盖才局部升级严格审计。
- 不读取敏感文件正文，不执行目标项目代码，不安装依赖，不访问仓库外符号链接。
- 保留现有 Manifest、Adapter、原子写入、所有权校验和回滚能力。
- 评估收敛为必要单元测试、一个跨语言 fixture，以及一次忽略既有规则的 `xm_bzhjswyh` 生成对比。

---

### Task 1: 建立一个插件、两个 Skill 的可发现结构

**Files:**
- Create: `.codex-plugin/plugin.json`
- Create: `skills/project-rules-init/SKILL.md`
- Create: `skills/project-rules-update/SKILL.md`
- Delete: `SKILL.md`
- Create: `tests/test_plugin_structure.py`
- Modify: `README.md`
- Modify: `README.zh-CN.md`

**Interfaces:**
- Consumes: 插件根目录现有 `references/`、`assets/`、`scripts/`。
- Produces: 两个插件可发现 Skill；Skill 通过 `../../references/`、`../../assets/`、`../../scripts/` 使用同一共享核心。

- [ ] **Step 1: 写插件结构失败测试**

新增 `tests/test_plugin_structure.py`，断言：

```python
def test_plugin_exposes_exactly_init_and_update_skills():
    plugin = json.loads((ROOT / ".codex-plugin/plugin.json").read_text("utf-8"))
    assert plugin["name"] == "project-rules-bootstrap"
    assert plugin["skills"] == "./skills/"
    skill_names = {
        load_frontmatter(path)["name"]
        for path in (ROOT / "skills").glob("*/SKILL.md")
    }
    assert skill_names == {"project-rules-init", "project-rules-update"}
    assert not (ROOT / "SKILL.md").exists()
```

同时断言 Init 描述只命中首次生成场景，Update 描述只命中已有规则更新场景；两者均引用共享内容契约和共享脚本，不复制 Adapter registry。

- [ ] **Step 2: 运行测试并确认失败**

Run:

```text
D:\minconda\envs\xm-bzhjswyh\python.exe -m unittest tests.test_plugin_structure -v
```

Expected: FAIL，因为插件清单和两个 Skill 尚不存在，根 `SKILL.md` 仍存在。

- [ ] **Step 3: 创建最小插件与双 Skill 入口**

`.codex-plugin/plugin.json` 使用：

```json
{
  "name": "project-rules-bootstrap",
  "version": "2.0.0",
  "description": "Discover and maintain project-specific coding rules for AI coding assistants.",
  "author": {"name": "aigoooowork"},
  "repository": "https://github.com/aigoooowork/project-rules-bootstrap",
  "license": "Apache-2.0",
  "keywords": ["project-rules", "coding-agents", "onboarding"],
  "skills": "./skills/",
  "interface": {
    "displayName": "Project Rules Bootstrap",
    "shortDescription": "Discover and maintain project-specific AI coding rules",
    "longDescription": "Two skills initialize and update actionable project rules from existing code patterns.",
    "developerName": "aigoooowork",
    "category": "Developer Tools",
    "capabilities": ["Interactive", "Write"],
    "defaultPrompt": [
      "Initialize AI coding rules from this repository.",
      "Update the existing AI coding rules after code changes."
    ]
  }
}
```

Init 和 Update 的 `SKILL.md` 先建立职责、触发条件、共享资源入口和互相移交规则；删除根 `SKILL.md`，避免第三个 Skill 被发现。

- [ ] **Step 4: 更新安装与使用文档**

README 明确：

- 安装一次得到两个 Skill；
- Init 用于首次规则发现；
- Update 用于可信基线后的增量维护；
- 共享核心仍位于插件根目录；
- 不再以旧单 Skill 方式安装。

- [ ] **Step 5: 验证插件结构**

Run:

```text
D:\minconda\envs\xm-bzhjswyh\python.exe -m unittest tests.test_plugin_structure -v
```

Expected: PASS。

- [ ] **Step 6: 提交**

```text
git add .codex-plugin skills tests/test_plugin_structure.py README.md README.zh-CN.md
git add -u SKILL.md
git commit -m "feat: split project rules into init and update skills"
```

### Task 2: 让扫描器按模块和源码角色选择跨语言代表文件

**Files:**
- Modify: `scripts/scan_project.py`
- Modify: `tests/test_scan_project.py`
- Create: `tests/fixtures/code-chain-multilang/frontend/package.json`
- Create: `tests/fixtures/code-chain-multilang/frontend/src/views/UserView.vue`
- Create: `tests/fixtures/code-chain-multilang/frontend/src/api/users.ts`
- Create: `tests/fixtures/code-chain-multilang/java/pom.xml`
- Create: `tests/fixtures/code-chain-multilang/java/src/main/java/example/UserController.java`
- Create: `tests/fixtures/code-chain-multilang/java/src/main/java/example/UserService.java`
- Create: `tests/fixtures/code-chain-multilang/java/src/main/java/example/UserRepository.java`
- Create: `tests/fixtures/code-chain-multilang/java/src/test/java/example/UserServiceTest.java`
- Create: `tests/fixtures/code-chain-multilang/go/go.mod`
- Create: `tests/fixtures/code-chain-multilang/go/cmd/server/main.go`
- Create: `tests/fixtures/code-chain-multilang/go/internal/http/user_handler.go`
- Create: `tests/fixtures/code-chain-multilang/go/internal/service/user_service.go`
- Create: `tests/fixtures/code-chain-multilang/go/internal/repository/user_repository.go`
- Create: `tests/fixtures/code-chain-multilang/go/internal/service/user_service_test.go`

**Interfaces:**
- Produces: `rule_discovery.candidates[]`，每项包含 `path`、`module`、`language`、`role_hints` 和 `selection_reason`。
- Preserves: 现有 `files`、`stack_signals`、`modules`、`git`、`limits` 输出键和安全限制。

- [ ] **Step 1: 写跨语言候选选择失败测试**

在 `tests/test_scan_project.py` 增加：

```python
def test_rule_discovery_candidates_cover_modules_roles_and_languages(self):
    result = scan_project(FIXTURES / "code-chain-multilang")
    candidates = result["rule_discovery"]["candidates"]
    assert {"vue", "typescript", "java", "go"} <= {
        item["language"] for item in candidates
    }
    assert {"entry", "interface", "business", "data", "test"} <= {
        role for item in candidates for role in item["role_hints"]
    }
    assert {"frontend", "java", "go"} <= {
        item["module"] for item in candidates
    }
```

再增加预算公平性、安全文件和未知语言回退测试：

- 每个主要模块至少有一个候选；
- `.env*`、密钥、二进制和外部链接不进入候选；
- 内容预算不足时记录未覆盖角色和模块；
- 未识别语言仍可按入口、测试和目录角色成为候选。

- [ ] **Step 2: 运行测试并确认失败**

Run:

```text
D:\minconda\envs\xm-bzhjswyh\python.exe -m unittest tests.test_scan_project -v
```

Expected: 新测试 FAIL，因为当前扫描器只读取固定清单文件且没有 `rule_discovery`。

- [ ] **Step 3: 实现语言、模块和角色识别**

在 `scripts/scan_project.py` 增加：

```python
SOURCE_LANGUAGES = {
    ".py": "python",
    ".js": "javascript",
    ".jsx": "javascript",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".vue": "vue",
    ".java": "java",
    ".go": "go",
    ".kt": "kotlin",
    ".kts": "kotlin",
    ".rs": "rust",
    ".cs": "csharp",
}

MODULE_MANIFESTS = {
    "package.json", "pyproject.toml", "requirements.txt", "Pipfile",
    "pom.xml", "build.gradle", "build.gradle.kts", "go.mod", "Cargo.toml",
}
```

实现：

```python
def select_rule_discovery_candidates(
    root: Path,
    files: List[Path],
    *,
    max_candidates_per_module: int = 12,
) -> Dict[str, object]:
    ...
```

角色提示只基于可观察信号：

- `entry`：main、cmd、manage、application、入口配置；
- `interface`：controller、handler、resource、route、view、page、CLI command；
- `validation`：parser、schema、dto、validator；
- `business`：service、usecase、domain、业务函数目录；
- `data`：repository、dao、mapper、model、sql；
- `shared`：middleware、common、utils、client、config；
- `test`：test、tests、spec、`*_test.go` 等。

候选按模块轮转选择，先覆盖角色再补同类比较文件。输出遗漏模块、遗漏角色和预算原因，不宣称已构建精确调用图。

- [ ] **Step 4: 将代表候选纳入正文读取预算**

`_read_bounded_body()` 不再只检查 `SCANNED_NAMES`，而是接收本次候选集合。依赖清单和代表源码均可在现有总字节预算内读取；输出仍不回显敏感正文。

- [ ] **Step 5: 验证扫描器**

Run:

```text
D:\minconda\envs\xm-bzhjswyh\python.exe -m unittest tests.test_scan_project -v
```

Expected: PASS，现有边界、预算、Git 超时和敏感路径测试不退化。

- [ ] **Step 6: 提交**

```text
git add scripts/scan_project.py tests/test_scan_project.py tests/fixtures/code-chain-multilang
git commit -m "feat: select cross-language rule discovery candidates"
```

### Task 3: 将规则内容契约改为可执行工作配方

**Files:**
- Create: `references/code-chain-discovery.md`
- Modify: `references/rule-classification.md`
- Modify: `references/rule-content-contract.md`
- Modify: `assets/templates/analysis.md`
- Modify: `assets/templates/rules/project.md`
- Modify: `assets/templates/rules/architecture.md`
- Modify: `assets/templates/rules/coding-style.md`
- Modify: `assets/templates/rules/frontend.md`
- Modify: `assets/templates/rules/backend.md`
- Modify: `assets/templates/rules/api.md`
- Modify: `assets/templates/rules/database.md`
- Modify: `assets/templates/rules/testing.md`
- Modify: `assets/templates/rules/security.md`
- Modify: `assets/templates/rules/restrictions.md`
- Modify: `tests/test_iteration_two_contract.py`

**Interfaces:**
- Produces: 共享内容契约，要求正式规则包含 scope、action、anchor、verification。
- Preserves: canonical domain、`rule-id` marker、Manifest 文本绑定和强约束确认记录。

- [ ] **Step 1: 写内容质量失败测试**

在 `tests/test_iteration_two_contract.py` 增加静态契约断言：

```python
def test_content_contract_rejects_stack_only_and_generic_rules():
    contract = read("references/rule-content-contract.md")
    assert "只识别技术栈" in contract
    assert "项目锚点" in contract
    assert "验证方式" in contract
    assert "空泛" in contract

def test_every_domain_template_requires_action_anchor_and_verification():
    for template in RULE_TEMPLATES:
        text = template.read_text("utf-8")
        assert "action" in text.lower() or "执行动作" in text
        assert "anchor" in text.lower() or "项目锚点" in text
        assert "verification" in text.lower() or "验证方式" in text
```

同时断言架构文件只允许保存能指导落点、依赖和影响面的内容，普通重复历史模式无需确认。

- [ ] **Step 2: 运行测试并确认失败**

Run:

```text
D:\minconda\envs\xm-bzhjswyh\python.exe -m unittest tests.test_iteration_two_contract -v
```

Expected: FAIL，因为现有内容契约仍以事实/架构分类和通用领域模板为主。

- [ ] **Step 3: 编写跨语言代码链发现手册**

`references/code-chain-discovery.md` 定义：

- 通用入口到测试链路；
- 多模块分层抽样；
- 同类实现横向比较；
- Python、JS/TS/Vue、Java、Go 和未知语言的证据线索；
- 从链路提取落点、复用、契约、风格、共享影响面和验证规则；
- 不把目录说明或技术栈名称直接当规则。

- [ ] **Step 4: 重写内容契约**

正式规则使用一个 marker 绑定的顶层列表项，允许缩进子项表达：

```markdown
<!-- rule-id: backend.add-business-endpoint -->
- 执行动作：新增同类接口时，在 `backend/app/{module}/res_*.py` 实现 Resource。
  - 适用范围：`backend/app/**`
  - 项目锚点：`backend/app/preparation/res_preparation.py`
  - 验证方式：检查路由仍由对应 `views_resource.py` 注册，并运行相关接口测试。
```

Manifest `rule.text` 继续与完整列表项正文精确绑定，不修改现有安全模型。

- [ ] **Step 5: 更新分析和领域模板**

分析预览改成：

- 代表代码链；
- 稳定项目模式；
- 拟生成的工作配方；
- 真实冲突或风险；
- 未覆盖模块。

模板元数据明确拒绝框架介绍、质量口号和无锚点规则；不适用领域不生成文件。

- [ ] **Step 6: 验证内容契约**

Run:

```text
D:\minconda\envs\xm-bzhjswyh\python.exe -m unittest tests.test_iteration_two_contract -v
```

Expected: PASS。

- [ ] **Step 7: 提交**

```text
git add references assets/templates tests/test_iteration_two_contract.py
git commit -m "feat: require actionable project rule recipes"
```

### Task 4: 实现 Init/Update 的内容优先与自适应确认流程

**Files:**
- Modify: `skills/project-rules-init/SKILL.md`
- Modify: `skills/project-rules-update/SKILL.md`
- Modify: `references/confirmation-policy.md`
- Modify: `references/update-workflow.md`
- Modify: `docs/examples/init-example.md`
- Modify: `docs/examples/update-example.md`
- Modify: `evals/evals.json`
- Modify: `tests/test_plugin_structure.py`
- Modify: `tests/test_iteration_two_contract.py`

**Interfaces:**
- Init consumes `rule_discovery.candidates[]` and produces a single content preview plus exact final write plan.
- Update consumes validated prior Manifest, Git delta and affected-chain candidates; produces a semantic rule delta.

- [ ] **Step 1: 写流程失败测试**

增加断言：

- Init 不询问用户角色；
- 规则语言默认跟随会话语言；
- 稳定重复模式不进入确认问题；
- 正常流程只有一次写入确认；
- Init 发现可信 Manifest 时移交 Update；
- Update 无可信 Manifest 时移交 Init；
- Update 只展示语义变化；
- 严格审计只由冲突、安全/数据风险、新强约束或不安全覆盖触发。

- [ ] **Step 2: 运行测试并确认失败**

Run:

```text
D:\minconda\envs\xm-bzhjswyh\python.exe -m unittest tests.test_plugin_structure tests.test_iteration_two_contract -v
```

Expected: FAIL，因为双 Skill 尚保留旧的角色询问和两道默认写入关口。

- [ ] **Step 3: 完成 Init 工作流**

Init 顺序固定为：

1. 定位根目录并检查可信基线；
2. 扫描模块和代表源码；
3. 读取候选正文并追踪代表代码链；
4. 横向比较稳定模式；
5. 按工作配方内容契约生成预览；
6. 只对风险项提问；
7. 一次确认后调用共享渲染、写入和验证脚本。

普通模式不创建 `.ai/rules.analysis.md`；严格模式需要保留冲突证据时才使用分析文件和对应所有权记录。

- [ ] **Step 4: 完成 Update 工作流**

Update 顺序固定为：

1. 验证既有输出树；
2. 读取 Git delta；
3. 从变化文件向上下游和测试扩展候选；
4. 对照原规则与当前稳定模式；
5. 展示新增、修改、废弃、冲突四类语义变化；
6. 无冲突时一次确认更新；
7. 局部风险只升级相关规则，不重新审计全部文件。

- [ ] **Step 5: 收敛 evals**

保留现有关键安全场景，但将普通初始化和更新期望改成一次内容确认。增加一个内容优先场景，断言输出包含真实落点、模仿锚点、公共能力复用和验证方式；不运行大规模多轮基准。

- [ ] **Step 6: 运行流程契约测试**

Run:

```text
D:\minconda\envs\xm-bzhjswyh\python.exe -m unittest tests.test_plugin_structure tests.test_iteration_two_contract -v
```

Expected: PASS。

- [ ] **Step 7: 提交**

```text
git add skills references docs/examples evals tests/test_plugin_structure.py tests/test_iteration_two_contract.py
git commit -m "feat: make rule discovery content-first and risk-adaptive"
```

### Task 5: 完整回归、插件校验和 xm_bzhjswyh 内容对比

**Files:**
- Modify: `CONTRIBUTING.md`
- Create: `docs/xm-bzhjswyh-content-comparison.md`
- Create: `dist/project-rules-bootstrap-plugin.zip`

**Interfaces:**
- Consumes: 完成后的插件、`D:\workspace\xm_bzhjswyh` 源码和测试；生成阶段明确排除该项目已有 `RULES.md`、`AGENTS.md`、`CLAUDE.md` 和规则文档正文。
- Produces: 一份“仅由代码发现的新规则预览 vs 当前人工规则”的覆盖对比，不修改 `xm_bzhjswyh`。

- [ ] **Step 1: 运行完整单元测试**

Run:

```text
D:\minconda\envs\xm-bzhjswyh\python.exe -m unittest discover -s tests -v
```

Expected: 全部通过；Windows 不允许创建符号链接时只保留现有明确 skip。

- [ ] **Step 2: 校验插件清单和两个 Skill**

使用 plugin-creator 的校验器：

```text
D:\minconda\envs\xm-bzhjswyh\python.exe C:\Users\78179\.codex\skills\.system\plugin-creator\scripts\validate_plugin.py D:\workAI\project-rules-bootstrap
```

并使用 skill-creator 的快速校验分别检查：

```text
D:\minconda\envs\xm-bzhjswyh\python.exe C:\Users\78179\.agents\skills\skill-creator\scripts\quick_validate.py skills/project-rules-init
D:\minconda\envs\xm-bzhjswyh\python.exe C:\Users\78179\.agents\skills\skill-creator\scripts\quick_validate.py skills/project-rules-update
```

Expected: 插件清单有效，两个 Skill 均可发现，无根级第三 Skill。

- [ ] **Step 3: 对 xm_bzhjswyh 做只读盲发现**

扫描时排除以下现有规则正文作为生成证据：

- `RULES.md`
- `AGENTS.md`
- 根和子目录 `CLAUDE.md`
- `docs/` 下规则、模板和架构说明
- `.ai/`、`.cursor/rules/`、`.trae/rules/` 等已有 Adapter

只使用：

- 源代码；
- package/requirements/构建配置；
- 路由和请求层；
- 后端接口、业务、数据访问；
- SQL；
- 测试；
- Git 文件与提交差异元数据。

不执行 `xm_bzhjswyh` 的代码、测试或构建，不写入其目录。

- [ ] **Step 4: 生成内容对比报告**

`docs/xm-bzhjswyh-content-comparison.md` 包含：

- 新版 Init 从代码独立发现的规则；
- 当前人工规则中已覆盖的对应项；
- 新版漏掉但人工规则包含的内容；
- 新版从代码发现但人工规则未明确写出的内容；
- 空泛规则检查；
- 对跨端链路、共享影响面、公共能力复用、数据库口径和验证命令的覆盖结论。

报告不复制敏感配置正文，不把推断写成已确认事实。

- [ ] **Step 5: 构建安装包并核对内容**

从当前提交状态生成 `dist/project-rules-bootstrap-plugin.zip`，检查归档包含：

- `.codex-plugin/plugin.json`
- `skills/project-rules-init/SKILL.md`
- `skills/project-rules-update/SKILL.md`
- 共享 `references/`、`assets/`、`scripts/`

且不包含根 `SKILL.md`、缓存、测试临时文件或本地 IDE 文件。

- [ ] **Step 6: 最终回归**

再次运行：

```text
D:\minconda\envs\xm-bzhjswyh\python.exe -m unittest discover -s tests -v
git diff --check
```

Expected: 测试通过，diff 无空白错误。

- [ ] **Step 7: 提交**

```text
git add CONTRIBUTING.md docs/xm-bzhjswyh-content-comparison.md dist
git commit -m "test: validate content-first project rule discovery"
```
