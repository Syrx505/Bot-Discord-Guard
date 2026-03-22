import discord
from discord.ext import commands
from discord import app_commands
import datetime
import os
import re
from flask import Flask
from threading import Thread

# --- VEB SERVER ---
app = Flask('')
@app.route('/')
def home(): return "Bot aktivdir!"
def run(): app.run(host='0.0.0.0', port=8080)
def keep_alive(): Thread(target=run).start()

# --- AYARLAR ---
TOKEN = os.environ.get('DISCORD_TOKEN') 
WHITELIST_USERS = [1402762600550240357, 1388969148683522270, 1218963997441921165] 

SPAM_LIMIT = 5
SPAM_SECONDS = 3

# Reklam linkləri üçün filtr (Regex)
LINK_PATTERN = re.compile(r"(discord\.gg|dsc\.gg|discord\.me|discord\.io|discord\.li|discord\.com/invite)")

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

@bot.tree.command(name="activate", description="Bütün sərt qorumaları işə salır.")
@app_commands.checks.has_permissions(administrator=True)
async def activate(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True) 
    bot.protection_active = True
    await interaction.followup.send("🛡️ Qoruma sistemi (Anti-Link daxil) aktiv edildi!")

@bot.event
async def on_guild_channel_delete(channel):
    if not bot.protection_active: return
    async for entry in channel.guild.audit_logs(action=discord.AuditLogAction.channel_delete, limit=1):
        user = entry.user
        if user.id in WHITELIST_USERS or user.id == bot.user.id or user.id == channel.guild.owner_id: return
        member = channel.guild.get_member(user.id)
        if member:
            try:
                await channel.guild.create_text_channel(name=channel.name, category=channel.category, position=channel.position)
                await member.edit(roles=[], reason="İzinsiz kanal silmə!")
                await member.timeout(datetime.timedelta(hours=1), reason="Nuke cəhdi")
                await channel.guild.system_channel.send(f"🚫 {user.mention} kanal sildiyi üçün yetkiləri alındı!")
            except: pass

@bot.event
async def on_message(message):
    if message.author.bot or not message.guild or not bot.protection_active: 
        return
    
    # --- 1. REKLAM LİNKİ QORUMASI ---
    if LINK_PATTERN.search(message.content.lower()):
        if message.author.id not in WHITELIST_USERS:
            try:
                await message.delete()
                await message.author.timeout(datetime.timedelta(minutes=10), reason="Reklam linki")
                await message.channel.send(f"🚫 {message.author.mention}, serverdə reklam etmək qadağandır! 10 dəqiqəlik susduruldun.", delete_after=10)
                return
            except: pass

    # --- 2. @EVERYONE / @HERE QORUMASI ---
    if "@everyone" in message.content or "@here" in message.content:
        if message.author.id not in WHITELIST_USERS:
            try:
                await message.delete()
                await message.author.edit(roles=[], reason="İzinsiz etiket cəhdi!")
                await message.author.timeout(datetime.timedelta(hours=1), reason="Everyone spamı")
                await message.channel.send(f"🚫 {message.author.mention} icazəsiz etiket atdığı üçün rolları alındı!")
                return
            except: pass

    # --- 3. ANTİ-SPAM (5 mesaj / 3 saniyə) ---
    user_id = message.author.id
    now = datetime.datetime.now()
    if user_id not in user_messages: user_messages[user_id] = []
    user_messages[user_id].append(now)
    user_messages[user_id] = [t for t in user_messages[user_id] if (now - t).total_seconds() < SPAM_SECONDS]

    if len(user_messages[user_id]) >= SPAM_LIMIT and user_id not in WHITELIST_USERS:
        try:
            await message.author.timeout(datetime.timedelta(minutes=10), reason="Sürətli spam")
            def is_spam_sender(m): return m.author.id == user_id
            await message.channel.purge(limit=15, check=is_spam_sender)
            await message.channel.send(f"🤫 {message.author.mention} spam etdiyi üçün susduruldu.", delete_after=10)
            user_messages[user_id] = []
        except: pass

    await bot.process_commands(message)

if __name__ == "__main__":
    keep_alive()  
    bot.run(TOKEN)
