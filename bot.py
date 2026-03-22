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
    print(f'--- {bot.user.name} SUPER DEFENDER AKTİVDİR ---')

@bot.tree.command(name="activate", description="Bütün qorumaları (Anti-Perm daxil) aktiv edir.")
@app_commands.checks.has_permissions(administrator=True)
async def activate(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True) 
    bot.protection_active = True
    await interaction.followup.send("🛡️ Server Tam Qorumaya Alındı: Kanal/Rol/Yetki dəyişmək qadağandır!")

# --- 1. KANAL DƏYİŞİKLİYİ QORUMASI (Anti-Channel Update) ---
@bot.event
async def on_guild_channel_update(before, after):
    if not bot.protection_active: return
    async for entry in after.guild.audit_logs(action=discord.AuditLogAction.channel_update, limit=1):
        user = entry.user
        if user.id in WHITELIST_USERS or user.id == bot.user.id: return
        
        member = after.guild.get_member(user.id)
        if member:
            try:
                # Dəyişikliyi geri qaytarmaq çətin olduğu üçün birbaşa adamı cəzalandırırıq
                await member.edit(roles=[], reason="İzinsiz kanal ayarı dəyişmə!")
                await member.timeout(datetime.timedelta(hours=1))
                await after.guild.system_channel.send(f"🚫 {user.mention} kanal ayarlarını dəyişdiyi üçün yetkiləri alındı!")
            except: pass

# --- 2. KANAL SİLMƏ QORUMASI ---
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
                await member.timeout(datetime.timedelta(hours=1))
                await channel.guild.system_channel.send(f"🚫 {user.mention} kanal sildiyi üçün yetkiləri alındı!")
            except: pass

# --- 3. YETKİ (ROL) VERMƏ QORUMASI (Anti-Member Update) ---
@bot.event
async def on_member_update(before, after):
    if not bot.protection_active: return
    # Əgər rollar dəyişibsə
    if len(before.roles) != len(after.roles):
        async for entry in after.guild.audit_logs(action=discord.AuditLogAction.member_role_update, limit=1):
            user = entry.user
            if user.id in WHITELIST_USERS or user.id == bot.user.id: return
            
            executor = after.guild.get_member(user.id)
            if executor:
                try:
                    # Rolu verən adamın rollarını al
                    await executor.edit(roles=[], reason="İzinsiz rol dəyişikliyi etmək!")
                    # Verilən rolu geri al (after üzvündən)
                    await after.edit(roles=before.roles, reason="Yetkisiz verilən rol geri alındı.")
                    await after.guild.system_channel.send(f"🚫 {user.mention} izinsiz rol verdiyi/aldığı üçün yetkiləri alındı!")
                except: pass

# --- 4. ROL SİLMƏ/YARATMA QORUMASI ---
@bot.event
async def on_guild_role_create(role):
    if not bot.protection_active: return
    async for entry in role.guild.audit_logs(action=discord.AuditLogAction.role_create, limit=1):
        user = entry.user
        if user.id in WHITELIST_USERS or user.id == bot.user.id: return
        member = role.guild.get_member(user.id)
        if member:
            await role.delete()
            await member.edit(roles=[])
            await role.guild.system_channel.send(f"🚫 {user.mention} rol yaratdığı üçün yetkiləri alındı!")

# --- 5. MESAJ QORUMALARI (LINK, EVERYONE, SPAM) ---
@bot.event
async def on_message(message):
    if message.author.bot or not message.guild or not bot.protection_active: return
    
    # Anti-Link
    if LINK_PATTERN.search(message.content.lower()) and message.author.id not in WHITELIST_USERS:
        try:
            await message.delete()
            await message.author.timeout(datetime.timedelta(minutes=10))
            return
        except: pass

    # Anti-Everyone
    if ("@everyone" in message.content or "@here" in message.content) and message.author.id not in WHITELIST_USERS:
        try:
            await message.delete()
            await message.author.edit(roles=[])
            await message.author.timeout(datetime.timedelta(hours=1))
            return
        except: pass

    # Anti-Spam
    user_id = message.author.id
    now = datetime.datetime.now()
    if user_id not in user_messages: user_messages[user_id] = []
    user_messages[user_id].append(now)
    user_messages[user_id] = [t for t in user_messages[user_id] if (now - t).total_seconds() < SPAM_SECONDS]
    if len(user_messages[user_id]) >= SPAM_LIMIT and user_id not in WHITELIST_USERS:
        try:
            await message.author.timeout(datetime.timedelta(minutes=10))
            def is_spam(m): return m.author.id == user_id
            await message.channel.purge(limit=15, check=is_spam)
            user_messages[user_id] = []
        except: pass

    await bot.process_commands(message)

if __name__ == "__main__":
    keep_alive()  
    bot.run(TOKEN)
