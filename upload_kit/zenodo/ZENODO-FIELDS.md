# Zenodo 上传表单 —— 每一栏填什么

打开 https://zenodo.org ，登录后点右上角的 **`+`** → **`New upload`**。
下面按表单从上到下的顺序写。**加粗的是直接粘贴的原文**，其余是说明。

---

## Resource type

选 **Dataset**。

## Title

```
vpsticker VPS price dataset
```

## Creators

填 **`jbbksam-ctrl`**。

这是你的 GitHub 用户名。**不要填真名** —— 一旦发布，作者名会永久写进 DOI 的元数据里，
而 DOI 是设计成删不掉的。填用户名既满足「有作者署名」，又不暴露个人信息。

`Affiliation`（单位）和 `ORCID` 两栏留空。不是必填。

## Description

下面这段整段粘贴。它是英文的，因为 Zenodo 的读者和引用者基本都是英文语境：

```
Published monthly and annual prices for virtual private server (VPS) plans, read
directly from the public pricing pages of 15 hosting providers. 30 offers in this
snapshot, each carrying the exact source URL it was read from and the UTC timestamp
of the fetch.

No price is estimated, interpolated, or filled in by hand. Where a provider does not
publish a machine-readable price, the offer is listed without a price rather than
guessed. The accompanying fetch-status table records the HTTP status and extraction
method for every provider, including providers that returned nothing.

Distributed as JSON and CSV. Covers consumer and small-business VPS plans only — not
dedicated servers, shared hosting, or GPU instances. Currencies are not converted
across USD and EUR; a separate price_monthly column normalises the billing cycle, not
the currency.

A live, continuously refreshed version of the same data is at https://vpsticker.com/
The column definitions are documented at
https://github.com/jbbksam-ctrl/vpsticker-promo-radar/blob/main/dataset/README.md
```

**关于「30 offers」这个数字**：这是你上传那一刻的快照条数。上传前先打开
`vpsticker-vps-prices.csv` 数一下行数（减去表头那行），跟这个数字对不上就改成实际的。
数字写错比数字不写更糟 —— 引用者会拿它做校验。

## License

在下拉框里选 **`Creative Commons Zero v1.0 Universal`**。

编号是 `cc0-1.0`，我查过 Zenodo 的公开许可证接口确认过这个编号存在。

## Keywords

一行一个，或者用逗号分隔：

```
VPS
virtual private server
hosting prices
price comparison
cloud computing
web hosting
pricing
economics
```

## Languages

选 **English**。

## Version

```
1.0
```

## Publisher

```
vpsticker
```

## Dates

`Date type` 选 **Issued**，日期填 `2026-09-19`（就是快照日期）。
如果你上传时已经是别的日子，填上传当天。

## 文件

点 `Choose files` 或直接把 `zenodo/` 里这 3 个拖进去：

- `vpsticker-vps-prices.json`
- `vpsticker-vps-prices.csv`
- `fetch-status.csv`

## 最后一步

点 **`Publish`**。

**DOI 是在点下 `Publish` 的那一刻才注册的。** 在那之前它只是一份草稿，没有 DOI。

草稿阶段可以先点 `Get a DOI now!` 预留一个号，但 Zenodo 官方文档明确写了：
**删掉草稿这个号就没了**。所以预留之后别删草稿。

另外一条官方限制：**发布之后文件只能在 45 天内改**（原文：
`After the record is published you can only add, remove or modify files by yourself within 45 days`）。
元数据随时能改。所以第一次上传就把 3 个文件传全。
