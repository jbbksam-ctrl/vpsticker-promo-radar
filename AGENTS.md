ILANG
[TYPE:agents][PROJECT:vpsticker][LANG:zh]

::STATE{@PROJECT, name:vpsticker-promo-radar, kind:优惠细分垂直站, brand:vpsticker, niche:VPS hosting deals, runtime:GitHub Actions 加 Cloudflare Pages, lang:Python 标准库}

::MODULE{WHAT|title:这个项目是什么}
  一个自己会更新的 VPS 优惠站 数据来自各家厂商自己的公开定价页
  管线是 抓取 写 json 渲染 出静态站 每 6 小时跑一次 每次留一条 commit
  站点规则写在 .ilang/site.ilang 那是对配置的唯一真源

::MODULE{FILES|title:每个文件管什么}
  .ilang/site.ilang   配置唯一真源 品牌 域名 厂商清单 字段 页面规则 更新频率
  ilang_config.py     解析 site.ilang 唯一实现
  scraper.py          抓公开页 写 data/offers.json
  build.py            读 offers.json 渲染 site/ 生成 sitemap 与 robots
  og_image.py         手写 PNG 编码器 生成社交分享大图
  templates/          页面版式 纯文本加占位符
  data/offers.json    数据集 每次跑覆盖
  site/               渲染产物 提交进仓库

::MODULE{ALLOWED|title:允许的动作}
  改 .ilang/site.ilang 加厂商 改品牌 改域名 改更新频率
  改 templates/ 调版式 但要保证 build.py 的占位符对得上
  改 scraper.py 的提取逻辑 加新的提取档位
  加新的厂商 前提是先本地跑一次确认真的出数

::MODULE{DATASOURCE|title:数据从哪来}
  只读公开页面 厂商官方定价页 sitemap feed
  遵守 robots.txt 按 User-agent 分组判定 不把给别的爬虫的规则算到自己头上
  不绕反爬 不登录 不抓登录后的内容
  抓不到的就不写 不许拿估的填

::RULE{配置只在 .ilang/site.ilang 一处 不许在 py 文件里另写一份厂商清单 改了 site.ilang 站就必须变}
::RULE{改完必须本地跑 scraper.py 加 build.py 确认 site/ 真的变了 再说改好了}
::RULE{每条 offer 必须能追到 source_url 与 fetched_at}
::BOUNDARY{never:编优惠 编价格 编佣金 编折扣幅度 绕反爬 抓登录后内容 刷量 买粉|scope:permanent}

::MODULE{KNOWN_GAPS|title:已知的坑 别重复踩}
  JS 渲染的页面抓不到价格 Hetzner A2 Hosting HostHatch 属于这类 加了也是 no_price
  返回 403 的厂商 Linode Vultr Contabo InterServer RackNerd Kamatera LiquidWeb Time4VPS 属于这类
  Hetzner 服务器拍卖页 sb 看起来有价格 实际是 JS 渲染 只有脚注里那个 37.30 能被正则捞到 不要用它
  regex 档位只出每个周期最便宜的一档 这是故意的 铺整张价目表会变成同标题刷屏

::MODULE{IF_YOU_ARE_AN_AI|title:接手这个仓库的 AI 看这里}
  先读 .ilang/site.ilang 再读这份文件 然后才动代码
  要改行为就改 site.ilang 要改呈现才动 templates 和 build.py
  不确定某个厂商能不能抓 就本地跑一次看 sources 那行报什么
  任何情况下都不要为了让页面好看而补一个编出来的价格
