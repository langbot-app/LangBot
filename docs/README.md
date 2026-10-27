# [LangBot](https://github.com/langbot-app/LangBot) 官方文档

> 此仓库是 LangBot 的文档仓库，代码仓库：  
> [LangBot 代码仓库](https://github.com/langbot-app/LangBot)  
> 这是 LangBot 4.0 的文档，3.0 文档请见 `v3` 分支

## 参与编写

文档使用 [Fumapress](https://press.fumadocs.dev/) 和 [Fumadocs](https://fumadocs.dev/) 生成，本地开发需要 Node.js 24 或更高版本。

Clone 本仓库，在目录下执行以下命令安装依赖：

```bash
npm ci
```

完成后即可修改文档，修改完后使用以下命令本地启动预览：

```bash
npm run dev
```

### 使用图片

把图片放到 `images` 目录下，然后在文档中使用绝对路径引用（相对于项目根目录），如：

```markdown
![image](/images/xxx.png)
```

### 部署细节

文档构建为 `dist/public` 下的静态站点，并托管在 Cloudflare Pages。部署前会运行类型检查、文档契约测试及完整静态构建。

### Agent 可读导出

`npm run build` 会在 `/docs` 基路径和站点地图处理完成后生成 Agent 文本。
每个已发布页面都有 `.md` 副本，HTML 使用 `rel="alternate" type="text/markdown"`
声明该地址，不改变可视界面。

- `/docs/llms.txt`、`/docs/llms-full.txt`：全部语言的索引与完整正文。
- `/docs/{en,zh,ja}/llms.txt`、`llms-full.txt`：对应语言的索引与正文。
- 各目录的 `llm.txt` 是 `llms.txt` 的兼容别名。
- `/docs/openapi/service-api-{en,zh,ja}.json`：完整 API 规范。

生成器直接解析源 MDX 的 Markdown AST，保留提示标题和图片地址；每个 API
操作包含请求、响应、鉴权及递归引用的 schema。遇到未支持的语义 JSX 或可执行
表达式会中止构建，避免静默丢失正文。请修改 MDX/OpenAPI 源文件，不要编辑
`dist/public` 中的生成结果。`npm test` 检查转换逻辑，构建后的
`npm run test:static` 检查站点地图覆盖、HTML 发现链接、内部链接与 API 契约。
已有完成基路径处理的构建可使用 `npm run generate:agent-docs` 单独更新文本。

### 一些规范化标准

- 文件夹和文件的命名：**一律使用全小写，单词直接`-`隔开，如**`plugin-intro.mdx`
- 子文件（夹）的命名，**不加前缀**（即文件夹的名称），如：`deploy`文件夹下的，文件夹`langbot`，`langbot`文件夹下的`manual`文件称之为`manual.mdx`
- 文档文件格式统一使用 `.mdx`；构建脚本会把现有 Mintlify 兼容组件转换为 Fumadocs 可渲染格式。
- 在 `docs.json` 中配置侧边栏导航结构。

---

**[English README](README_EN.md)**
