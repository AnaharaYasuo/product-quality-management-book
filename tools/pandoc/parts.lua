-- tools/pandoc/parts.lua
-- 各部の最初の章の前に「部扉」の見出しを挿入する（EPUB の目次と本文に部の区切りを出す）。
-- 内容は tools/build_pdf.py の PART_STARTS と一致させること。
local parts = {
  [1] = "第I部：パラダイムシフトと二大成果物モデル",
  [3] = "第II部：プロダクト成果物の検証・レビュー・監査",
  [10] = "第III部：開発プロセス成果物のバリエーションと品質保証",
  [14] = "第IV部：動的検証・シフトライト・セキュリティ品質",
  [17] = "第V部：AIプロダクトと自律型AIエージェントの品質保証",
  [20] = "第VI部：組織変革・カルチャーと品質の未来",
  [22] = "第VII部：品質のトレードオフ・倫理・現場のリアリズム",
}

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
