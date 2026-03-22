import discord
from discord.ext import commands
from discord import app_commands
import datetime
import asyncio
import os
from flask import Flask
from threading import Thread

# --- 24/7 AKTİV SAXLAMAQ ÜÇÜN VEB SERVER ---
app = Flask('')

@app.route('/')
def home():
    return "Bot aktivdir!"

def run():
    app.run(host='0.0.0.0', port=8080)

def keep_alive():
    t = Thread(target=run)
    t.start()

# --- AYARLAR ---
# Tokeni Render-in 'Environment Variables' hissəsindən götürür
TOKEN = os.environ.get('DISCORD_TOKEN') 

SPAM_LIMIT = 5          
SPAM_SECONDS = 5
NUKE_LIMIT = 3          
NUKE_SECONDS = 10

class MyBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.all()
        super().__init__(command_prefix="!", intents=intents)
        self.protection_active = False 

    async def setup_hook(self):
        await self.tree.sync()
        print("Slash komandaları (/) sinxronizasiya olundu.")

bot = MyBot()

user_messages = {}
nuke_tracker = {}

@bot.event
async def on_ready():
    print(f'--- {bot.user.name} AKTİVDİR ---')

# --- 1. AKTİV ETMƏ KOMANDASI ---
@bot.tree.command(name="activate", description="Bütün qoruma sistemlərini işə salır.")
@app_commands.checks.has_permissions(administrator=True)
async def activate(interaction: discord.Interaction):
    bot.protection_active = True
    embed = discord.Embed(
        title="🛡️ Qoruma Sistemi Aktivləşdirildi",
        description="Artıq server Nuke, Spam və Everyone hücumlarından qorunur.",
        color=discord.Color.green()
    )
    await interaction.response.send_message(embed=embed)

# --- 2. KANAL QORUMASI VƏ ANTİ-NUKE ---
@bot.event
async def on_guild_channel_delete(channel):
    if not bot.protection_active:
        return

    try:
        new_channel = await channel.guild.create_text_channel(
            name=channel.name,
            category=channel.category,
            position=channel.position,
            topic="🛡️ Bu kanal avtomatik bərpa olundu."
        )
    except:
        pass

    async for entry in channel.guild.audit_logs(action=discord.AuditLogAction.channel_delete, limit=1):
        user = entry.user
        if user.id == bot.user.id: return

        now = datetime.datetime.now()
        if user.id not in nuke_tracker:
            nuke_tracker[user.id] = []
        
        nuke_tracker[user.id].append(now)
        nuke_tracker[user.id] = [t for t in nuke_tracker[user.id] if (now - t).total_seconds() < NUKE_SECONDS]

        if len(nuke_tracker[user.id]) >= NUKE_LIMIT:
            try:
                await channel.guild.ban(user, reason="ANTİ-NUKE: Kütləvi kanal silmə cəhdi!")
                await new_channel.send(f"🚫 {user.mention} nuke atmağa çalışdığı üçün banlandı!")
            except:
                pass

# --- 3. ANTİ-EVERYONE VƏ ANTİ-SPAM ---
@bot.event
async def on_message(message):
    if message.author.bot or not message.guild or not bot.protection_active:
        return

    if "@everyone" in message.content or "@here" in message.content:
        if not message.author.guild_permissions.mention_everyone:
            await message.delete()
            try:
                await message.author.ban(reason="İzinsiz @everyone spamı!")
            except:
                pass
            return

    user_id = message.author.id
    now = datetime.datetime.now()
    if user_id not in user_messages:
        user_messages[user_id] = []
    
    user_messages[user_id].append(now)
    user_messages[user_id] = [t for t in user_messages[user_id] if (now - t).total_seconds() < SPAM_SECONDS]

    if len(user_messages[user_id]) > SPAM_LIMIT:
        await message.delete()
        try:
            await message.author.timeout(datetime.timedelta(minutes=10), reason="Spam")
            await message.channel.send(f"🤫 {message.author.mention} susduruldu.", delete_after=5)
        except:
            pass

    await bot.process_commands(message)

# --- BOTU BAŞLAT ---
if __name__ == "__main__":
    keep_alive() # Veb serveri işə salır
    bot.run(TOKEN) # Botu işə salır