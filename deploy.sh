#!/usr/bin/env bash
# ILANG
# [TYPE:script][PROJECT:vpsticker][LANG:zh]
# ::ROLE{把 site/ 部署到 Cloudflare Pages 免域名免钱}
# ::PRECOND{环境变量 CLOUDFLARE_API_TOKEN 带 Cloudflare Pages:Edit 权限}
# ::PRECOND{环境变量 CLOUDFLARE_ACCOUNT_ID 32 位十六进制账号 ID}
# ::WHY{只给 Pages 权限的令牌读不到账号列表 wrangler 无法自动探测 所以必须显式给账号 ID}
# ::BOUNDARY{never:把令牌写进仓库或任何文件|scope:permanent}
#
# 用法：  CLOUDFLARE_API_TOKEN=xxx CLOUDFLARE_ACCOUNT_ID=yyy ./deploy.sh [项目名]
set -euo pipefail

cd "$(dirname "$0")"

if [ -z "${CLOUDFLARE_API_TOKEN:-}" ]; then
  echo "缺少 CLOUDFLARE_API_TOKEN。请先导出带 Cloudflare Pages: Edit 权限的令牌。" >&2
  exit 1
fi

if [ -z "${CLOUDFLARE_ACCOUNT_ID:-}" ]; then
  echo "缺少 CLOUDFLARE_ACCOUNT_ID。只给 Pages 权限的令牌读不到账号列表，必须显式提供。" >&2
  echo "在 https://dash.cloudflare.com 登录后看地址栏 dash.cloudflare.com/<这里就是账号ID>/..." >&2
  exit 1
fi

PROJECT="${1:-vpsticker}"

echo "==> 1/3 重新渲染站点"
python build.py

echo "==> 2/3 确保 Pages 项目存在"
npx --yes wrangler@4 pages project create "$PROJECT" --production-branch main 2>/dev/null \
  || echo "    项目已存在，跳过创建"

echo "==> 3/3 直传 site/ 到 Cloudflare Pages"
npx --yes wrangler@4 pages deploy site/ --project-name "$PROJECT" --branch main --commit-dirty=true

echo
echo "完成。生产地址 https://${PROJECT}.pages.dev"
