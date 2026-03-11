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

# ID-URI REVIZUITE
TOURNAMENT_CATEGORY_ID = 1481418592217206885
LOG_CHANNEL_ID = 1481418592217206885
TABEL_MECIURI_CH_ID = 1481418744956850392 
STAFF_ROLE_ID = 1481436643603906600       # Staff general
SPECIAL_USER_ID = 810609759324471306     # Utilizator cu acces special la ticket

# State Turneu
tournament_players = []
banned_players = [] # Jucătorii care au pierdut (nu se mai pot înscrie)
tournament_data = {} 
tournament_matches = []
tournament_status = "închis"

# ================= BUTON CLOSE TICKET =================

class TicketControlView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="ÎNCHIDE TICKET", style=discord.ButtonStyle.danger, custom_id="close_ticket_btn", emoji="🔒")
    async def close_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Verificare permisiuni: Doar Staff sau ID-ul Special
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

    @discord.ui.button(label="ÎNSCRIE-TE ÎN TURNEU", style=discord.ButtonStyle.success, custom_id="tr_join_btn", emoji="🏆")
    async def create_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        global tournament_status
        if tournament_status != "înscrieri":
            return await interaction.response.send_message("❌ Înscrierile sunt închise!", ephemeral=True)
        if interaction.user.id in banned_players:
            return await interaction.response.send_message("❌ Ai pierdut deja și nu te mai poți înscrie!", ephemeral=True)
        if interaction.user.id in tournament_players:
            return await interaction.response.send_message("❌ Ești deja înscris!", ephemeral=True)

        guild = interaction.guild
        category = guild.get_channel(TOURNAMENT_CATEGORY_ID)
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            interaction.user: discord.PermissionOverwrite(view_channel=True, send_messages=True, attach_files=True),
            guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True, manage_channels=True)
        }

        ticket_channel = await guild.create_text_channel(name=f"înscriere-{interaction.user.name}", category=category, overwrites=overwrites)
        await interaction.response.send_message(f"✅ Ticket creat! {ticket_channel.mention}", ephemeral=True)
        
        # Trimitem instrucțiunile și butonul de Close
        await ticket_channel.send(
            content=f"Salut {interaction.user.mention}! Trimite ID, Device și Poza Profil SO2 aici.\n\n*Butonul de mai jos este doar pentru Staff:*",
            view=TicketControlView()
        )

        def check(m):
            return m.author == interaction.user and m.channel == ticket_channel and len(m.attachments) > 0

        try:
            msg = await bot.wait_for("message", check=check, timeout=600)
            tournament_players.append(interaction.user.id)
            tournament_data[interaction.user.id] = {"user_name": interaction.user.display_name}

            log_chan = bot.get_channel(LOG_CHANNEL_ID)
            if log_chan:
                embed = discord.Embed(title="📥 ÎNSCRIERE NOUĂ", color=discord.Color.green())
                embed.add_field(name="Jucător", value=interaction.user.mention)
                embed.set_image(url=msg.attachments[0].url)
                await log_chan.send(embed=embed)

            await ticket_channel.send("✅ Date salvate! Staff-ul va închide ticketul după verificare.")
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
        await tabel_ch.send(f"🏆 Jucătorul **{member.display_name}** trece în etapa următoare!")

@bot.command()
@is_staff_or_special()
async def lose(ctx, member: discord.Member):
    global tournament_players, banned_players
    if member.id in tournament_players: tournament_players.remove(member.id)
    banned_players.append(member.id)
    tabel_ch = bot.get_channel(TABEL_MECIURI_CH_ID)
    if tabel_ch:
        await tabel_ch.send(f"❌ **{member.display_name}** a fost eliminat!")

# ================= COMENZI DOAR OWNER (#setup / #admin) =================

@bot.command()
@commands.is_owner()
async def setup_tournament(ctx):
    await ctx.message.delete()
    embed = discord.Embed(title="🏆 TURNEU STANDOFF 2", description="Apasă butonul pentru înscriere!", color=0xff0000)
    await ctx.send(embed=embed, view=TournamentJoinView())

@bot.command()
@commands.is_owner()
async def admin_tr(ctx):
    view = discord.ui.View()
    # Adăugăm butoanele rapid pentru panou
    btn_open = discord.ui.Button(label="DESCHIDE ÎNSCRIERI", style=discord.ButtonStyle.success)
    async def open_callback(inter):
        global tournament_status, tournament_players, banned_players
        tournament_status, tournament_players, banned_players = "înscrieri", [], []
        await inter.response.send_message("✅ Înscrieri deschise!", ephemeral=True)
    btn_open.callback = open_callback
    view.add_item(btn_open)
    
    await ctx.send("🛡️ **PANOU OWNER**", view=view, ephemeral=True)

@bot.event
async def on_ready():
    bot.add_view(TournamentJoinView())
    bot.add_view(TicketControlView())
    print(f"✅ Bot Online: {bot.user}")

keep_alive()
bot.run(os.getenv("DISCORD_TOKEN"))
