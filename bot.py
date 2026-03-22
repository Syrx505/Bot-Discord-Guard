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
MENTION_LIMIT = 3
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

# --- 1. KOMANDALAR ---
@bot.tree.command(name="activate", description="Bütün qorumaları aktiv edir.")
@app_commands.checks.has_permissions(administrator=True)
async def activate(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True) 
    bot.protection_active = True
    await interaction.followup.send("🛡️ Qoruma sistemi (Anti-Ban daxil) aktiv edildi!")

@bot.tree.command(name="join", description="Kanal ID-si vasitəsilə səsə girər və 7/24 orda qalar.")
@app_commands.describe(channel_id="Girmək istədiyiniz səs kanalının ID-si")
async def join(interaction: discord.Interaction, channel_id: str):
    try:
        target_channel = bot.get_channel(int(channel_id))
        if not target_channel or not isinstance(target_channel, discord.VoiceChannel):
            await interaction.response.send_message("❌ Səhv ID!", ephemeral=True)
            return
        if interaction.guild.voice_client:
            await interaction.guild.voice_client.move_to(target_channel)
        else:
            await target_channel.connect()
        await interaction.response.send_message(f"🎙️ **{target_channel.name}** kanalına girildi!")
    except Exception as e:
        await interaction.response.send_message(f"❌ Xəta: {e}", ephemeral=True)

# --- 2. ANTİ-BAN (BAN ATANI CƏZALANDIRMA) ---
@bot.event
async def on_member_ban(guild, user):
    if not bot.protection_active: return
    
    await asyncio.sleep(1) # Audit Log-un düşməsi üçün gözləmə
    async for entry in guild.audit_logs(limit=1, action=discord.AuditLogAction.ban):
        executor = entry.user # Banı atan şəxs
        
        # Əgər banı atan Whitelist-də deyilsə və botun özü deyilsə
        if executor.id not in WHITELIST_USERS and executor.id != bot.user.id:
            member = guild.get_member(executor.id)
            if member:
                try:
                    # Banı atanın rollarını al
                    await member.edit(roles=[], reason="İzinsiz ban atmaq!")
                    # Banı atanı 1 saatlıq timeout et
                    await member.timeout(datetime.timedelta(hours=1), reason="İzinsiz ban cəhdi")
                    
                    # Kanala məlumat ver
                    if guild.system_channel:
                        await guild.system_channel.send(f"🚫 **KRİTİK:** {executor.mention} icazəsiz ban atdığı üçün bütün yetkiləri alındı!")
                except Exception as e:
                    print(f"Anti-Ban xətası: {e}")

# --- 3. DİGƏR QORUMALAR (Kanal, Rol, Perm) ---
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
                    await member.edit(roles=[], reason="Kanal ayarı dəyişmə!")
                    await member.timeout(datetime.timedelta(hours=1))
                except: pass

@bot.event
async def on_guild_channel_delete(channel):
    if not bot.protection_active: return
    await asyncio.sleep(1)
    async for entry in channel.guild.audit_logs(limit=1, action=discord.AuditLogAction.channel_delete):
        user = entry.user
        if user.id in WHITELIST_USERS or user.id == bot.user.id: return
        member = channel.guild.get_member(user.id)
        if member:
            try:
                await channel.guild.create_text_channel(name=channel.name, category=channel.category, position=channel.position)
                await member.edit(roles=[])
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
                    await executor.edit(roles=[])
                    await after.edit(roles=before.roles)
                except: pass

# --- 4. MESAJ QORUMALARI ---
@bot.event
async def on_message(message):
    if message.author.bot or not message.guild or not bot.protection_active: return
    if len(message.mentions) > MENTION_LIMIT and message.author.id not in WHITELIST_USERS:
        try: await message.delete(); await message.author.ban(reason="Mass Mention"); return
        except: pass
    if LINK_PATTERN.search(message.content.lower()) and message.author.id not in WHITELIST_USERS:
        try: await message.delete(); await message.author.timeout(datetime.timedelta(minutes=10))
        except: pass
    if ("@everyone" in message.content or "@here" in message.content) and message.author.id not in WHITELIST_USERS:
        try: await message.delete(); await message.author.edit(roles=[])
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

# --- SƏS 7/24 ---
@bot.event
async def on_voice_state_update(member, before, after):
    if member.id == bot.user.id and after.channel is None:
        if before.channel:
            await asyncio.sleep(3)
            try: await before.channel.connect()
            except: pass

if __name__ == "__main__":
    keep_alive()  
    bot.run(TOKEN)
