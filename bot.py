import discord
from discord.ext import commands
from discord import app_commands
import datetime
import os
import re
import asyncio
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
WHITELIST_USERS = [1402762600550240357, 1388969148683522270, 1218963997441921165, 973615262655975465, 1460228601051086858]
SPAM_LIMIT = 5
SPAM_SECONDS = 3
MENTION_LIMIT = 3 # Bir mesajda maksimum 3 etiket ola bilər
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
    print(f'--- {bot.user.name} TOTAL PROTECTION AKTİVDİR ---')

@bot.tree.command(name="activate", description="Raid və Nuke qorumasını aktiv edir.")
@app_commands.checks.has_permissions(administrator=True)
async def activate(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True) 
    bot.protection_active = True
    await interaction.followup.send("🛡️ Raid qoruması (Mass Mention daxil) aktiv edildi!")

# --- 1. KANAL/ROL/YETKİ QORUMALARI (Eyni qalır) ---
@bot.event
async def on_guild_channel_update(before, after):
    if not bot.protection_active: return
    await asyncio.sleep(1)
    async for entry in after.guild.audit_logs(limit=1, action=discord.AuditLogAction.channel_update):
        user = entry.user
        if user.id not in WHITELIST_USERS and user.id != bot.user.id:
            member = after.guild.get_member(user.id)
            if member:
                try:
                    await member.edit(roles=[], reason="İzinsiz kanal ayarı dəyişmə!")
                    await member.timeout(datetime.timedelta(hours=1))
                except: pass

@bot.event
async def on_guild_channel_delete(channel):
    if not bot.protection_active: return
    await asyncio.sleep(1)
    async for entry in channel.guild.audit_logs(limit=1, action=discord.AuditLogAction.channel_delete):
        user = entry.user
        if user.id in WHITELIST_USERS or user.id == bot.user.id or user.id == channel.guild.owner_id: return
        member = channel.guild.get_member(user.id)
        if member:
            try:
                await channel.guild.create_text_channel(name=channel.name, category=channel.category, position=channel.position)
                await member.edit(roles=[], reason="İzinsiz kanal silmə!")
                await member.timeout(datetime.timedelta(hours=1))
            except: pass

@bot.event
async def on_member_update(before, after):
    if not bot.protection_active: return
    if len(before.roles) != len(after.roles):
        await asyncio.sleep(1)
        async for entry in after.guild.audit_logs(limit=1, action=discord.AuditLogAction.member_role_update):
            user = entry.user
            if user.id in WHITELIST_USERS or user.id == bot.user.id: return
            executor = after.guild.get_member(user.id)
            if executor:
                try:
                    await executor.edit(roles=[], reason="İzinsiz rol dəyişikliyi!")
                    await after.edit(roles=before.roles)
                except: pass

# --- 2. MESAJ VƏ RAİD QORUMASI ---
@bot.event
async def on_message(message):
    if message.author.bot or not message.guild or not bot.protection_active: return
    
    # --- MASS MENTION (ID SCRAPE SPAM) QORUMASI ---
    if len(message.mentions) > MENTION_LIMIT:
        if message.author.id not in WHITELIST_USERS:
            try:
                await message.delete()
                # Raid edən hesabı dərhal banlayırıq (çünki bu normal istifadəçi deyil)
                await message.author.ban(reason="Mass Mention Raid cəhdi!")
                await message.channel.send(f"🚨 **RAİD BLOKLANDI:** {message.author.name} çoxlu etiket atdığı üçün banlandı!", delete_after=10)
                return
            except: pass

    # Anti-Link
    if LINK_PATTERN.search(message.content.lower()) and message.author.id not in WHITELIST_USERS:
        try: await message.delete(); await message.author.timeout(datetime.timedelta(minutes=10))
        except: pass

    # Anti-Everyone
    if ("@everyone" in message.content or "@here" in message.content) and message.author.id not in WHITELIST_USERS:
        try: await message.delete(); await message.author.edit(roles=[]); await message.author.timeout(datetime.timedelta(hours=1))
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
