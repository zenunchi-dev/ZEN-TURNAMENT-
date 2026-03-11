import discord
from discord.ext import commands, tasks
from flask import Flask
from threading import Thread
import random
import asyncio
import os

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

# ID-URILE TALE
CATEGORY_TICKETS = 1481418592217206885
LOG_CH_ID = 1481418592217206885
TABEL_MECIURI_CH_ID = 1481430801131376640 # Canalul unde se trimite progresul

tournament_players = []
tournament_data = {}
tournament_status = "închis"

# ================= SISTEM ÎNSCRIERE PRIN TICKET (POZĂ DIRECTĂ) =================

class TournamentJoinView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="ÎNSCRIE-TE ÎN TURNEU", style=discord.ButtonStyle.success, custom_id="tr_join_btn", emoji="🏆")
    async def create_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        global tournament_status
        if tournament_status != "înscrieri":
            return await interaction.response.send_message("❌ Înscrierile sunt închise!", ephemeral=True)
        if interaction.user.id in tournament_players:
            return await interaction.response.send_message("❌ Ești deja înscris!", ephemeral=True)
        if len(tournament_players) >= 8:
            return await interaction.response.send_message("❌ Turneul este plin!", ephemeral=True)

        guild = interaction.guild
        category = guild.get_channel(CATEGORY_TICKETS)
        
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            interaction.user: discord.PermissionOverwrite(view_channel=True, send_messages=True),
            guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True, manage_channels=True)
        }

        ticket_ch = await guild.create_text_channel(name=f"înscriere-{interaction.user.name}", category=category, overwrites=overwrites)
        await interaction.response.send_message(f"✅ Ticket creat: {ticket_ch.mention}", ephemeral=True)

        await ticket_ch.send(f"Salut {interaction.user.mention}!\n\n**Te rog să trimiți următoarele date într-un singur mesaj:**\n1. ID-ul de joc\n2. Device-ul (Telefon/Tabletă)\n3. **ATAȘEAZĂ POZA/SS CU PROFILUL TĂU SO2**")

        def check(m):
            return m.author == interaction.user and m.channel == ticket_ch and len(m.attachments) > 0

        try:
            msg = await bot.wait_for("message", check=check, timeout=300)
            
            # Salvăm datele
            tournament_players.append(interaction.user.id)
            tournament_data[interaction.user.id] = {
                "nume": interaction.user.display_name,
                "info": msg.content,
                "photo_url": msg.attachments[0].url
            }

            # Trimitem Log-ul cu POZA directă
            log_ch = bot.get_channel(LOG_CH_ID)
            if log_ch:
                embed = discord.Embed(title="📥 ÎNSCRIERE NOUĂ", color=discord.Color.green())
                embed.add_field(name="Utilizator", value=interaction.user.mention)
                embed.add_field(name="Detalii", value=msg.content if msg.content else "Doar poză")
                embed.set_image(url=msg.attachments[0].url)
                await log_ch.send(embed=embed)

            await ticket_ch.send("✅ Înregistrare reușită! Ticket-ul se va închide în 10 secunde.")
            await asyncio.sleep(10)
            await ticket_ch.delete()

        except asyncio.TimeoutError:
            await ticket_ch.send("❌ Timp expirat. Ticket-ul se va închide.")
            await asyncio.sleep(5)
            await ticket_ch.delete()

# ================= ADMIN PANEL & TABEL DINAMIC =================

class TournamentAdminPanel(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="DESCHIDE ÎNSCRIERI", style=discord.ButtonStyle.success, custom_id="adm_open")
    async def open_reg(self, interaction: discord.Interaction, button: discord.ui.Button):
        global tournament_status, tournament_players, tournament_data
        tournament_status, tournament_players, tournament_data = "înscrieri", [], {}
        await interaction.response.send_message("✅ Înscrierile sunt deschise!", ephemeral=True)

    @discord.ui.button(label="GENEREAZĂ CALIFICĂRI", style=discord.ButtonStyle.danger, custom_id="adm_gen")
    async def start_tr(self, interaction: discord.Interaction, button: discord.ui.Button):
        if len(tournament_players) < 8:
            return await interaction.response.send_message(f"❌ Nevoie de 8 oameni!", ephemeral=True)
        
        random.shuffle(tournament_players)
        p = tournament_players
        meciuri = [[p[0], p[1]], [p[2], p[3]], [p[4], p[5]], [p[6], p[7]]]
        
        embed = discord.Embed(title="🏆 TABEL TURNEU - CALIFICĂRI", color=0xffd700)
        for i, m in enumerate(meciuri):
            n1 = tournament_data[m[0]]['nume']
            n2 = tournament_data[m[1]]['nume']
            embed.add_field(name=f"Meciul {i+1}", value=f"⚔️ **{n1}** vs **{n2}**", inline=False)
        
        # Trimitem pe canalul de TABEL specificat de tine
        tabel_ch = bot.get_channel(TABEL_MECIURI_CH_ID)
        if tabel_ch:
            await tabel_ch.send(embed=embed)
        await interaction.response.send_message("✅ Tabelul a fost trimis!", ephemeral=True)

    @discord.ui.button(label="PROMOVEAZĂ JUCĂTOR", style=discord.ButtonStyle.primary, custom_id="adm_win")
    async def winner(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Această funcție poate fi extinsă pentru a muta jucătorii manual în etapa următoare
        await interaction.response.send_message("Scrie `#win @jucator` pentru a-l trece în etapa următoare pe canalul de tabel.", ephemeral=True)

# ================= COMENZI =================

@bot.command()
@commands.is_owner()
async def win(ctx, member: discord.Member):
    """Anunță cine a trecut mai departe pe canalul de tabel"""
    tabel_ch = bot.get_channel(TABEL_MECIURI_CH_ID)
    if tabel_ch:
        await tabel_ch.send(f"✨ Jucătorul **{member.display_name}** a câștigat meciul și trece în etapa următoare! 🏆")
        await ctx.send(f"✅ Am anunțat victoria lui {member.mention} pe canalul de tabel.")

@bot.command()
@commands.is_owner()
async def setup_tournament(ctx):
    await ctx.message.delete()
    embed = discord.Embed(title="🏆 TURNEU STANDOFF 2 🏆", description="Apasă butonul de mai jos pentru a te înscrie prin TICKET.\nPregătește ID-ul și Screenshot-ul cu profilul!", color=0xff0000)
    await ctx.send(embed=embed, view=TournamentJoinView())

@bot.command()
@commands.is_owner()
async def admin_tr(ctx):
    await ctx.send("🛡️ **ADMIN PANEL**", view=TournamentAdminPanel(), ephemeral=True)

@bot.event
async def on_ready():
    print(f"✅ Bot Online: {bot.user}")
    bot.add_view(TournamentJoinView())
    bot.add_view(TournamentAdminPanel())

keep_alive()
bot.run(os.getenv("DISCORD_TOKEN"))
