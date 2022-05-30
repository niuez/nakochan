## voicevox(coeiroink)を使った読み上げbot

- 自分のPCでvoicevoxのサーバを建てつつ、`ext_discord.py`を実行して使います

## 機能

- `>con` コマンドを入力した人がいるvcに接続
- `>dc` 切断
- `>add <before> <after>` beforeをafterと読みます
- `>rem <before>` 辞書に登録したbeforeを削除
- "1時に寝る"のような人に1時に催促、1時半に警告を入れる
    - 条件: サーバニックネームが"\d+に"と始まる人が同じvcに入っている
- なこちゃんがひとりになったらおやすみします
- 読み上げ
