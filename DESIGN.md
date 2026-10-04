# Gurumoji のUI設計入口

日本語の録音を確かめ、発話を直し、分析の根拠へ戻り、研究結果を保存する仕事を支える。既存の紙色と濃緑を出発点とし、操作の意味・対象・版・保存状態が分かることを優先する。

このファイルは短い設計索引。実装の正本はコード・設定・テスト、設計判断の根拠はSoftware Vault。[AGENTS.md](AGENTS.md)の作業範囲を引き継ぎ、調査・検証はdotで進め、意味のある節目を記録する。全文献の読込は不要。

## 今回の仕事から読む

- 設計・改善: [設計契約](docs/program-vault/40-Design/ui-design-contract.md)の対象節と[実装計画](docs/program-vault/40-Design/ui-design-implementation-plan.md)の該当作業だけ
- 画面の現状: [画面とURL](docs/program-vault/20-Modules/ui-screens.md)から対象コードへ。分析のM0〜M7と未提供能力は[分析統合設計](docs/program-vault/40-Design/analysis-milestone-visualization-design.md)の導入範囲と現行実装を照合する
- 品質評価: [UI評価の役割](.agents/agents/gurumoji-ui-critic.md)、対象[シナリオ](docs/program-vault/50-Tests/ui-design-scenarios.md)、必要な[受入方法](docs/program-vault/50-Tests/ui-design-acceptance.md)
- 文献・参考UI・プロンプト: [設計知識索引](docs/program-vault/40-Design/ui-design-knowledge.md)で対象の資料・節だけを選ぶ

## 設計の判断

既存API・URL・ID・保存経路を再利用し、原文とAI案、人の編集・確認、現在データと固定runを区別する。欠測・未実行・失敗をゼロや成功として表示しない。表示上の完了と保存・Vault書出しの成否を分ける。具体的な互換条件と提案は設計契約に集約する。

色・寸法の実値は[既存CSS](src/gurumoji/static/style.css)と対象部品に戻る。ここに別のtoken表を作らない。ソース確認、実画面の観察、操作再現、人の利用評価を区別し、対象版と未実施を残す。短い修正に全面再設計を要求しない。

採用した判断と理由は[既存ADR](docs/program-vault/40-Design/decisions.md)、版・検証・次の作業は[運用引継ぎ](docs/program-vault/60-Operations/dot-cloud-development-handoff.md)へ。設計知識は必要時に取得する資料であり、モデル重みの学習、常駐エージェント、ファイル名による自動読込を意味しない。
