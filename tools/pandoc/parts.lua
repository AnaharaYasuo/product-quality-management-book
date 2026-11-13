-- tools/pandoc/parts.lua
-- 1. 各部の最初の章の前に「部扉」の見出しを挿入する（EPUB の目次と本文に部の区切りを出す）。
--    内容は tools/build_pdf.py の PART_STARTS と一致させること。
-- 2. 環境変数 MERMAID_IMAGE_DIR が指定されている場合、```mermaid コードブロックを
--    事前レンダリング済みの高解像度PNG画像（mermaid-001.png ...）へ置換する。
--    期待されるPNGファイルが存在しない場合は fail-closed（エラー終了）とする。

local parts = {
  [1] = "第I部：パラダイムシフトと二大成果物モデル",
  [3] = "第II部：プロダクト成果物の検証・レビュー・監査",
  [10] = "第III部：開発プロセス成果物のバリエーションと品質保証",
  [14] = "第IV部：動的検証・シフトライト・セキュリティ品質",
  [17] = "第V部：AIプロダクトと自律型AIエージェントの品質保証",
  [20] = "第VI部：組織変革・カルチャーと品質の未来",
  [22] = "第VII部：品質のトレードオフ・倫理・現場のリアリズム",
}

local mermaid_dir = os.getenv("MERMAID_IMAGE_DIR")
local mermaid_idx = 0

function Header(el)
  if el.level ~= 1 then
    return nil
  end
  local n = pandoc.utils.stringify(el):match("^第(%d+)章")
  if n == nil then
    return nil
  end
  local title = parts[tonumber(n)]
  if title == nil then
    return nil
  end
  local part = pandoc.Header(1, pandoc.Inlines(title), pandoc.Attr("part-" .. n, { "part" }))
  return { part, el }
end

function CodeBlock(el)
  if not el.classes:includes("mermaid") then
    return nil
  end
  if mermaid_dir == nil or mermaid_dir == "" then
    return nil
  end
  mermaid_idx = mermaid_idx + 1
  local img_path = string.format("%s/mermaid-%03d.png", mermaid_dir, mermaid_idx)
  local fh = io.open(img_path, "rb")
  if fh == nil then
    error(string.format("[parts.lua] Missing pre-rendered Mermaid PNG for diagram #%d: %s", mermaid_idx, img_path))
  end
  fh:close()
  local alt = string.format("図%d", mermaid_idx)
  local img = pandoc.Image({ pandoc.Str(alt) }, img_path)
  return pandoc.Div({ pandoc.Plain({ img }) }, pandoc.Attr("", { "mermaid-figure" }))
end
