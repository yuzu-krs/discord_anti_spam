import discord
from discord.ext import commands
import time

# ===== Intent設定 =====
# メッセージ内容取得 & メンバー操作（timeout）に必要
intents = discord.Intents.default()
intents.message_content = True
intents.members = True

# Bot本体
bot = commands.Bot(command_prefix="!", intents=intents)

# ===== スパム判定用パラメータ =====
TIME_WINDOW = 10        # 何秒以内を監視するか
CHANNEL_LIMIT = 3       # 何チャンネル以上でスパム扱い
TIMEOUT_MINUTES = 1440    # タイムアウト時間（分）

# user_id : [(channel_id, timestamp, message_id)]
# ユーザーごとの発言履歴を保存
user_logs = {}

@bot.event
async def on_message(message: discord.Message):
    # Botの発言・DMは無視
    if message.author.bot or not message.guild:
        return

    user_id = message.author.id          # 発言者のID
    now = time.time()                    # 現在時刻（秒）

    # そのユーザーの過去ログ取得（なければ空）
    logs = user_logs.get(user_id, [])

    # ===== 時間外のログを削除 =====
    # TIME_WINDOW 秒より古い発言はカウントしない
    logs = [
        (ch, ts, mid)
        for ch, ts, mid in logs
        if now - ts <= TIME_WINDOW
    ]

    # ===== 今回のメッセージを記録 =====
    logs.append((
        message.channel.id,  # どのチャンネルか
        now,                  # いつ送ったか
        message.id            # どのメッセージか
    ))
    user_logs[user_id] = logs

    # ===== 異なるチャンネル数を計算 =====
    # setを使うことで同じチャンネルは1回として数える
    unique_channels = {ch for ch, _, _ in logs}

    # ===== スパム判定 =====
    # 短時間に複数チャンネルへ投稿したらアウト
    if len(unique_channels) >= CHANNEL_LIMIT:
        try:
            # ===== 記録されたメッセージを全削除 =====
            for ch_id, _, msg_id in logs:
                channel = message.guild.get_channel(ch_id)
                if channel:
                    try:
                        msg = await channel.fetch_message(msg_id)
                        await msg.delete()
                    except discord.NotFound:
                        # 既に消されている場合は無視
                        pass

            # ===== ユーザーをタイムアウト =====
            member = message.guild.get_member(user_id)
            if member:
                await member.timeout(
                    discord.utils.utcnow()
                    + discord.timedelta(minutes=TIMEOUT_MINUTES),
                    reason="短時間で複数チャンネルに投稿（スパム）"
                )

            # ログをリセット（連続処罰防止）
            user_logs.pop(user_id, None)

        except Exception as e:
            print(e)

    # コマンド処理（他の !command を使う場合に必要）
    await bot.process_commands(message)
