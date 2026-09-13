---
note_id: method-outline
method_id: outline
method_version: text-analysis-store-2
algorithm_version: ai-finishing-3
execution_kind: builtin
title: 議題・アウトライン
status: current
tags: [gurumoji/analysis, gurumoji/generative-ai, gurumoji/orchestrator]
---

# 議題・アウトライン（`outline`）

## 実装契約

全発話をバッチ化してAIへ渡し、議題、時刻、箇条書き、発話根拠を持つアウトラインを作る。Obsidianでは研究者が全体アウトラインを編集できる。根拠IDに対応する本文・話者・時刻が現行発話と異なれば、アウトラインを`stale`として扱う。

## オーケストレーターの判断

- アウトラインは会話ナビゲーションと編集用の中間成果物で、分析テーマや議事録の最終版ではない。
- バッチ境界を跨ぐ議題、時刻順序、根拠IDの完全性を検証する。空のセクション、無根拠の箇条書き、同じIDへの過剰な依存を失敗・要確認にする。
- 研究者が手編集したアウトラインを再生成で上書きしない。生成元、編集者、版、反映状態を分けて保存する。

## 言えないこと

アウトラインの章立てや箇条書きの順序は、研究テーマの真の構造、発話の重要度、合意を意味しない。

## 査読文献との関係

アウトライン生成そのものに対応する固定の査読済み分析法はない。[Gilardi et al. (2023)](https://doi.org/10.1073/pnas.2305016120)のようなLLM注釈評価は補助利用の可能性を示すに留まる。人の編集、根拠照合、版管理がこの機能の妥当性の中心である。
