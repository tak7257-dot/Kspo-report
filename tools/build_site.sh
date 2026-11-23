#!/bin/sh
# web/app → 공개용 폴더(기본 _site). GitHub Pages 배포와 화면 테스트가 같은 결과물을 쓴다.
# claude.ai 미리보기는 문서 머리말(doctype·charset·viewport)을 자동으로 붙여 주지만 Pages는 아니라서 여기서 붙인다.
set -e
OUT=${1:-_site}
ROOT=$(cd "$(dirname "$0")/.." && pwd)
rm -rf "$OUT"; mkdir -p "$OUT"
cp -R "$ROOT/web/app/." "$OUT/"
{
  printf '<!doctype html>\n<html lang="ko">\n<head>\n<meta charset="utf-8">\n'
  printf '<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">\n'
  cat "$ROOT/web/app/index.html"
} > "$OUT/index.html"
