---
name: probe-workspace
description: .tmp/issue-probes/ の正本、編集責任、証拠の辿り方、ID、鮮度、方針の規約。成果物を読み書きするときに使う。
---

# 調査成果物の扱い

issue-probe は調査対象コードのリポジトリ直下の `.tmp/issue-probes/` に成果物を置く。`.tmp/.gitignore` は `*` だけを持つ。

調査依頼の issue と調査対象のコードは別のリポジトリにあることがある。ワークスペースはコード側に作る。証拠はコードを指すので、証拠と同じ場所に置くほうが辿りやすい。

```text
.tmp/
├── .gitignore
└── issue-probes/
    ├── <issue番号>/
    │   ├── issue.json        # issue のメタと本文。調査観点の出どころ。prepare.py が作る
    │   ├── schema.json       # シートの列構成。report.tsv の検証契約。メインが書く
    │   ├── coverage.json     # 網羅性の検索定義と実測件数。メインが定義し count_hits.py が件数を書く
    │   ├── policy.md         # その issue だけの調査方針。共有方針より優先する。無いことが普通
    │   ├── findings.md       # front matter、スコープ、観点の対応、該当なし、確定できなかったこと。メインが書く
    │   ├── findings/<観点>.md # 観点ごとの証跡。issue-investigator が1ファイル1ライターで書く
    │   ├── report.tsv        # 一覧の正本。シートに載る内容そのもの。メインが書く
    │   ├── verdicts.md       # 再検証のラウンド記録。メインが統合して書く
    │   └── issue-comment.md  # issue へ貼る対外報告文。メインが書く
    ├── policy.md             # そのリポジトリの全 issue に効く調査方針。無ければ方針なし
    └── <主題>.md             # issue から独立に成り立つ背景知識。関心ごとに1ファイル
```

`policy.md` は方針の予約名である。

## 正本と派生

report.tsv は一覧の正本である。シートに載る内容そのものを持ち、1列目 No. が項目の不変IDになる。

findings.md と `findings/` は根拠の正本である。report.tsv の各行がなぜそう書けるかは、ここにしか無い。

issue-comment.md は対外報告文の正本である。一覧に載らない全体判断（改修計画、優先順位、関係者確認事項）はここが持つ。閲覧用の要約を別ファイルに二重で持たない。

`schema.json` と `coverage.json` は契約である。前者はシートの列、後者は網羅性の検索定義を宣言し、いずれも check_rows.py と count_hits.py が読む。

report.tsv と findings は現在の状態、verdicts.md は再検証による変更と削除の履歴を持つ。verdicts.md の各 `## <codeSha>` は、そのコミットで実施した1回の再検証を表す。

## 問いと在り処

| 問い | 読む場所 |
|---|---|
| この項目の根拠は何か | `findings/` のいずれかにある `### <番号>` の節 |
| 何を調べて何が無かったのか | findings.md の「該当なしと確認した観点」と coverage.json の検索定義 |
| その件数はどう数えたのか | coverage.json の `searches`。`count_hits.py` が記録した値であり、手で数えた値ではない |
| シートのどの列に何が入るのか | schema.json の `columns`。順序がシートのヘッダ行と一致する |
| 調査依頼には何が書かれていたか | issue.json の `body` と `comments` |
| 再検証でなぜ変わったか | verdicts.md を新しいラウンドから辿り、同じ番号が最初に現れる節 |
| 欠番の項目は何だったのか | verdicts.md の delete 評決。取り下げの理由はここにしか残らない |
| まだ確定していないことは何か | findings.md の「確定できなかったこと」。誰が何をすれば確定するかまで書く |
| この調査は現在のコードとどれだけずれているか | findings.md の `codeSha` と現在の HEAD。check_rows.py が差を `info` に出す |

## ID の規約

report.tsv の1列目 No. が論理的な項目の不変IDである。

更新でも削除でも番号を詰め直さない。欠番は再利用しない。シートは一度貼ると行位置が固定されるため、詰め直すと転記済みの行と一覧の対応が壊れる。欠番のある一覧は見た目が不揃いになるが、対応が壊れるより望ましい。

findings.md の front matter の `nextItem` は、report.tsv・`findings/`・verdicts.md に現れるすべての番号より大きい。新規項目へ割り当てるたびに1増やす。check_rows.py がこの不変条件を検証する。

削除は report.tsv と `findings/` の現在状態へ反映し、verdicts.md に delete の評決として理由を残す。評決の無い削除は check_rows.py が problem にする。

## 件数の扱い

件数はスクリプトが測る。coverage.json に検索定義を書き、`count_hits.py` が実行して件数を記録し、成果物はその記録を引く。

手で数えた件数を成果物に書かない。過去の調査では手で数えた件数が後の検証で覆り、対外成果物の数字が実態とずれていた。

スコープを伴わない件数は意味を持たない。coverage.json の `scope` が対象ディレクトリを宣言し、件数はその範囲でのみ成立する。

## 鮮度の確認

調査は findings.md の `codeSha` が表す時点のコードに対して成立する。現在との差はユーザーへ伝え、追随には probe-issue の再実行を使う。

`check_rows.py` は `codeSha` と現在の HEAD の差を `info` に載せる。停止はさせない。差があること自体は誤りではなく、報告すべき事実である。

## 調査方針

`policy.md` は調査の対象と結論の書き方を制約する。

優先順位は3段で、下が上を上書きする。

1. 既定。`issue-investigator.md` の調査の観点・除外基準・リスク度の判定基準
2. 共有方針。`.tmp/issue-probes/policy.md`。そのリポジトリの全 issue に効く
3. issue個別方針。`.tmp/issue-probes/<番号>/policy.md`。その issue だけに効く

条項IDはファイルごとに `P1` から振り、外からは `共有P1`・`個別P1` の形で参照する。

方針が上書きできないものが3つある。リスク度、証拠の要否、観測した事実である。リスク度は判定基準と証拠が決めるものであり、条項を根拠に動かさない。これらを上書きしようとする条項は無効として扱い、その旨を報告する。

## 手を入れるとき

probe-issue は調査と一覧の作成、verify-items は既存項目の再検証、withdraw-items は指定項目の取り下げを担う。セルの文面は row-style に従う。

`findings/` は1ファイル1ライターである。並列で調査するとき、エージェントは自分の担当観点のファイルだけを書く。findings.md と report.tsv と issue-comment.md はメインが書く。

外向きの書き込みは行わない。シートへの貼り付けと issue への投稿は人が行う。成果物はそのための材料であり、貼れば済む形になっていることが完成条件である。
