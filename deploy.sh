#!/usr/bin/env bash
# ILANG
# [TYPE:script][PROJECT:vps-deals][LANG:zh]
# ::ROLE{把 site/ 部署到 Cloudflare Pages 免域名免钱}
# ::PRECOND{环境变量 CLOUDFLARE_API_TOKEN 需要带 Cloudflare Pages: Edit 权限}
# ::BOUNDARY{never:把令牌写进仓库或任何文件|scope:permanent}
#
# 用法：  CLOUDFLARE_API_TOKEN=xxx ./deploy.sh [项目名]
set -euo pipefail

cd "$(dirname "$0")"

if [ -z "${CLOUDFLARE_API_TOKEN:-}" ]; then
  echo "缺少 CLOUDFLARE_API_TOKEN。请先导出带 Cloudflare Pages: Edit 权限的令牌。" >&2
  exit 1
fi

PROJECT="${1:-vps-deals}"

echo "==> 1/3 重新渲染站点"
python build.py

echo "==> 2/3 确保 Pages 项目存在"
npx --yes wrangler@4 pages project create "$PROJECT" --production-branch main 2>/dev/null \
  || echo "    项目已存在，跳过创建"

echo "==> 3/3 直传 site/ 到 Cloudflare Pages"
npx --yes wrangler@4 pages deploy site/ --project-name "$PROJECT" --branch main

echo
echo "完成。地址形如 https://${PROJECT}.pages.dev"
