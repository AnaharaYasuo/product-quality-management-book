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

  -- Mermaidコードから図の種類・サブグラフ名・ノードラベルを抽出し、詳細な代替テキストを生成する
  local src = el.text or ""
  local diagram_type = "ダイアグラム"
  if src:match("^%s*flowchart") or src:match("^%s*graph") then
    diagram_type = "フローチャート"
  elseif src:match("^%s*sequenceDiagram") then
    diagram_type = "シーケンス図"
  elseif src:match("^%s*stateDiagram") then
    diagram_type = "状態遷移図"
  elseif src:match("^%s*classDiagram") then
    diagram_type = "クラス図"
  elseif src:match("^%s*erDiagram") then
    diagram_type = "ER図"
  elseif src:match("^%s*quadrantChart") then
    diagram_type = "象限チャート"
  elseif src:match("^%s*gitGraph") then
    diagram_type = "Gitグラフ"
  end

  local labels = {}
  local seen = {}
  for lbl in src:gmatch('%["([^"]+)"%]') do
    local clean = lbl:gsub("<br%s*/?>", " "):gsub("%s+", " "):match("^%s*(.-)%s*$")
    if clean ~= "" and not seen[clean] then
      seen[clean] = true
      table.insert(labels, clean)
      if #labels >= 8 then break end
    end
  end
  if #labels == 0 then
    for lbl in src:gmatch("%[([^%[%]\"]+)") do
      local clean = lbl:gsub("<br%s*/?>", " "):gsub("%s+", " "):match("^%s*(.-)%s*$")
      if clean ~= "" and not seen[clean] then
        seen[clean] = true
        table.insert(labels, clean)
        if #labels >= 8 then break end
      end
    end
  end

  local alt
  if #labels > 0 then
    alt = string.format("図%d（%s）: %s", mermaid_idx, diagram_type, table.concat(labels, " / "))
  else
    alt = string.format("図%d（%s）: 構成・処理フロー図解", mermaid_idx, diagram_type)
  end

  local img = pandoc.Image({ pandoc.Str(alt) }, img_path, alt)
  return pandoc.Div({ pandoc.Plain({ img }) }, pandoc.Attr("", { "mermaid-figure" }))
end
