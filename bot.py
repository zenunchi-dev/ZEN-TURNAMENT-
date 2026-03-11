import discord
from discord.ext import commands, tasks
from flask import Flask
from threading import Thread
import random
import asyncio
import os
import re

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
            
            # Încercăm să extragem ID-ul (cifre) din mesaj
            found_id = re.search(r'\d{5,10}', msg.content)
            game_id = found_id.group(0) if found_id else "ID Necunoscut"

            tournament_players.append(interaction.user.id)
            tournament_data[interaction.user.id] = {
                "user_name": interaction.user.display_name,
                "game_id": game_id
            }

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

# ================= COMENZI STAFF (#win / #lose) =================

def is_staff_or_special():
    async def predicate(ctx):
        is_staff = any(role.id == STAFF_ROLE_ID for role in ctx.author.roles)
        return is_staff or ctx.author.id == SPECIAL_USER_ID or ctx.author.id == ctx.guild.owner_id
    return commands.check(predicate)

@bot.command()
@is_staff_or_special()
async def win(ctx, member: discord.Member):
    tabel_ch = bot.get_channel(TABEL_MECIURI_CH_ID)
    if tabel_ch:
        p_data = tournament_data.get(member.id, {"game_id": "N/A"})
        # Formatul cerut: Nume Discord + ID într-un pătrățel (code block)
        visual_name = f"**{member.display_name}** `ID: {p_data['game_id']}`"
        
        embed = discord.Embed(
            title="🏆 ETAPĂ URMĂTOARE",
            description=f"Jucătorul {visual_name} a câștigat și merge mai departe!",
            color=discord.Color.gold()
        )
        await tabel_ch.send(embed=embed)
        await ctx.message.add_reaction("✅")

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

# ================= COMENZI DOAR OWNER (#setup / #admin) =================

@bot.command()
@commands.is_owner()
async def setup_tournament(ctx):
    await ctx.message.delete()
    embed = discord.Embed(
        title="🏆 STANDOFF 2 - TOURNAMENT 🏆",
        description="Apasă butonul de mai jos pentru a deschide un ticket de înscriere.\n\n"
                    "⚠️ **Asigură-te că ai screenshot-ul profilului pregătit!**",
        color=0xff0000
    )
    embed.set_image(url="https://i.imgur.com/your_tournament_banner.png") # Poți pune un banner aici
    await ctx.send(embed=embed, view=TournamentJoinView())

@bot.command()
@commands.is_owner()
async def admin_tr(ctx):
    embed = discord.Embed(
        title="🛡️ PANOU CONTROL OWNER",
        description="Gestionează starea înscrierilor pentru turneu.",
        color=discord.Color.dark_grey()
    )
    
    view = discord.ui.View()
    
    btn_start = discord.ui.Button(label="START ÎNSCRIERI", style=discord.ButtonStyle.success, emoji="▶️")
    async def start_callback(inter):
        global tournament_status
        tournament_status = "înscrieri"
        await inter.response.send_message("✅ Înscrierile au fost pornite!", ephemeral=True)
    btn_start.callback = start_callback
    
    btn_stop = discord.ui.Button(label="STOP ÎNSCRIERI", style=discord.ButtonStyle.danger, emoji="⏹️")
    async def stop_callback(inter):
        global tournament_status
        tournament_status = "închis"
        await inter.response.send_message("🛑 Înscrierile au fost oprite!", ephemeral=True)
    btn_stop.callback = stop_callback

    btn_reset = discord.ui.Button(label="RESET DATE", style=discord.ButtonStyle.secondary, emoji="🔄")
    async def reset_callback(inter):
        global tournament_players, banned_players, tournament_data
        tournament_players, banned_players, tournament_data = [], [], {}
        await inter.response.send_message("🧹 Toate datele au fost resetate!", ephemeral=True)
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
