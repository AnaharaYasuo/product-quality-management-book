"""
AI Book Reviewer (LLM-as-a-Judge)
技術原稿が「人間にとって有意義か、現場で役立つか、面白いか」を5大次元で評価する審査プロンプト生成・評価エンジン。
"""

import sys
import argparse
from pathlib import Path

REVIEW_RUBRIC_PROMPT = """
### [役割・コンテキスト]
あなたは15年以上の開発・QA経験を持つプリンシパルエンジニア兼テクニカルライターです。
対象書籍『プロダクト品質管理の実践ガイド』の該当章原稿を、現場のエンジニア・QA・PMにとって「本当に有意義で価値があるか」という読者体験の観点から厳格に審査してください。

---

### [5大評価次元ルーブリック（各1〜5点）]

1. **実務解像度（Actionability）**
   - 5点: 概念論にとどまらず、コピペで使えるコード、プロンプト、設定ファイル、具体的なツール名が網羅され、明日から現場で実践できる。
   - 3点: 理論は正しいが、現場でどうコードに落とせばいいのか具体的な一歩が少し曖昧。
   - 1点: 一般論・綺麗事のみ。「で、どうすればいいの？」という疑問が残る。

2. **現場リアリズム・共感度（Pain & Empathy）**
   - 5点: 現場が直面する泥臭いペイン（レビュー疲れ、Flakyテスト、形骸化、組織の壁）への深い共感と、リアルなアンチパターンが描かれている。
   - 3点: 課題感は分かるが、教科書的で現場の切迫感や泥臭さがやや薄い。
   - 1点: 現場の実態を無視した机上の空論。理想論の押し付け。

3. **論理的納得感（Logical Conviction）**
   - 5点: DORAの科学的データ、ISO規格、工学的トレードオフに基づき、なぜそうすべきかが完全に論証されている。
   - 3点: 結論には同意できるが、論拠やデータの裏付けが一部弱い。
   - 1点: 主観的な思い込みや根拠のない断定が目立つ。

4. **認知的テンポ・面白さ（Engagement）**
   - 5点: 問いかけ、対比、具体例、Mermaid図解がリズミカルに配置され、一気に引き込まれて読める。
   - 3点: 普通の技術書。やや文章が硬く、長文が続いて集中力が切れかける箇所がある。
   - 1点: 退屈な辞書・仕様書の引き写し。眠くなる。

5. **読後感・持ち帰り価値（Takeaway Value）**
   - 5点: 章末に明確な結論と、即日使えるセルフチェックリスト/演習があり、読後に視界が開けた感覚がある。
   - 3点: 勉強にはなったが、読み終わった後に何をすればいいかのアクションがやや弱い。
   - 1点: 読んだ後に何も残らない。

---

### [3つのペルソナによる読者フィードバック]
以下の3者の視点から、それぞれ率直な感想・ツッコミを述べてください：
- **ペルソナA：忙しいテックリード**（「開発速度を落とさずにどう品質を保つか」に関心）
- **ペルソナB：品質保証・QAエンジニア**（「テストの網羅性と合否判定」に関心）
- **ペルソナC：ジュニアエンジニア**（「分かりやすさと実践のしやすさ」に関心）

---

### [出力フォーマット（JSON形式）]
```json
{
  "scores": {
    "actionability": <1-5>,
    "pain_empathy": <1-5>,
    "logical_conviction": <1-5>,
    "engagement": <1-5>,
    "takeaway_value": <1-5>
  },
  "overall_score": <1.0-5.0の平均値>,
  "persona_reviews": {
    "tech_lead": "テックリード視点でのコメント・ツッコミ",
    "qa_engineer": "QAエンジニア視点でのコメント・ツッコミ",
    "junior_dev": "ジュニア視点でのコメント・ツッコミ"
  },
  "strengths": [
    "ここが特に優れている点1",
    "ここが特に優れている点2"
  ],
  "actionable_improvements": [
    "ここをこう改善すればさらに良くなる点1",
    "ここをこう改善すればさらに良くなる点2"
  ]
}
```
"""

def generate_review_prompt(file_path):
    path = Path(file_path)
    if not path.exists():
        print(f"Error: File not found {file_path}")
        sys.exit(1)

    with open(path, "r", encoding="utf-8") as f:
        content = f.read()

    full_prompt = f"{REVIEW_RUBRIC_PROMPT}\n\n### [審査対象の原稿: {path.name}]\n```markdown\n{content}\n```\n"
    return full_prompt

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate LLM-as-a-Judge review prompt for technical manuscripts.")
    parser.add_argument("file", help="Path to the manuscript markdown file")
    parser.add_argument("--output", "-o", help="Optional output file to save prompt")

    args = parser.parse_args()
    prompt = generate_review_prompt(args.file)

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(prompt)
        print(f"Review prompt generated and saved to: {args.output}")
    else:
        print(prompt)
