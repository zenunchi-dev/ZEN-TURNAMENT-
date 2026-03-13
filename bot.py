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
TABEL_MECIURI_CH_ID = 1481418744956850392 
STAFF_ROLE_ID = 1481794622752555072       
OWNER_ID = 1466541122636611759            
REJECT_ROLE_ID = 1481789988654940272      
TOURNAMENT_ROLE_ID = 1481418649196560414  
SPECIAL_USER_ID = 810609759324471306     

# State Turneu
tournament_players = []
tournament_status = "închis"
last_table_msg_id = None 
bracket_slots = {i: "[LIBER]" for i in range(1, 18)}

# --- TABEL ---
def generate_bracket_text(last_user="Nimeni"):
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
        f"Ultimul update: {last_user}\n"
        "```"
    )
    return text

async def update_table(user_name="Nimeni"):
    global last_table_msg_id
    tabel_ch = bot.get_channel(TABEL_MECIURI_CH_ID)
    if tabel_ch:
        if last_table_msg_id:
            try:
                old_msg = await tabel_ch.fetch_message(last_table_msg_id)
                await old_msg.delete()
            except: pass
        new_msg = await tabel_ch.send(generate_bracket_text(user_name))
        last_table_msg_id = new_msg.id

# ================= VIEWS =================

class StaffReviewView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="ACCEPTĂ", style=discord.ButtonStyle.success, emoji="✅", custom_id="persistent_accept_v5")
    async def accept(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not (any(r.id == STAFF_ROLE_ID for r in interaction.user.roles) or interaction.user.id == OWNER_ID):
            return await interaction.response.send_message("❌ Doar Staff!", ephemeral=True)

        # Găsim jucătorul din mențiunea din mesaj
        match = re.search(r'<@!?(\d+)>', interaction.message.content)
        if not match: return await interaction.response.send_message("❌ Eroare utilizator!", ephemeral=True)
        target = interaction.guild.get_member(int(match.group(1)))

        free = [i for i in range(1, 11) if bracket_slots[i] == "[LIBER]"]
        if not free: return await interaction.response.send_message("❌ Tabel plin!", ephemeral=True)

        slot = random.choice(free)
        bracket_slots[slot] = f"{target.name}"
        await update_table(target.name)
        await interaction.response.send_message(f"✅ {target.name} adăugat pe {slot}!")

    @discord.ui.button(label="REJECTĂ", style=discord.ButtonStyle.danger, emoji="❌", custom_id="persistent_reject_v5")
    async def reject(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not (any(r.id == STAFF_ROLE_ID for r in interaction.user.roles) or interaction.user.id == OWNER_ID):
            return await interaction.response.send_message("❌ Doar Staff!", ephemeral=True)

        match = re.search(r'<@!?(\d+)>', interaction.message.content)
        target = interaction.guild.get_member(int(match.group(1)))
        rej_role = interaction.guild.get_role(REJECT_ROLE_ID)
        
        if rej_role and target:
            await target.add_roles(rej_role)
            await interaction.response.send_message(f"❌ Respins. Rolul scos în 12h.")
            async def remove_later():
                await asyncio.sleep(43200)
                try: await target.remove_roles(rej_role)
                except: pass
            bot.loop.create_task(remove_later())

class TicketControlView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="ÎNCHIDE TICKET", style=discord.ButtonStyle.danger, custom_id="persistent_close_v5", emoji="🔒")
    async def close_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        if any(r.id == STAFF_ROLE_ID for r in interaction.user.roles) or interaction.user.id in [OWNER_ID, SPECIAL_USER_ID]:
            await interaction.response.send_message("🔒 Se închide...")
            await asyncio.sleep(3)
            await interaction.channel.delete()

class TournamentJoinView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="🏆 ÎNSCRIE-TE", style=discord.ButtonStyle.success, custom_id="persistent_join_v5")
    async def create_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        global tournament_status
        if tournament_status != "înscrieri":
            return await interaction.response.send_message("❌ Înscrierile sunt închise!", ephemeral=True)
        
        if any(role.id == REJECT_ROLE_ID for role in interaction.user.roles):
            return await interaction.response.send_message("❌ Ai Reject recent!", ephemeral=True)

        guild = interaction.guild
        category = guild.get_channel(TOURNAMENT_CATEGORY_ID)
        
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            interaction.user: discord.PermissionOverwrite(view_channel=True, send_messages=True),
            guild.get_role(STAFF_ROLE_ID): discord.PermissionOverwrite(view_channel=True, send_messages=True),
            guild.get_member(OWNER_ID): discord.PermissionOverwrite(view_channel=True, send_messages=True)
        }

        ch = await guild.create_text_channel(name=f"🎫-{interaction.user.name}", category=category, overwrites=overwrites)
        await interaction.response.send_message(f"✅ Ticket: {ch.mention}", ephemeral=True)
        
        # Trimitem butoanele FĂRĂ a cere player în __init__, folosim mențiunea pentru logică
        await ch.send(content=f"Cerere de la: {interaction.user.mention}\nTrimite screenshot-ul!", view=StaffReviewView())
        await ch.send("Control:", view=TicketControlView())

# ================= COMENZI =================

@bot.command(name="win", aliases=["set"])
async def set_winner(ctx, slot: int, member: discord.Member):
    if not (any(r.id == STAFF_ROLE_ID for r in ctx.author.roles) or ctx.author.id == OWNER_ID):
        return await ctx.send("❌ Lipsă permisiuni!")
    if slot in bracket_slots:
        bracket_slots[slot] = f"{member.name}"
        await update_table(member.name)
        await ctx.send(f"✅ Seta pe locul {slot}.")
    else: await ctx.send("❌ Loc 1-17!")

@bot.command()
@commands.is_owner()
async def setup_tournament(ctx):
    await ctx.message.delete()
    embed = discord.Embed(title="🏆 TURNEU STANDOFF 2", description="Apasă butonul pentru înscriere.", color=0xff0000)
    await ctx.send(embed=embed, view=TournamentJoinView())

@bot.command()
@commands.is_owner()
async def admin_tr(ctx):
    v = discord.ui.View()
    b1 = discord.ui.Button(label="START ÎNSCRIERI", style=discord.ButtonStyle.green)
    async def s1(i):
        global tournament_status
        tournament_status = "înscrieri"
        await i.response.send_message("✅ Pornit!", ephemeral=True)
    b1.callback = s1
    b2 = discord.ui.Button(label="STOP ÎNSCRIERI", style=discord.ButtonStyle.red)
    async def s2(i):
        global tournament_status
        tournament_status = "închis"
        await i.response.send_message("🛑 Oprit!", ephemeral=True)
    b2.callback = s2
    v.add_item(b1); v.add_item(b2)
    await ctx.send("Control:", view=v, ephemeral=True)

@bot.event
async def on_ready():
    bot.add_view(TournamentJoinView())
    bot.add_view(TicketControlView())
    bot.add_view(StaffReviewView())
    print(f"✅ Bot Online!")

keep_alive()
bot.run(os.getenv("DISCORD_TOKEN"))
