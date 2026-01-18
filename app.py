import discord
from discord.ext import commands
import os
import time

# ===== 設定 =====
TOKEN = os.environ.get("DISCORD_TOKEN")
LOG_CHANNEL_ID = 1263561413851611278  # ログを流すチャンネルID

if not TOKEN:
    print("⚠️ DISCORD_TOKEN が設定されていません")
    exit(1)

# ===== Intents 設定 =====
intents = discord.Intents.default()
intents.message_content = True
intents.members = True  # タイムアウトに必要

bot = commands.Bot(command_prefix="!", intents=intents)

# ===== スパム判定用パラメータ =====
TIME_WINDOW = 10        # 秒
CHANNEL_LIMIT = 3       # このチャンネル数以上でスパム
TIMEOUT_MINUTES = 1440  # タイムアウト時間（分）

# ユーザーごとの発言履歴
# user_id : [(channel_id, timestamp, message_id)]
user_logs = {}

# ===== メッセージ受信イベント =====
@bot.event
async def on_message(message: discord.Message):
    # Bot の発言や DM は無視
    if message.author.bot or not message.guild:
        return

    user_id = message.author.id
    now = time.time()
    logs = user_logs.get(user_id, [])

    # 古いログを削除
    logs = [(ch, ts, mid) for ch, ts, mid in logs if now - ts <= TIME_WINDOW]

    # 今回のメッセージを追加
    logs.append((message.channel.id, now, message.id))
    user_logs[user_id] = logs

    # 異なるチャンネル数をカウント
    unique_channels = {ch for ch, _, _ in logs}

    if len(unique_channels) >= CHANNEL_LIMIT:
        try:
            # ① メッセージ削除
            for ch_id, _, msg_id in logs:
                channel = message.guild.get_channel(ch_id)
                if channel:
                    try:
                        msg = await channel.fetch_message(msg_id)
                        await msg.delete()
                    except discord.NotFound:
                        pass

            # ② ユーザーをタイムアウト
            member = message.guild.get_member(user_id)
            if member:
                # aware datetime にするため discord.utils.utcnow() を使用
                await member.timeout(
                    discord.utils.utcnow() + discord.timedelta(minutes=TIMEOUT_MINUTES),
                    reason="短時間で複数チャンネルに投稿（スパム）"
                )

            # ③ ログ通知
            log_channel = message.guild.get_channel(LOG_CHANNEL_ID)
            if log_channel:
                await log_channel.send(
                    f"{message.author.mention} が短時間で複数チャンネルに投稿したため、"
                    f"{TIMEOUT_MINUTES}分間タイムアウトされました。"
                )

            # ④ 発言履歴リセット
            user_logs.pop(user_id, None)

        except Exception as e:
            print(f"スパム処理エラー: {e}")

    # 他のコマンド処理
    await bot.process_commands(message)

# ===== Bot 起動 =====
bot.run(TOKEN)
