# vpsticker.com 广告联盟审核前自检表（线上实测）

实测时间：2026-09-17T07:21:02Z (UTC)

| 项 | 结论 | 现状与证据 |
|---|---|---|
| 1 隐私政策页 | OK | 线上 `/privacy` HTTP 200，正文 867 词。导航/页脚可达（`<a>` 里有 2 处指向 /privacy）。已写明会放第三方广告：True；写明广告 Cookie 与退出链接：True；写明 Google/行业退出页：True。还写了本站自身不设 Cookie、不跑自有分析。 |
| 2 关于页 | OK | 线上 `/about` HTTP 200，正文 402 词。含「Who runs this」小节：True —— 写清了运营者身份（一个独立运营者 / 副业项目，非公司），并说明不卖主机、无编辑团队、无赞助内容、与厂商无关系。 |
| 3 联系页 | OK | 线上 `/contact` HTTP 200，正文 170 词。有可点邮箱链接：True（Cloudflare 邮箱保护把 `mailto:` 重写成 `/cdn-cgi/l/email-protection#...`，浏览器靠 JS 还原，功能正常）；另有**不依赖 JS** 的明文邮箱：`sanhu12138@outlook.com` —— 明文那行是刻意加的，保证不执行 JS 的抓取（含部分审核工具）也能读到真实地址。页面还写明能帮什么、不能帮什么。 |
| 4 真实内容非空壳 | OK | 全站 52 个 HTML 页，正文合计 38794 词，平均 746 词/页。最短页：`404.html` 135 词（404 页，功能性页面）。lorem ipsum / coming soon / 未渲染占位符命中：0 处。正文 <180 词的页：2 个（404.html, contact.html）。其余全部 ≥180 词，其中 28 页 ≥800 词。 |
| 5 导航与链接 | OK | 实测站内唯一 URL 51 个（含 CSS/图标）。真实断链：0 个。 另有 0 个 Cloudflare 邮箱保护重写链接（`/cdn-cgi/l/email-protection#...`）返回 404 —— 这是 CF 的邮箱混淆机制，不是本站断链；已额外提供明文邮箱兜底。全部 52 页线上逐页实测均为 HTTP 200。 |
| 6 手机端 | OK | 线上全站 viewport：`width=device-width,initial-scale=1`。页面实际引用的样式表是 `/assets/style.css?v=da4da196`（带内容指纹）。从该地址实测取到 7327 字节，含 1 处 `@media (max-width: 640px)`：标题缩小、`.facts` 从双列改单列、内边距收紧。超长 URL 换行保护 `overflow-wrap`：2 处；整页横向兜底 `overflow-x:hidden`：True；图片 `max-width:100%`：True。详情页存在 40+ 字符的裸 URL 文本（如 BuyVM 的 source page），`overflow-wrap:anywhere` 就是为它加的。对比表用 `.tablewrap{overflow-x:auto}` + 表格 `min-width:640px` 做容器内横滚，不会把整页撑宽。 |
| 7 加载速度 | OK | 首页 TTFB 实测 312 ms。线上实际传输体积：`/` 3.3 KB(br)；`/privacy` 3.1 KB(br)；`/about` 2.0 KB(br)；`/compare` 3.5 KB(br)；`/deal/ionos-vps-2-0-month` 3.7 KB(br)；`/assets/style.css?v=da4da196` 2.5 KB(br)。CSS 由 Cloudflare 用 Brotli 压缩发出（响应头 `Content-Encoding: br`）。OG 图 1200x630 且仅 5.3 KB（构建时生成）。全站自包含：无外部字体、无外部 JS、无外链图片，首屏没有任何第三方请求。`/assets/*` 配了一年版缓存并带内容指纹 `?v=<hash>`：实测内容一变指纹就变（本次从 `87021f1f` 变成 `da4da196`），所以改了样式用户不会看到旧版本。注意：不带指纹的裸路径 `/assets/style.css` 仍会命中边缘缓存里的旧副本 —— 本账号的 API 令牌没有清缓存权限（实测 `POST /purge_cache` 返回 401），但这不影响任何访问者，因为站内所有页面引用的都是带指纹的地址。 |

## 未通过的项

无。七项全部通过。

## 需要你知道的两条实测限制

1. **外链里有两个非 200，都不是本站问题**：
   - `https://www.aboutads.info/choices/` 返回 429 —— 该站对本机限流，浏览器里正常。
   - `https://www.inmotionhosting.com/vps-hosting` 返回 403 —— 该厂商对这台机器反爬，不是页面写错；它同时也出现在抓取器的 sources 记录里。
2. **`/cdn-cgi/l/email-protection#...` 返回 404 是 Cloudflare 行为**，不是断链：CF 把页面上所有 `mailto:` 重写成这个前缀并靠 JS 还原。所以联系页额外加了一行明文邮箱，保证不执行 JS 的环境（含部分审核工具）也读得到。
