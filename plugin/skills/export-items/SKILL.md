---
name: export-items
description: findings.md の項目から、シートへ貼れる1枚の paste.tsv を導出する。
argument-hint: <issue番号1, issue番号2...>
disable-model-invocation: true
compatibility: python3 3.10以上、git
---

# シート転記用の書き出し

`.tmp/issue-probes/<番号>/findings.md` の項目を、共有スプレッドシートへ貼れる1枚の TSV として `<dir>/paste.tsv` に書き出す。

paste.tsv は findings.md の導出物である。毎回作り直されるので、直すのは findings.md のほうである。

成果物の正本と編集責任は[調査成果物の扱い](../probe-workspace/SKILL.md)に従う。

## 手順

### 1. 検査

依頼文から issue の番号を取る。受け取れなければ質問し、回答を得てから進める。issue 番号ごとに実行する。

[check_items.py](../../scripts/check_items.py)をPython 3で実行し、`<dir>`を渡す。

- 終了コード0: `info` の工数合計とリスク度の分布を控えて書き出しへ進む
- 終了コード1: `problems` を解消してから書き出す。整合していない一覧を貼ると、シート側の行を後から直すことになる
- 終了コード2: `action` に従って直してから再実行する

`info` に「件数の計測時のコミットが調査時点と違います」が出た場合は、`count_hits.py` を再実行し、findings.md の網羅性の件数を記録に合わせてから書き出す。

### 2. 書き出し

[export_items.py](../../scripts/export_items.py)をPython 3で実行し、`<dir>`を渡す。

- 終了コード0: `path` に paste.tsv が書かれた
- 終了コード1: `problems` を findings.md 側で解消して再実行する。前回の paste.tsv があれば削除される。古い書き出しは現行のものと見分けが付かないため残さない
- 終了コード2: `action` に従って直してから再実行する

### 3. 報告

issue 番号ごとに次を伝える。

- paste.tsv のパスと、シートへ貼る範囲（ヘッダ行を除く2行目以降、`rows` 行 `columns` 列）
- 応答の `items` から組み立てた俯瞰の表。列は番号・リスク度・項目名・工数の4つにする
- 検査で控えた工数合計とリスク度の分布
- 転記済みの行がある場合は、同じ番号の行を上書きする対応になること

## 規律

- 書き込みは `<dir>/paste.tsv` だけ。findings.md には書かない
- シートへの貼り付けは行わない。paste.tsv は人が貼るための材料である
- 列構成を変える依頼を受けても、ワークスペースに列定義を作らない。列は `scripts/columns.py` が持つ1箇所である
