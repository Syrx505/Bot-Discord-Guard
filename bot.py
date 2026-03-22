import discord
from discord.ext import commands
from discord import app_commands
import datetime
import asyncio
import os
from flask import Flask
from threading import Thread

# --- 24/7 AKTİV SAXLAMAQ ÜÇÜN VEB SERVER (FLASK) ---
app = Flask('')

@app.route('/')
def home():
    return "Bot aktivdir!"

def run():
    # Render üçün port 8080 olaraq qalmalıdır
    app.run(host='0.0.0.0', port=8080)

def keep_alive():
    t = Thread(target=run)
    t.start()

# --- AYARLAR ---
# Tokeni Render-in 'Environment Variables' hissəsindən götürürük
TOKEN = os.environ.get('DISCORD_TOKEN') 

SPAM_LIMIT = 5          # 5 saniyədə neçə mesaj?
SPAM_SECONDS = 5
NUKE_LIMIT = 3          # 10 saniyədə neçə kanal silinə bilər?
NUKE_SECONDS = 10

class MyBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.all()
        super().__init__(command_prefix="!", intents=intents)
        self.protection_active = False 

    async def setup_hook(self):
        # Slash komandalarını sinxronizasiya edirik
        await self.tree.sync()
        print("Slash komandaları (/) sinxronizasiya olundu.")

bot = MyBot()

# Məlumatları yadda saxlamaq üçün lüğətlər
user_messages = {}
nuke_tracker = {}

@bot.event
async def on_ready():
    print(f'--- {bot.user.name} AKTİVDİR ---')

# --- 1. AKTİV ETMƏ KOMANDASI (Yalnız Adminlər) ---
@bot.tree.command(name="activate", description="Bütün qoruma sistemlərini işə salır.")
@app_commands.checks.has_permissions(administrator=True)
async def activate(interaction: discord.Interaction):
    # 'Uygulama yanıt vermedi' xətasının qarşısını almaq üçün defer edirik
    await interaction.response.defer(ephemeral=True) 
    
    bot.protection_active = True
    
    embed = discord.Embed(
        title="🛡️ Qoruma Sistemi Aktivləşdirildi",
        description="Artıq server Nuke, Spam və Everyone hücumlarından qorunur.",
        color=discord.Color.green()
    )
    
    # Defer istifadə etdiyimiz üçün followup.send yazırıq
    await interaction.followup.send(embed=embed)

# --- 2. KANAL QORUMASI VƏ ANTİ-NUKE ---
@bot.event
async def on_guild_channel_delete(channel):
    if not bot.protection_active:
        return

    # Kanalları dərhal bərpa et
    try:
        new_channel = await channel.guild.create_text_channel(
            name=channel.name,
            category=channel.category,
            position=channel.position,
            topic="🛡️ Bu kanal avtomatik bərpa olundu."
        )
    except:
        pass

    # Audit loglarından siləni tapırıq
    async for entry in channel.guild.audit_logs(action=discord.AuditLogAction.channel_delete, limit=1):
        user = entry.user
        if user.id == bot.user.id: return

        now = datetime.datetime.now()
        if user.id not in nuke_tracker:
            nuke_tracker[user.id] = []
        
        nuke_tracker[user.id].append(now)
        # Köhnə qeydləri təmizlə
        nuke_tracker[user.id] = [t for t in nuke_tracker[user.id] if (now - t).total_seconds() < NUKE_SECONDS]

        # Limit aşılarsa banla
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

    # Anti-Everyone/Here
    if "@everyone" in message.content or "@here" in message.content:
        if not message.author.guild_permissions.mention_everyone:
            await message.delete()
            try:
                await message.author.ban(reason="İzinsiz @everyone spamı!")
                await message.channel.send(f"🚫 {message.author.mention} everyone etiketlədiyi üçün banlandı!")
            except:
                pass
            return

    # Anti-Spam
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
            await message.channel.send(f"🤫 {message.author.mention} çox sürətli yazdığı üçün 10 dəqiqəlik susduruldu.", delete_after=5)
        except:
            pass

    await bot.process_commands(message)

# --- BOTU BAŞLAT ---
if __name__ == "__main__":
    keep_alive()  # Flask serveri işə salır
    bot.run(TOKEN) # Botu işə salır
