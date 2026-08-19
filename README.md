# issue-probe

GitHub 経由でインストールする、Claude Code 向けの調査ワークフロープラグイン。GitHub issue に書かれた調査依頼を読み、網羅的に調べ、一覧と根拠を1枚に持つ findings.md、共有スプレッドシートへ貼るだけの TSV、issue へ貼るコメント草案までを作る。調査対象コードのリポジトリ直下 `.tmp/issue-probes/` に置く成果物で各工程が連携する。

リポジトリ直下がマーケットプレイスルート、`plugin/` がプラグインルート。ユーザーと対話する入口は skills、観点ごとの調査と反証は agents、共有CLIは `plugin/scripts/` が担う。

外向きの書き込みは行わない。シートへの貼り付けと issue への投稿は人が行う。

## ワークフロー

```text
probe-issue ──→ findings.md + issue-comment.md ──→ export-items ──→ paste.tsv ──→ 人がシートへ転記
                    │
                    ├── verify-items（任意）──→ findings.md の更新 + verdicts.md
                    └── withdraw-items ────────→ 指定項目の取り下げ
```

verify-items は、一覧の各項目を証拠の再現と前提への反証によって疑い直す任意工程である。件数主張は必ず数え直し、リスク度は判定基準と突き合わせ、確定できないものは「誰が何をすれば確定するか」まで書いて残す。

## コンポーネント

| 種別 | 名前 | 役割 |
|---|---|---|
| 入口スキル | probe-issue | issue から調査観点とスコープを読み、検索定義を確定し、観点ごとに調査を並列実行して findings.md と issue-comment.md を作る |
| 入口スキル | verify-items | 既存項目を反証し、評決を findings.md へ反映して verdicts.md に経緯を残す |
| 入口スキル | withdraw-items | `issue番号:No` で指定した項目を、番号を詰めずに取り下げる |
| 入口スキル | export-items | findings.md からシートへ貼れる paste.tsv を導出する |
| 判断スキル | probe-workspace | `.tmp/issue-probes/` の構造、正本、findings.md の見出し規約、ID と鮮度、方針の優先順位を定める |
| 判断スキル | row-style | シートのセルに載る日本語の規約を定める |
| エージェント | issue-investigator | 担当観点を調査し、項目の節を報告する |
| エージェント | item-verifier | 担当項目を反証し、評決を報告する |

probe-workspace と row-style は工程ではない。生成済み成果物について質問されたときや、フィールドの文面を扱うときに、入口スキルから独立して使われる。

エージェントはファイルを書かない。成果物を書くのは入口スキルのメインで、これは1ファイル1ライターを保つためである。並列の単位が観点であるため、単一のライターになれるのはメインだけになる。

## 成果物

findings.md が唯一の正本である。1つの項目が1つの節で、シートに載る文面と、その主張がなぜ書けるかが同じ場所にある。

```markdown
### 2 [高] 番組表のチャンネルID取得

- 該当箇所: RealTimeGuideViewController.swift L318,329,355（3箇所）
- 本来の経路: 型付きプロパティ経由の共通取得処理
- 現状: 辞書バックのモデルから文字列キーで取得し、強制キャストしている
- 想定される事象: APIがidをnullや欠落で返すと番組表表示時に即クラッシュする
- 影響範囲:
  - RealTimeGuideViewController.swift チャンネルID取得（L318,329,355） → nil考慮の共通取得へ3箇所一括で置換する
  - 番組表画面 → チャンネル一覧・番組セル描画・日付切替の横断確認を行う
- 工数: 4h（設計: 2h/ 実装: 2h）
- 備考: なし

#### 根拠

<証跡の散文。シートには出ない>
```

見出しの番号・リスク度・項目名と、7つのフィールドが、そのままシートの10列になる。長い列挙はネストした箇条のまま書き、`1. … 2. …` への畳み込みは export-items が行う。

- `findings.md`: 一覧と根拠の正本。front matter・スコープと除外・網羅性・項目・該当なしと確認した観点・確定できなかったこと
- `paste.tsv`: findings.md の導出物。export-items が実行のたびに作り直す
- `issue-comment.md`: issue へ貼る対外報告文の正本。要約・改修計画・関係者確認事項
- `coverage.json`: 網羅性の検索定義と実測件数
- `verdicts.md`: 反証検証と取り下げの追記記録
- `issue.json`: 調査依頼の出どころ
- `policy.md`: 調査方針（任意）

```text
.tmp/
└── issue-probes/
    ├── policy.md
    └── <issue番号>/
        ├── issue.json
        ├── coverage.json
        ├── policy.md
        ├── findings.md
        ├── verdicts.md
        ├── issue-comment.md
        └── paste.tsv
```

項目番号は論理的な項目の不変IDである。更新でも取り下げでも番号を詰め直さず、欠番は再利用しない。シートは一度貼ると行位置が固定されるため、詰め直しは転記済みシートとの対応を壊す。

## 設計

- 入口スキルはユーザーだけが起動する。どの工程もGitHubやスプレッドシートへ書き込まない
- 一覧と根拠を同じ節に置く。別ファイルに分けると同じ主張を2つの語り口で書くことになり、更新が片側にしか届かない
- シートの形は導出する。読みやすい形で書き、貼れる形は `export_items.py` が作る
- 列構成はプラグインの `scripts/columns.py` が1箇所で持つ。ワークスペースごとに宣言しない
- 件数はスクリプトが測る。`count_hits.py` が記録した件数を成果物が引くことで、手で数えた値が独り歩きしない
- 転記事故は検査で止める。`check_items.py` が値に混じったタブや改行、フィールドの欠落、リスク度の語彙外、番号の重複を書き出し前に検出する
- 番号が消えても主張は残る。取り下げは節を消すが、欠番には delete の評決が要る
- 確定できないことは構造化して残す。実測が要る項目は「誰が何をすれば確定するか」まで書き、実測自体は別プラグインに委ねる

## 開発

[uv](https://docs.astral.sh/uv/) を使う。`make fix` で整形と自動修正、`make lint` で ruff と mypy、`make test` で pytest を実行する。`make fix` を `make lint` より先に走らせる。詳細は [CONTRIBUTING.md](CONTRIBUTING.md) を参照。

## インストール

```bash
claude plugin marketplace add akitorahayashi/issue-probe
claude plugin install issue-probe@issue-probe
```

ローカル開発では `claude --plugin-dir ./plugin` でそのセッションだけプラグインルートを読み込める。
