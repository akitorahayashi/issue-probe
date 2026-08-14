---
name: probe-issue
description: GitHub issue の調査依頼を調べ、一覧と根拠を持つ findings.md と issue コメント草案を作る。
argument-hint: <issue番号1, issue番号2...>
disable-model-invocation: true
compatibility: Claude Code（サブエージェントの起動と再開に Agent ツールと SendMessage ツールを使う）、python3 3.10以上、repo スコープで認証済みの gh CLI、git、ripgrep
---

# issue の調査

指定された issue の調査依頼を読み、調査対象コードのリポジトリ直下 `.tmp/issue-probes/<番号>/` に findings.md と issue-comment.md を作る。関連する複数 issue の調査は並行する。

issue-investigator が観点ごとの調査と調査結果の報告、メインがユーザーとの対話、契約の確定、スクリプト、findings.md、issue-comment.md を担当する。成果物はメインだけが書く。

以下の `<plugin-root>` は、この SKILL.md の2階層上として解決する。成果物の正本と編集責任は[調査成果物の扱い](../probe-workspace/SKILL.md)に従う。

## 生成するファイル

| 生成先 | 内容 |
|---|---|
| `<dir>/coverage.json` | 網羅性の検索定義。[coverage](assets/coverage.json)をメインが実体化する |
| `<dir>/findings.md` | 一覧と根拠の正本。[findings](assets/findings.md)をメインが実体化する |
| `<dir>/issue-comment.md` | issue へ貼る報告文。[issue-comment](assets/issue-comment.md)をメインが実体化する |

prepare.py は `<dir>` と issue.json を用意する。シート転記用の paste.tsv は export-items が作る。

## 手順

### 1. 準備

依頼文から issue の番号を取る。受け取れなければ質問し、回答を得てから進める。

issue 番号ごとに実行する。git の状態を触るため並列にせず、1つずつ回す。

```bash
python3 <plugin-root>/scripts/prepare.py <issue番号> [--repo <owner/name>]
```

- 終了コード0: `dir` が作業場所になる。`issueRepo` と `codeRepo` が違う場合は、調査対象がコード側であることを確認して進む
- 終了コード2・4: その issue を止め、stderr の理由と `action` が示す選択肢をユーザーに渡す

`--repo` は issue があるリポジトリを指す。省略すると調査対象リポジトリの origin を使う。調査依頼が別のドキュメントリポジトリにある構成では省略できない。

`state` が OPEN でない issue は、続行するかユーザーに確認する。

共有の `.tmp/issue-probes/policy.md` を読む。あれば条項数を報告する。依頼文に issue 個別の方針があれば `<dir>/policy.md` に記録する。

### 2. 網羅性の定義

issue.json の `body` と `comments` から、調査観点・スコープ・除外を読む。調査依頼には検索キーワードや分類が明記されていることが多い。

`<dir>/coverage.json` に網羅性の検索定義を書く。issue に列挙された検索キーワードは、採用・不採用にかかわらず全て入れる。「調べたが該当なし」も成果物であり、後で網羅性の証跡になる。`scope` には検索対象のディレクトリを並べる。

シートの列構成は確定しなくてよい。`scripts/columns.py` が全 issue 共通で持つ。

### 3. 網羅性の計測

```bash
python3 <plugin-root>/scripts/count_hits.py <dir>
```

- 終了コード0: 件数が coverage.json に記録された。以降、成果物に書く件数はこの記録を引く
- 終了コード2・4: その issue を止め、`action` をユーザーに渡す

以降、手で数えた件数を成果物に書かない。数え直す必要が出たら coverage.json に検索定義を足して再実行する。

### 4. 調査

観点ごとに `issue-probe:issue-investigator` を1つのメッセージで並列起動する。Agent ツールの `subagent_type` は `issue-probe:issue-investigator`。各 prompt に書くのは次の2つだけで、issue の情報は investigator が `<dir>` から読む。

- 作業場所 `<dir>`
- 担当する観点

観点の切り方は責務で決める。上限は5体。

- issue が分類を持つならそれに従う。持たないなら「何を疑うか」で切る
- 同じファイル群を読んで同じ機構を論じることになる2つは、1つの観点である。分けると同じ調査が二重に走り、同じ原因が2項目になる
- 観点が1つなら investigator も1体でよい。0体にはしない。横断検索と読み込みをメインのコンテキストから隔離する価値は観点数に依らない

項目番号は渡さない。採番は手順5でメインが行う。事前に範囲を配ると、使われなかった番号が主張を持たない欠番になる。

investigator は項目ごとの節と、確定できなかったことを返す。全観点の応答とエージェントIDを受け取ってから手順5へ進む。

### 5. 一覧化

全観点の応答を読み、[一覧セルの文体](../row-style/SKILL.md)に従って `<dir>/findings.md` を書く。

- 見出しと項目の形式は[調査成果物の扱い](../probe-workspace/SKILL.md)の見出し規約に従う
- 観点をまたいで同じ原因・同じ直し方になるものは1項目に統合する。観点で分けて調べたことと、項目の切り方は別である
- 番号を1から振るのは findings.md が無いときだけ。既にある場合はコードの変化に追随する再実行なので、同じ主張には既存の番号をそのまま使い、新しい主張だけを `nextItem` から割り当てる。取り下げ済みの番号は再利用しない
- 番号は昇順に並べ、`nextItem` を割り当てた最後の番号より1大きい値にする
- front matter・スコープと除外・網羅性・項目・該当なしと確認した観点・確定できなかったことを書く
- 網羅性の件数は coverage.json の記録を引く

確定できなかったことは、何が未確定かと、誰が何をすれば確定するかの両方を書く。実機や通信の実測が要る場合はそう書く。この工程では実測しない。

### 6. 検査

```bash
python3 <plugin-root>/scripts/check_items.py <dir>
```

- 終了コード0: 受け入れた。`info` の工数合計とリスク分布を控えて次へ進む
- 終了コード1: `problems` を種類で分ける。見出し・フィールド・書式のものはメインが findings.md を直す。根拠の不足や内容の誤りは、該当する観点の issue-investigator に `SendMessage` で追加調査を依頼し、返答をメインが反映する
- 終了コード2: findings.md が読めない。`action` に従って直してから再実行する

終了コード0まで繰り返す。

### 7. 報告

[issue-comment](assets/issue-comment.md)の構造で `<dir>/issue-comment.md` を書く。要約、改修計画、関係者確認をお願いしたい事項、本チケット対象外として切り出したものを持つ。

issue 番号ごとに次を伝える。

- findings.md のパスと項目数
- `info` の工数合計とリスク度の分布
- 確定できなかったことの一覧と、それぞれ誰が何をすれば確定するか
- issue-comment.md のパス

実測が必要な項目があれば、agent-device や charles-traffic のような実測用プラグインの利用を案内する。このスキルからは起動しない。

次の入口を示す。

```text
export-items <番号>
verify-items <番号1> <番号2>
withdraw-items <番号1>:3,7
```

## 規律

- 対象リポジトリへの書き込みは `.tmp/issue-probes/` 配下に置く
- シートへの貼り付けと issue への投稿は行わない。成果物は人が貼るための材料である
