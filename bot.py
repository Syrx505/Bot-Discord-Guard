import discord
from discord.ext import commands
from discord import app_commands
import datetime
import asyncio
import os
from flask import Flask
from threading import Thread

# --- VEB SERVER (BOTU OYAQ SAXLAMAQ ÜÇÜN) ---
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
TOKEN = os.environ.get('DISCORD_TOKEN') 

SPAM_LIMIT = 5          
SPAM_SECONDS = 5

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

@bot.event
async def on_ready():
    print(f'--- {bot.user.name} AKTİVDİR ---')

# --- 1. AKTİV ETMƏ KOMANDASI ---
@bot.tree.command(name="activate", description="Bütün qoruma sistemlərini işə salır.")
@app_commands.checks.has_permissions(administrator=True)
async def activate(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True) 
    bot.protection_active = True
    
    embed = discord.Embed(
        title="🛡️ Qoruma Sistemi Aktivləşdirildi",
        description="Artıq kimsə 1 kanal belə silsə, bütün rolları dərhal alınacaq!",
        color=discord.Color.green()
    )
    await interaction.followup.send(embed=embed)

# --- 2. KANAL SİLMƏ QORUMASI (DƏRHAL YETKİ ALMA) ---
@bot.event
async def on_guild_channel_delete(channel):
    if not bot.protection_active:
        return

    # Kanalı bərpa etməyə çalışırıq
    try:
        await channel.guild.create_text_channel(
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
        
        # Bot özü silsə və ya Server Sahibi silsə heç nə etmə
        if user.id == bot.user.id or user.id == channel.guild.owner_id:
            return

        # Üzvü tapırıq və bütün rollarını silirik (Permission-ları bağlamaq üçün)
        member = channel.guild.get_member(user.id)
        if member:
            try:
                # Rolları silirik (İstisna: @everyone silinə bilməz)
                await member.edit(roles=[], reason="ANTİ-NUKE: İzinsiz kanal silmə cəhdi!")
                
                # Həm də 1 saatlıq timeout atırıq
                await member.timeout(datetime.timedelta(hours=1), reason="Kanal silmə cəhdi")
                
                # Xəbərdarlıq mesajı
                msg = f"🚫 **DİQQƏT:** {user.mention} kanal sildiyi üçün bütün yetkiləri dərhal alındı!"
                await channel.guild.system_channel.send(msg)
            except Exception as e:
                print(f"Yetki alınarkən xəta: {e}")

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
                await message.author.edit(roles=[], reason="İzinsiz @everyone spamı!")
                await message.channel.send(f"🚫 {message.author.mention} everyone etiketlədiyi üçün yetkiləri alındı!")
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
            await message.channel.send(f"🤫 {message.author.mention} spam etdiyi üçün susduruldu.", delete_after=5)
        except:
            pass

    await bot.process_commands(message)

# --- BOTU BAŞLAT ---
if __name__ == "__main__":
    keep_alive()  
    bot.run(TOKEN)
