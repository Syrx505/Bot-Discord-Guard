import discord
from discord.ext import commands
from discord import app_commands
import datetime
import os
import asyncio
from flask import Flask
from threading import Thread

# --- VEB SERVER (BOTU 7/24 OYAQ SAXLAMAQ ÜÇÜN) ---
app = Flask('')
@app.route('/')
def home(): return "Bot aktivdir!"
def run(): app.run(host='0.0.0.0', port=8080)
def keep_alive(): Thread(target=run).start()

# --- AYARLAR ---
TOKEN = os.environ.get('DISCORD_TOKEN') 

# 🛡️ WHITELIST (TOXUNULMAZLAR): Bu ID-si olanlara bot heç vaxt toxunmayacaq.
WHITELIST_USERS = [1402762600550240357, 1388969148683522270, 1218963997441921165] 

SPAM_LIMIT = 5
SPAM_SECONDS = 5

class MyBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.all()
        super().__init__(command_prefix="!", intents=intents)
        self.protection_active = False 

    async def setup_hook(self):
        await self.tree.sync()

bot = MyBot()
user_messages = {}

@bot.event
async def on_ready():
    print(f'--- {bot.user.name} QORUMA SİSTEMİ HAZIRDIR ---')

# --- 1. AKTİV ETMƏ KOMANDASI ---
@bot.tree.command(name="activate", description="Bütün sərt qorumaları işə salır.")
@app_commands.checks.has_permissions(administrator=True)
async def activate(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True) 
    bot.protection_active = True
    embed = discord.Embed(
        title="🛡️ Qoruma Sistemi Aktivdir",
        description="Artıq kimsə kanal silsə və ya @everyone atsa, bütün rolları alınacaq və Mute (Timeout) atılacaq!",
        color=discord.Color.red()
    )
    await interaction.followup.send(embed=embed)

# --- 2. ANTİ-NUKE (KANAL SİLMƏ QORUMASI) ---
@bot.event
async def on_guild_channel_delete(channel):
    if not bot.protection_active:
        return

    async for entry in channel.guild.audit_logs(action=discord.AuditLogAction.channel_delete, limit=1):
        user = entry.user
        
        # Whitelist, Bot və ya Server Sahibi yoxlaması
        if user.id == bot.user.id or user.id == channel.guild.owner_id or user.id in WHITELIST_USERS:
            return

        member = channel.guild.get_member(user.id)
        if member:
            try:
                # Kanalı dərhal bərpa et
                await channel.guild.create_text_channel(
                    name=channel.name, category=channel.category, position=channel.position
                )
                # Cəzalandır: Bütün rolları al + 1 saatlıq Mute
                await member.edit(roles=[], reason="İzinsiz kanal silmə!")
                await member.timeout(datetime.timedelta(hours=1), reason="Nuke cəhdi")
                
                await channel.guild.system_channel.send(f"🚫 **TƏHLÜKƏ SÖNDÜRÜLDÜ:** {user.mention} kanal sildiyi üçün yetkiləri alındı və susduruldu!")
            except Exception as e:
                print(f"Nuke qorumasında xəta: {e}")

# --- 3. ANTİ-EVERYONE & ANTİ-SPAM ---
@bot.event
async def on_message(message):
    if message.author.bot or not message.guild or not bot.protection_active: 
        return
    
    # --- @EVERYONE / @HERE QORUMASI ---
    if "@everyone" in message.content or "@here" in message.content:
        if message.author.id not in WHITELIST_USERS:
            try:
                await message.delete() # Mesajı sil
                await message.author.edit(roles=[], reason="İzinsiz etiket cəhdi!") # Rolları al
                await message.author.timeout(datetime.timedelta(hours=1), reason="Everyone spamı") # Mute at
                await message.channel.send(f"🚫 {message.author.mention} icazəsiz etiket atdığı üçün rolları alındı və susduruldu!")
            except: pass
            return

    # --- ANTİ-SPAM ---
    user_id = message.author.id
    now = datetime.datetime.now()
    if user_id not in user_messages: user_messages[user_id] = []
    user_messages[user_id].append(now)
    user_messages[user_id] = [t for t in user_messages[user_id] if (now - t).total_seconds() < SPAM_SECONDS]

    if len(user_messages[user_id]) > SPAM_LIMIT and user_id not in WHITELIST_USERS:
        try:
            await message.delete()
            await message.author.timeout(datetime.timedelta(minutes=10), reason="Spam")
            await message.channel.send(f"🤫 {message.author.mention} spam etdiyi üçün 10 dəqiqəlik susduruldu.", delete_after=5)
        except: pass

    await bot.process_commands(message)

if __name__ == "__main__":
    keep_alive()  
    bot.run(TOKEN)
