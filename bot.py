import discord
from discord.ext import commands, tasks
from flask import Flask
from threading import Thread
import random
import asyncio
import os
import re
import io
from PIL import Image, ImageDraw, ImageFont
import requests

# === SERVER PENTRU RENDER ===
app = Flask('')
@app.route('/')
def home(): return "Online"
def run():
    port = int(os.getenv("PORT", 8080))
    app.run(host='0.0.0.0', port=port)
def keep_alive():
    t = Thread(target=run)
    t.daemon = True
    t.start()

# === CONFIGURARE BOT ===
intents = discord.Intents.all()
bot = commands.Bot(command_prefix="#", intents=intents)

# ID-URI REVIZUITE
TOURNAMENT_CATEGORY_ID = 1481418592217206885
LOG_CHANNEL_ID = 1481418592217206885
TABEL_MECIURI_CH_ID = 1481418744956850392 
STAFF_ROLE_ID = 1481436643603906600       
SPECIAL_USER_ID = 810609759324471306     

# State Turneu
tournament_players = []
banned_players = [] 
tournament_data = {} 
tournament_status = "închis"

# --- LOGICĂ TABEL TEXT (Schema 10 Persoane) ---
bracket_slots = {i: "[LIBER]" for i in range(1, 18)}
# Mapare vizuală: 11=WinA, 12=WinB, 13=WinC, 14=WinD, 15=WinSUS, 16=WinJOS, 17=REGE

def generate_bracket_text(last_user="Nimeni", last_id="N/A"):
    text = (
        "```text\n"
        "ROUND 1           SEMIFINALA           FINALA           CAMPION\n\n"
        f"{bracket_slots[1]} ──┐\n"
        f"           ├── {bracket_slots[11]} ──┐\n"
        f"{bracket_slots[2]} ──┘                 │\n"
        f"                             ├── {bracket_slots[15]} ──┐\n"
        f"{bracket_slots[3]} ──┐                 │                  │\n"
        f"           ├── {bracket_slots[12]} ──┘                  │\n"
        f"{bracket_slots[4]} ──┘                                    │\n"
        "                                                │\n"
        f"{bracket_slots[5]} ───────────────────────────────────────┤\n"
        "                                                │\n"
        f"                                                ├── 🏆 {bracket_slots[17]}\n"
        f"{bracket_slots[10]} ──────────────────────────────────────┤\n"
        "                                                │\n"
        f"{bracket_slots[6]} ──┐                                    │\n"
        f"           ├── {bracket_slots[13]} ──┐                  │\n"
        f"{bracket_slots[7]} ──┘                 │                  │\n"
        f"                             ├── {bracket_slots[16]} ──┘\n"
        f"{bracket_slots[8]} ──┐                 │\n"
        f"           ├── {bracket_slots[14]} ──┘\n"
        f"{bracket_slots[9]} ──┘\n\n"
        "=========================================\n"
        f"Ultimul update: Jucătorul {last_user} (ID: {last_id})\n"
        "```"
    )
    return text

# ================= BUTON CLOSE TICKET =================

class TicketControlView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="ÎNCHIDE TICKET", style=discord.ButtonStyle.danger, custom_id="close_ticket_btn", emoji="🔒")
    async def close_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        is_staff = any(role.id == STAFF_ROLE_ID for role in interaction.user.roles)
        is_special = interaction.user.id == SPECIAL_USER_ID
        is_owner = interaction.user.id == interaction.guild.owner_id

        if is_staff or is_special or is_owner:
            await interaction.response.send_message("🔒 Ticketul se va închide în 5 secunde...")
            await asyncio.sleep(5)
            await interaction.channel.delete()
        else:
            await interaction.response.send_message("❌ Nu ai permisiunea de a închide acest ticket!", ephemeral=True)

# ================= SISTEM ÎNSCRIERE =================

class TournamentJoinView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="🏆 ÎNSCRIE-TE", style=discord.ButtonStyle.success, custom_id="tr_join_btn")
    async def create_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        global tournament_status
        if tournament_status != "înscrieri":
            return await interaction.response.send_message("❌ Înscrierile sunt închise momentan!", ephemeral=True)
        if interaction.user.id in banned_players:
            return await interaction.response.send_message("❌ Ai fost eliminat din turneu și nu te mai poți înscrie!", ephemeral=True)
        if interaction.user.id in tournament_players:
            return await interaction.response.send_message("❌ Ești deja înscris în acest turneu!", ephemeral=True)

        guild = interaction.guild
        category = guild.get_channel(TOURNAMENT_CATEGORY_ID)
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            interaction.user: discord.PermissionOverwrite(view_channel=True, send_messages=True, attach_files=True),
            guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True, manage_channels=True)
        }

        ticket_channel = await guild.create_text_channel(name=f"🎫-{interaction.user.name}", category=category, overwrites=overwrites)
        await interaction.response.send_message(f"✅ Ticket creat! Verifică aici: {ticket_channel.mention}", ephemeral=True)
        
        embed_ticket = discord.Embed(
            title="📝 FORMULAR DE ÎNSCRIERE",
            description="Te rugăm să trimiți un singur mesaj care să conțină:\n\n"
                        "1️⃣ **ID-ul de joc** (Ex: 12345678)\n"
                        "2️⃣ **Device-ul**\n"
                        "3️⃣ **Screenshot cu profilul tău**",
            color=discord.Color.blue()
        )
        embed_ticket.set_footer(text="Staff-ul va verifica datele trimise.")
        
        await ticket_channel.send(content=f"{interaction.user.mention}", embed=embed_ticket, view=TicketControlView())

        def check(m):
            return m.author == interaction.user and m.channel == ticket_channel and len(m.attachments) > 0

        try:
            msg = await bot.wait_for("message", check=check, timeout=600)
            
            found_id = re.search(r'\d{5,10}', msg.content)
            game_id = found_id.group(0) if found_id else "ID Necunoscut"

            tournament_players.append(interaction.user.id)
            tournament_data[interaction.user.id] = {
                "user_name": interaction.user.name,
                "game_id": game_id,
                "mention": interaction.user.mention
            }

            # --- AUTOMATIZARE TABEL LA INSCRIERE ---
            tabel_ch = bot.get_channel(TABEL_MECIURI_CH_ID)
            if tabel_ch:
                # Căutăm primul loc liber de la 1 la 10
                for i in range(1, 11):
                    if bracket_slots[i] == "[LIBER]":
                        bracket_slots[i] = f"{interaction.user.name}({game_id})"
                        break
                await tabel_ch.send(generate_bracket_text(interaction.user.name, game_id))

            log_chan = bot.get_channel(LOG_CHANNEL_ID)
            if log_chan:
                log_embed = discord.Embed(title="📥 ÎNSCRIERE NOUĂ CONFIRMATĂ", color=discord.Color.green())
                log_embed.add_field(name="Jucător", value=interaction.user.mention, inline=True)
                log_embed.add_field(name="ID Joc Detalii", value=msg.content, inline=True)
                log_embed.set_image(url=msg.attachments[0].url)
                await log_chan.send(embed=log_embed)

            await ticket_channel.send("✅ Datele au fost înregistrate! Așteaptă confirmarea staff-ului.")
        except asyncio.TimeoutError:
            await ticket_channel.delete()

# ================= COMENZI STAFF (#win / #set / #lose) =================

def is_staff_or_special():
    async def predicate(ctx):
        is_staff = any(role.id == STAFF_ROLE_ID for role in ctx.author.roles)
        return is_staff or ctx.author.id == SPECIAL_USER_ID or ctx.author.id == ctx.guild.owner_id
    return commands.check(predicate)

@bot.command()
@is_staff_or_special()
async def win(ctx, pozitie: int, member: discord.Member):
    if 1 <= pozitie <= 17:
        p_data = tournament_data.get(member.id, {"game_id": "N/A"})
        bracket_slots[pozitie] = f"{member.name}({p_data['game_id']})"
        
        tabel_ch = bot.get_channel(TABEL_MECIURI_CH_ID)
        if tabel_ch:
            await tabel_ch.send(generate_bracket_text(member.name, p_data['game_id']))
            await ctx.send(f"✅ Jucătorul {member.mention} a fost pus pe poziția {pozitie}!")
    else:
        await ctx.send("❌ Alege o poziție între 1 și 17.")

@bot.command()
@is_staff_or_special()
async def set(ctx, pozitie: int, member: discord.Member):
    # Această comandă face același lucru ca #win, dar cu numele cerut de tine
    if 1 <= pozitie <= 17:
        p_data = tournament_data.get(member.id, {"game_id": "N/A"})
        bracket_slots[pozitie] = f"{member.name}({p_data['game_id']})"
        
        tabel_ch = bot.get_channel(TABEL_MECIURI_CH_ID)
        if tabel_ch:
            await tabel_ch.send(generate_bracket_text(member.name, p_data['game_id']))
            await ctx.send(f"✅ Poziția {pozitie} a fost actualizată pentru {member.mention}!")
    else:
        await ctx.send("❌ Alege o poziție între 1 și 17.")

@bot.command()
@is_staff_or_special()
async def lose(ctx, member: discord.Member):
    global tournament_players, banned_players
    if member.id in tournament_players: tournament_players.remove(member.id)
    banned_players.append(member.id)
    tabel_ch = bot.get_channel(TABEL_MECIURI_CH_ID)
    if tabel_ch:
        await tabel_ch.send(f"❌ **{member.display_name}** a fost eliminat din turneu.")
    await ctx.message.add_reaction("💀")

# ================= COMENZI DOAR OWNER =================

@bot.command()
@commands.is_owner()
async def setup_tournament(ctx):
    await ctx.message.delete()
    embed = discord.Embed(
        title="🏆 STANDOFF 2 - TOURNAMENT 🏆",
        description="Apasă butonul de mai jos pentru a deschide un ticket de înscriere.",
        color=0xff0000
    )
    await ctx.send(embed=embed, view=TournamentJoinView())

@bot.command()
@commands.is_owner()
async def admin_tr(ctx):
    embed = discord.Embed(title="🛡️ PANOU CONTROL OWNER", color=discord.Color.dark_grey())
    view = discord.ui.View()
    
    btn_start = discord.ui.Button(label="START ÎNSCRIERI", style=discord.ButtonStyle.success)
    async def start_callback(inter):
        global tournament_status
        tournament_status = "înscrieri"
        await inter.response.send_message("✅ Pornit!", ephemeral=True)
    btn_start.callback = start_callback
    
    btn_stop = discord.ui.Button(label="STOP ÎNSCRIERI", style=discord.ButtonStyle.danger)
    async def stop_callback(inter):
        global tournament_status
        tournament_status = "închis"
        await inter.response.send_message("🛑 Oprit!", ephemeral=True)
    btn_stop.callback = stop_callback

    btn_reset = discord.ui.Button(label="RESET DATE", style=discord.ButtonStyle.secondary)
    async def reset_callback(inter):
        global tournament_players, banned_players, tournament_data, bracket_slots
        tournament_players, banned_players, tournament_data = [], [], {}
        for i in range(1, 18): bracket_slots[i] = "[LIBER]"
        await inter.response.send_message("🧹 Resetat!", ephemeral=True)
    btn_reset.callback = reset_callback

    view.add_item(btn_start)
    view.add_item(btn_stop)
    view.add_item(btn_reset)
    await ctx.send(embed=embed, view=view, ephemeral=True)

@bot.event
async def on_ready():
    bot.add_view(TournamentJoinView())
    bot.add_view(TicketControlView())
    print(f"✅ Bot Online: {bot.user}")

keep_alive()
bot.run(os.getenv("DISCORD_TOKEN"))
