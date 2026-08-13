# issue-probe

GitHub 経由でインストールする、Claude Code 向けの調査ワークフロープラグイン。GitHub issue に書かれた調査依頼を読み、網羅的に調べ、共有スプレッドシートへ貼るだけの一覧と issue へ貼るコメント草案までを作る。調査対象コードのリポジトリ直下 `.tmp/issue-probes/` に置く成果物で各工程が連携する。

リポジトリ直下がマーケットプレイスルート、`plugin/` がプラグインルート。ユーザーと対話する入口は skills、観点ごとの調査と反証は agents、共有CLIは `plugin/scripts/` が担う。

外向きの書き込みは行わない。シートへの貼り付けと issue への投稿は人が行う。

## ワークフロー

```text
probe-issue ──→ findings/ + report.tsv + issue-comment.md ──→ 人がシートへ転記・issueへ投稿
                    │
                    ├── verify-items（任意）──→ 各成果物の更新 + verdicts.md
                    └── withdraw-items ────────→ 指定項目の取り下げ
```

verify-items は、一覧の各項目を証拠の再現と前提への反証によって疑い直す任意工程である。件数主張は必ず数え直し、リスク度は判定基準と突き合わせ、確定できないものは「誰が何をすれば確定するか」まで書いて残す。

## コンポーネント

| 種別 | 名前 | 役割 |
|---|---|---|
| 入口スキル | probe-issue | issue から調査観点とスコープを読み、列構成と検索定義を確定し、観点ごとに調査を並列実行して report.tsv と issue-comment.md を作る |
| 入口スキル | verify-items | 既存項目を反証し、評決を各成果物へ反映して verdicts.md に経緯を残す |
| 入口スキル | withdraw-items | `issue番号:No` で指定した項目を、番号を詰めずに取り下げる |
| 判断スキル | probe-workspace | `.tmp/issue-probes/` の構造、正本、ID と鮮度、方針の優先順位を定める |
| 判断スキル | row-style | シートのセルに載る日本語の規約を定める |
| エージェント | issue-investigator | 担当観点を調査し、証跡ファイルを書く |
| エージェント | item-verifier | 担当項目を反証し、評決ファイルを書く |

probe-workspace と row-style は工程ではない。生成済み成果物について質問されたときや、セルの文面を扱うときに、入口スキルから独立して使われる。

## 成果物

report.tsv と findings が異なる責任の正本である。

- `report.tsv`: シートに載る内容そのものの正本。1列目 No. が項目の不変ID
- `findings.md` / `findings/<観点>.md`: 根拠の正本。スコープと除外、各項目の証跡、該当なしと確認した観点、確定できなかったこと
- `issue-comment.md`: issue へ貼る対外報告文の正本。要約・改修計画・関係者確認事項
- `schema.json`: シートの列構成。report.tsv の検証契約
- `coverage.json`: 網羅性の検索定義と実測件数
- `verdicts.md`: 反証検証の評決と変更の追記記録
- `issue.json`: 調査依頼の出どころ
- `policy.md`: 調査方針（任意）

```text
.tmp/
├── .gitignore
└── issue-probes/
    ├── policy.md
    └── <issue番号>/
        ├── issue.json
        ├── schema.json
        ├── coverage.json
        ├── policy.md
        ├── findings.md
        ├── findings/<観点>.md
        ├── report.tsv
        ├── verdicts.md
        └── issue-comment.md
```

No. は論理的な項目の不変IDである。更新でも削除でも番号を詰め直さず、欠番は再利用しない。シートは一度貼ると行位置が固定されるため、詰め直しは転記済みシートとの対応を壊す。

## 設計

- 入口スキルはユーザーだけが起動する。どの工程もGitHubやスプレッドシートへ書き込まない
- 件数はスクリプトが測る。`count_hits.py` が記録した件数を成果物が引くことで、手で数えた値が独り歩きしない
- 転記事故は検査で止める。`check_rows.py` がセル内のタブ・改行、列数不一致、ID の重複を受け入れ前に検出する
- 確定できないことは構造化して残す。実測が要る項目は「誰が何をすれば確定するか」まで書き、実測自体は別プラグインに委ねる

## 開発

[uv](https://docs.astral.sh/uv/) を使う。`make fix` で整形と自動修正、`make lint` で ruff と mypy、`make test` で pytest を実行する。`make fix` を `make lint` より先に走らせる。詳細は [CONTRIBUTING.md](CONTRIBUTING.md) を参照。

## インストール

```bash
claude plugin marketplace add akitorahayashi/issue-probe
claude plugin install issue-probe@issue-probe
```

ローカル開発では `claude --plugin-dir ./plugin` でそのセッションだけプラグインルートを読み込める。
