---
name: probe-issue
description: GitHub issue の調査依頼を調べ、シート転記用の report.tsv と issue コメント草案を作る。
argument-hint: <issue番号1, issue番号2...>
disable-model-invocation: true
compatibility: Claude Code（サブエージェントの起動と再開に Agent ツールと SendMessage ツールを使う）、python3 3.10以上、repo スコープで認証済みの gh CLI、git、ripgrep。列定義の初期生成にのみ Google Drive MCP を使う（任意）
---

# issue の調査

指定された issue の調査依頼を読み、調査対象コードのリポジトリ直下 `.tmp/issue-probes/<番号>/` に report.tsv と findings と issue-comment.md を作る。関連する複数 issue の調査は並行する。

issue-investigator が観点ごとの調査と `findings/<観点>.md`、メインがユーザーとの対話、契約の確定、スクリプト、report.tsv、findings.md、issue-comment.md を担当する。

以下の `<plugin-root>` は、この SKILL.md の2階層上として解決する。成果物の正本と編集責任は[調査成果物の扱い](../probe-workspace/SKILL.md)に従う。

## 生成するファイル

| 生成先 | 内容 |
|---|---|
| `<dir>/schema.json` | シートの列構成。[schema](assets/schema.json)をメインが実体化する |
| `<dir>/coverage.json` | 網羅性の検索定義。[coverage](assets/coverage.json)をメインが実体化する |
| `<dir>/findings.md` | front matter とスコープと横断事項。[findings](assets/findings.md)をメインが実体化する |
| `<dir>/findings/<観点>.md` | 観点ごとの証跡。issue-investigator が書く |
| `<dir>/report.tsv` | 一覧の正本。メインが書く |
| `<dir>/issue-comment.md` | issue へ貼る報告文。[issue-comment](assets/issue-comment.md)をメインが実体化する |

prepare.py は `<dir>` と issue.json を用意する。

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

### 2. 契約の確定

issue.json の `body` と `comments` から、調査観点・スコープ・除外を読む。調査依頼には検索キーワードや分類が明記されていることが多い。それを次の2つの契約に落とす。

`<dir>/schema.json` にシートの列構成を書く。シートのURLが分かる場合は Google Drive MCP でヘッダ行を読み、列の順序と文字列をそのまま写す。同じシートに他プラットフォームの記入例があれば読み、粒度と書式の参考にする。MCP が使えない場合は列構成をユーザーに1回確認する。列の役割（`id` / `text` / `enum` / `effort`）は内容から決め、`enum` には許容値、`effort` には単位を書く。

`<dir>/coverage.json` に網羅性の検索定義を書く。issue に列挙された検索キーワードは、採用・不採用にかかわらず全て入れる。「調べたが該当なし」も成果物であり、後で網羅性の証跡になる。`scope` には検索対象のディレクトリを並べる。

### 3. 網羅性の計測

```bash
python3 <plugin-root>/scripts/count_hits.py <dir>
```

- 終了コード0: 件数が coverage.json に記録された。以降、成果物に書く件数はこの記録を引く
- 終了コード2・4: その issue を止め、`action` をユーザーに渡す

以降、手で数えた件数を成果物に書かない。数え直す必要が出たら coverage.json に検索定義を足して再実行する。

### 4. 調査

観点ごとに `issue-probe:issue-investigator` を1つのメッセージで並列起動する。Agent ツールの `subagent_type` は `issue-probe:issue-investigator`。各 prompt に書くのは次の3つだけで、issue の情報は investigator が `<dir>` から読む。

- 作業場所 `<dir>`
- 担当する観点と、その観点で書き出すファイル名 `findings/<観点slug>.md`
- 割り当てた項目番号の範囲（メインが nextItem から観点ごとに確保する）

観点の切り方は、issue が分類を持つならそれに従う。持たないなら「何を疑うか」で切る。ファイルを分けるのは1ファイル1ライターを守るためであり、観点が1つなら investigator も1体でよい。

investigator は `findings/<観点>.md` を書き、担当観点の項目一覧と、確定できなかったことだけを返す。全観点の応答とエージェントIDを受け取ってから手順5へ進む。

### 5. 一覧化

全観点の `findings/` を読み、[一覧セルの文体](../row-style/SKILL.md)に従って `<dir>/report.tsv` を作る。

- 1行目はヘッダで、schema.json の `columns` の `header` をその順序で並べる
- 項目は1事象1行にする。同じ原因で同じ直し方になるものはまとめ、件数を該当箇所の列に書く
- 番号は昇順に並べ、詰め直さない
- `<dir>/findings.md` に front matter・スコープと除外・観点と担当ファイルの対応・該当なしと確認した観点・確定できなかったことを書く。`nextItem` は最後に割り当てた番号より1大きい値にする

確定できなかったことは、何が未確定かと、誰が何をすれば確定するかの両方を書く。実機や通信の実測が要る場合はそう書く。この工程では実測しない。

### 6. 検査

```bash
python3 <plugin-root>/scripts/check_rows.py <dir>
```

- 終了コード0: 受け入れた。`info` の工数合計とリスク分布を控えて次へ進む
- 終了コード1: `problems` を全件、該当する観点の issue-investigator に `SendMessage` で渡す。investigator が `findings/` を直すので、report.tsv 側の修正はメインが行う
- 終了コード2: 契約か findings が読めない。`action` に従って直してから再実行する

差し戻し後は修正応答を待って再検査し、終了コード0まで繰り返す。

### 7. 報告

[issue-comment](assets/issue-comment.md)の構造で `<dir>/issue-comment.md` を書く。要約、改修計画、関係者確認をお願いしたい事項、本チケット対象外として切り出したものを持つ。

issue 番号ごとに次を伝える。

- report.tsv のパスと、シートへ貼る範囲（ヘッダを除く2行目以降、何行何列か）
- `info` の工数合計とリスク度の分布
- 確定できなかったことの一覧と、それぞれ誰が何をすれば確定するか
- issue-comment.md のパス

実測が必要な項目があれば、agent-device や charles-traffic のような実測用プラグインの利用を案内する。このスキルからは起動しない。

次の入口として再検証を示す。

```text
verify-items <番号1> <番号2>
withdraw-items <番号1>:3,7
```

## 規律

- 対象リポジトリへの書き込みは `.tmp/issue-probes/` 配下に置く
- シートへの貼り付けと issue への投稿は行わない。成果物は人が貼るための材料である
- 件数は count_hits.py の記録を引く。手で数えた値を書かない
- 項目番号は詰め直さない。削除は verdicts.md に評決を残す
