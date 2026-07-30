# `xm_bzhjswyh` 内容优先规则对比

## 对比方法

下面的生成草案是在读取项目现有的 `RULES.md`、`AGENTS.md`、`CLAUDE.md`
或其他文档之前确定的。这些文件没有作为规则发现的证据。草案只依据当前源码、
包配置、导入关系、调用方和测试生成。敏感环境文件仅记录是否存在，不读取正文。

这次对比检查的是内容质量，不是为了打分。核心问题是：一个新 AI 能否依据生成的
规则完成修改，并让代码看起来像这个项目原本的写法。

## 基于代码盲生成的规则草案

### 项目与变更链规则

1. **跨前后端追踪业务变更**
   - **操作：** 修改前，先定位前端页面或共享流程组件、它在
     `frontend/src/api/business.js` 中调用的函数、对应的 Flask Resource
     `backend/app/<domain>/res_<domain>.py`、领域 service、
     `repository_ops.py` 持久化调用以及最近的测试。修改所有受影响环节，
     不要仅根据页面推测保存链路。
   - **范围：** 筹建、换届、调整和评估流程。
   - **项目锚点：** 筹建草稿的调用链为
     `PreparationCreateView.vue` → `savePreparationDraft` →
     `PreparationDraft.post` → `yw_preparation.service.save_application_draft`
     → `repository_ops.save_prep_application`。
   - **验证：** 运行最近的前端 `.test.mjs`、对应的后端 pytest 模块；
     修改 Vue 代码时还要执行前端构建。

2. **把共享流程代码修改视为多业务变更**
   - **操作：** 修改 `BusinessListPage.vue`、`ApplicationCreatePage.vue`、
     `NodeProcessView.vue`、共享详情辅助函数、附件组件或
     `src/config/node-process.js` 时，列出筹建、换届、调整和评估的全部调用方，
     并补充“应同步变化”和“不应受影响”两类检查。
   - **范围：** 共享前端页面、字段注册表、辅助函数和流程组件。
   - **项目锚点：** 四个业务模块都使用公共列表、创建、详情和节点办理能力；
     聚焦测试也会读取或导入这些共享源码。
   - **验证：** 运行所有导入或静态读取被修改共享文件的聚焦测试，然后在
     `frontend` 下执行 `npm run build`。

### 前端规则

3. **通过现有公共页面契约扩展业务功能**
   - **操作：** 业务页面保持轻量，只负责业务默认值、载荷整形、业务校验和成功后的
     路由跳转；复用 `ApplicationCreatePage.vue`、`BusinessListPage.vue`、
     `NodeProcessView.vue` 和详情组件，不要复制它们的布局或流程。
   - **范围：** 四类业务新增或修改的 Vue 页面。
   - **项目锚点：** `PreparationCreateView.vue`、`ReelectionCreateView.vue`
     和 `AssessmentReportCreateView.vue` 都配置并使用
     `ApplicationCreatePage.vue`；各业务列表页则封装 `BusinessListPage.vue`。
   - **验证：** 运行对应的业务辅助函数测试，并构建前端。

4. **把传输和响应结构处理放在 API 层**
   - **操作：** 在 `frontend/src/api/business.js` 中增加接口包装函数，并使用共享
     `http` 实例。复用现有 token、固定参数、签名、登录失效和网络错误处理。
     使用已有 `ensure*` 辅助函数校验预期的 `code/data` 结构；页面只处理 UI
     状态和用户提示。
   - **范围：** 前端调用项目后端的全部请求。
   - **项目锚点：** `business.js` 始终通过 `http` 发起请求，并统一处理对象、
     数组和 Blob 响应；`http.js` 负责拦截器和签名。
   - **验证：** 运行 HTTP 签名测试、最近的 API 或静态测试，并构建前端。

5. **前端展示字段不得进入后端载荷**
   - **操作：** 使用现有 `frontendOnly` 标记或明确的前端字段键列表标识纯展示、
     本地编辑字段；为渲染初始化这些字段，并在构造保存或提交载荷时删除它们。
     不要为了保存页面本地展示状态而新增后端字段。
   - **范围：** 节点办理字段、创建表单、结果或审核展示以及详情区域。
   - **项目锚点：** `src/config/node-process.js` 声明 `frontendOnly`；
     `NodeProcessView.vue` 会过滤这些字段；筹建创建页在构造载荷前使用
     `FRONTEND_ONLY_FIELD_KEYS`。
   - **验证：** 运行对应的 `*-frontend-fields.test.mjs` 或
     `*-frontend-only.test.mjs` 聚焦测试，并检查最终载荷构造函数。

6. **从大型 Vue 组件中提取可测试行为**
   - **操作：** 将可复用的归一化、状态流转、可见性判断、载荷构造和校验逻辑放在
     相邻的 `.mjs` 辅助模块中；Vue 组件导入这些辅助函数，并使用 Node 直接测试。
     只有无法脱离浏览器导入的组件接线关系才使用读取源码的静态测试。
   - **范围：** 大型公共 Vue 组件和业务流程。
   - **项目锚点：** 节点办理、业务详情、评估、筹建和换届逻辑都拆分到了相邻的
     `.mjs` 模块，并在 `frontend/tests` 下提供聚焦测试。
   - **验证：** 在 `frontend` 下运行
     `node tests/<matching-test>.test.mjs`；修改组件接线时再执行构建。

### 后端与 API 规则

7. **通过领域注册链新增 Flask 接口**
   - **操作：** 在 `backend/app/<domain>/parsers.py` 中定义请求解析；Resource
     方法保持为薄适配层，只负责取得载荷、用户上下文和连接并调用领域 service；
     在 `views_resource.py` 中注册资源，同时保留 `__init__.py` 中现有的领域
     Blueprint 前缀。
   - **范围：** 新增或修改的 Flask REST 接口。
   - **项目锚点：** 筹建、换届、调整和评估都重复使用
     `Blueprint` → `RES_LST` → `Resource` → service 模式。
   - **验证：** 以测试模式导入应用，检查路由注册，并运行对应接口的 service
     或 Resource 测试。

8. **业务决策放在 service，SQL 映射放在 repository**
   - **操作：** 在 `backend/yw_<domain>/service.py` 中实现校验、流程分支、
     新旧载荷归一化和业务编排；SQL、表名、数据库行到 API 的映射以及插入或更新
     机制放在 `repository_ops.py`。沿调用链传递现有连接和用户上下文，
     不要另开一条数据库访问路径。
   - **范围：** 后端领域行为和持久化。
   - **项目锚点：** 筹建和换届 service 调用各自的 `repository_ops`；
     Resource 类取得 `get_conn()` 后委托给 service。
   - **验证：** 通过 monkeypatch repository 函数单测 service 行为；
     SQL 和映射使用捕获到的辅助函数调用单独测试。

9. **复用项目数据库辅助函数，并在 repository 边界完成映射**
   - **操作：** 使用现有 `sql_v2_*` 辅助函数构造参数，使用配置中的 schema
     和表名；同类查询已有 `is_deleted = 0` 过滤时继续保持；在 repository 内
     将数据库 `snake_case` 行转换为 API `camelCase` 字典。局部保存时，
     使用本地合并辅助函数保留载荷中未提供的已存字段，不要用空默认值覆盖。
   - **范围：** 面向 GBase 的 repository 查询和局部更新。
   - **项目锚点：** `yw_preparation/repository_ops.py` 使用
     `sql_v2_build_sql_key`、`sql_v2_build_sql_in_params`、配置化表名常量、
     显式行映射和 `_payload_value`。
   - **验证：** 在 repository 测试中断言 SQL 片段和绑定参数映射；
     增加局部更新回归，证明未修改字段保持不变。

10. **通过现有执行器处理流程动作**
    - **操作：** 对提交、通过、驳回、退回和完成动作，使用
      `StateMachineExecutor` 调用现有领域 service，并同步修改配置的流转路径
      和受影响的副作用。不要在 Resource 或前端页面中重复修改状态。
    - **范围：** 业务单流程流转。
    - **项目锚点：** 筹建 Resource 创建 `StateMachineExecutor`，
      领域 service 负责编排 repository 写入和流程执行。
    - **验证：** 增加 service 测试，覆盖允许流转、拒绝流转、持久化副作用和
      返回状态。

### 启动与测试规则

11. **保留后端启动链**
    - **操作：** 从 `backend/flask_run.py` 或既有 manage 入口启动，
      确保在导入应用前完成环境初始化。新增领域 Blueprint 时，通过
      `app.create_app()` 现有的 Blueprint 列表注册，并保持中间件、错误处理器和
      运行时服务的初始化顺序。
    - **范围：** 后端启动、新领域模块、中间件和部署入口。
    - **项目锚点：** `flask_run.py` 在导入 `manage.app` 前调用 `set_env()`；
      `app/__init__.py` 依次创建配置、运行时服务、Blueprint、中间件和错误处理器。
    - **验证：** 不绕过环境初始化，以测试模式导入或创建应用，并检查 URL Map。

12. **遵循项目的聚焦回归风格**
    - **操作：** 在行为附近增加最小回归：后端 pytest 通过 monkeypatch
      service/repository 边界，断言业务结果或 SQL；前端 Node 测试导入 `.mjs`
      辅助函数，或静态检查 Vue 接线。不要把 Vue 构建通过当作行为或视觉验证。
    - **范围：** 所有代码修改。
    - **项目锚点：** `backend/tests/test_preparation_member_profile.py`
      隔离 repository/service 协作者；`frontend/tests` 包含聚焦的辅助函数和
      接线回归测试。
    - **验证：** 先运行新增的精确回归，再运行相关邻近测试；适用时执行前端构建。

## 盲生成草案的边界

- 第一轮扫描仅记录敏感路径是否存在，但固定的模块采样更偏向按字母排序靠前的包
  占位文件和校验文件。这个发现推动了扫描器改进：现在会忽略本地 worktree 和
  工具缓存，识别 `.mjs/.cjs` 测试，跳过 `__init__.py`，并优先选择有效的
  service、repository、路由或 Resource、HTTP 客户端和测试锚点。即使如此，
  仍需继续跟踪导入关系和调用方，因为有界候选列表并不等于完整调用图。
- 仅凭代码无法确定所有运维策略、强制命令、数据库兼容例外或有意设置的严格禁令。
  不应仅为了让规则看起来完整而编造这些内容。

## 与当前人工规则的对比

人工规则是在上面的盲生成部分确定之后才读取的。

| 对比领域 | 盲生成内容 | 当前人工规则 | 判断 |
| --- | --- | --- | --- |
| 端到端变更链 | 给出了具体的 Vue → API 包装 → Resource → service → repository → 测试配方。 | 调用链分散存在于 `RULES.md` 和 `backend/CLAUDE.md` 中，主要以边界和导航形式描述。 | 生成版本更适合直接指导编码任务。 |
| 前端共享代码影响面 | 要求枚举调用方，并检查应同步变化和不应受影响的场景，同时提供公共组件锚点。 | `RULES.md` 明确定义了共享改动影响规则。 | 高度一致；生成版本补充了当前源码锚点。 |
| 前端实现风格 | 识别出轻量业务页面、公共页面复用、`.mjs` 抽取、API 归一化和 `frontendOnly` 载荷排除。 | 根规则规定 Vue、Element、Axios 和门户行为；`CLAUDE.md` 记录了多个纯前端演示流程。 | 生成内容恢复了仅列技术栈无法体现的日常编码方式；人工规则在门户部署事实方面更丰富。 |
| Flask 接口扩展 | 给出了 parser → 注册 → 薄 Resource → service 的操作指引。 | 人工规则和后端导航定义了相同边界，并增加模板一致性策略。 | 高度一致。该生成规则基于四个重复业务域，不是通用 Flask 偏好。 |
| 领域持久化 | 当前 service 函数负责业务编排，领域 repository 负责 SQL 和映射。 | `backend/CLAUDE.md` 描述 Resource → `yw_*` → workflow/query/repository；`RULES.md` 警告不要强行套用通用 Service/Repository 重构。 | 只要表述为观察到的当前调用链，两者就是兼容的。生成规则必须描述现有函数，不能把它提升为框架级架构命令。 |
| 数据库行为 | 识别出配置化表名常量、参数辅助函数、软删除过滤、行映射和局部更新保留。 | 人工规则进一步规定 GBase 8s 版本、Oracle 模式、命名参数禁令、循环/分页/count 规则、schema 策略和强制增量 SQL 文件。 | 仅从代码可以得到实现配方，但无法可靠推导全部运维和迁移策略；人工内容在这里明显更丰富。 |
| 启动链 | 识别出环境优先启动、应用工厂注册和中间件初始化。 | 人工规则定义准确环境、运行时版本、公共包注入和冻结的启动链。 | 结构上高度一致；人工规则补充了普通源码采样无法获得的外部运维事实。 |
| 认证与 API 传输 | 识别出唯一 Axios 客户端、签名和 token 注入、登录失效处理以及 `code/data` 归一化。 | 人工规则进一步规定门户前缀、token 来源、中间件归一化和禁止 refresh 等策略。 | 生成内容足以指导普通接口开发；部署和认证正确性仍需要人工规则。 |
| 测试 | 给出后端 monkeypatch 边界测试、前端辅助函数/静态测试，并区分回归证明与构建证明。 | 人工规则指定关键测试集和执行纪律。 | 生成风格具体且有证据；人工规则补充权威验收范围。 |
| Agent 与执行策略 | 不会从源码编造角色、文档、审批、fallback 或沟通规则。 | `AGENTS.md` 定义快速执行、按需加载文档、中文回答和文档同步。 | 这些内容没有出现在盲生成草案中是正确的。它们属于策略规则，正常生成时应从可信人工说明中合并。 |

### 盲生成效果较好的部分

新的内容契约补回了旧版输出中缺失的核心内容：

- 准确的代码落点和复用位置；
- 完整的前端、后端、持久化和测试调用链；
- 项目中重复出现的本地模式，而不是 `Vue + Flask + black`；
- 共享代码影响面处理；
- 项目特有的载荷、响应、SQL 辅助函数和测试方式；
- 每条规则都带有验证方法。

12 条盲生成配方中有 9 条与当前人工指导高度重合。其余 3 条也不是填充内容：
它们揭示了代码中实际存在、但在人工规则里比较分散或隐含的实现细节。

### 仅从代码生成时不应假装知道的内容

盲生成没有足够证据将以下内容发布为权威规则：

- 准确的 Python、Node、GSDK 和驱动版本；
- 外部 `ch_apis_000` 与 `yw_utils` 的优先级策略；
- 强制增量 SQL 的命名和交付义务；
- 生产门户路径和部分 token 兼容规则；
- 文档加载与 `CLAUDE.md` 同步策略；
- 有意设置的“禁止 fallback / 禁止跨边界修补”规则。

这些人工规则本身是有价值的。正常 Init 应把它们作为可信文档证据读取并协调；
本次仅为了独立测试代码发现能力，才刻意排除了它们。

### Update Skill 应报告的漂移和冲突

当前人工规则更丰富，但不代表它们必然与当前有效源码完全一致：

- `RULES.md` 描述的默认中间件链包含
  `check_user/check_endpoint/check_limit/url_log`，而当前
  `app/__init__.py` 实际注册的是
  `options/reqvals/check_token/authz/integrity/file_filter/timestamp`。
  `backend/CLAUDE.md` 更接近当前源码。Update 应把它归类为真实冲突，
  不能静默复制任意一方。
- 根规则警告不要进行通用 Service/Repository 重构，但当前领域代码持续使用函数式
  `service.py` 和 `repository_ops.py`。正确的生成规则应保留当前具体边界，
  但不能把它描述为适用于整个框架的架构命令。
- 人工规则中的部分环境和依赖事实无法仅通过包清单核验。它们应带着来源继续作为
  文档事实保留，而不是依据弱信号重新“发现”。

### 结论

修改后的 Skills 生成的是可实际指导编码的项目手册，而不再只是项目概况。
对于这个仓库，合适的 canonical 输出应重点覆盖 `project`、`frontend`、
`backend`、`api`、`database`、`testing` 以及具有明确证据的
`restrictions`。独立的架构清单是可选项，不应挤占这些可执行规则。

安全流程也与任务规模更匹配：稳定重复的代码风格自动采纳；普通 Init/Update
只需要一次最终写入确认；普通模式不持久化审计文件；Update 只报告新增、修改、
废弃和冲突的规则语义。
