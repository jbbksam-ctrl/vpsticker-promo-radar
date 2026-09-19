# upload_kit — 两个需要你本人出账号的地方，素材已备好

这两件事的共同点是：**注册、收验证信、点确认链接只能你本人做**，我替不了。
除此之外的东西（文件、元数据、说明文字）已经全部准备好，你只需要拖拽和粘贴。

两个目录各管一个平台：

| 目录 | 去哪里 | 干什么 |
|---|---|---|
| `zenodo/` | https://zenodo.org | 传 3 个数据文件，拿一个 DOI |
| `huggingface/` | https://huggingface.co | 建一个 dataset 仓库，传 4 个文件 |

---

## zenodo/

要传的文件（3 个，全部在 `zenodo/` 里）：

- `vpsticker-vps-prices.json`
- `vpsticker-vps-prices.csv`
- `fetch-status.csv`

表单每一栏填什么，见 **`zenodo/ZENODO-FIELDS.md`**，照着抄就行。

为什么值得做：Zenodo 会给这个数据集一个 **DOI**。DOI 是一个永久标识符，
论文、文章、别人的项目里引用数据集时用的是它，不是 URL —— 而 DOI 是目前
唯一一种「对方不需要信任你、也能确认这份数据没被改过」的引用方式。

## huggingface/

要传的文件（4 个，全部在 `huggingface/` 里）：

- `README.md` ← **必须叫这个名字**，里面的 YAML 头是给平台读的，别改
- `vpsticker-vps-prices.json`
- `vpsticker-vps-prices.csv`
- `fetch-status.csv`

建仓库时选 **Dataset** 类型（不是 Model），名字建议 `vpsticker-vps-prices`。

为什么值得做：Hugging Face 上的数据集页面自带预览器，别人打开就能直接看表格，
不用下载。它是目前「别人随手找数据」最常用的入口之一。

---

## 两个平台都用同一份数据

这里面的文件就是仓库 `dataset/` 里的那一份，内容一模一样。
快照时间写在 `vpsticker-vps-prices.json` 的 `generated_at` 字段里。

数据本身是 CC0 1.0（公有领域），两个平台都选这个许可证：

- Zenodo 的许可证编号：`cc0-1.0`（显示名 `Creative Commons Zero v1.0 Universal`）
- Hugging Face 的许可证标识：`cc0-1.0`（**全小写**，写成 `CC0-1.0` 平台认不出来）

这两个编号不是猜的，是分别查了 Zenodo 和 Hugging Face 的公开接口确认过的。
