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

# ID-URI
TOURNAMENT_CATEGORY_ID = 1481418592217206885
TABEL_MECIURI_CH_ID = 1481418744956850392 
STAFF_ROLE_ID = 1481794622752555072       
OWNER_ID = 1466541122636611759            
REJECT_ROLE_ID = 1481790057412038738      
SPECIAL_USER_ID = 810609759324471306     

# State
tournament_players = []
banned_players = [] 
tournament_data = {} 
tournament_status = "închis"
last_table_msg_id = None

bracket_slots = {i: "[LIBER]" for i in range(1, 18)}

def generate_bracket_text(last_user="Nimeni", last_id="N/A"):
    return (
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

async def update_table(user_name="Nimeni", game_id="N/A"):
    global last_table_msg_id
    tabel_ch = bot.get_channel(TABEL_MECIURI_CH_ID)
    if tabel_ch:
        if last_table_msg_id:
            try:
                old_msg = await tabel_ch.fetch_message(last_table_msg_id)
                await old_msg.delete()
            except: pass
        new_msg = await tabel_ch.send(generate_bracket_text(user_name, game_id))
        last_table_msg_id = new_msg.id

# ================= BUTOANELE CARE "NU SE VEDEAU" (FIXED) =================

class StaffReviewView(discord.ui.View):
    def __init__(self, player_id, player_name):
        super().__init__(timeout=None)
        self.player_id = player_id
        self.player_name = player_name

    @discord.ui.button(label="ACCEPTĂ", style=discord.ButtonStyle.success, custom_id="staff_accept", emoji="✅")
    async def accept(self, interaction: discord.Interaction, button: discord.ui.Button):
        is_staff = any(role.id == STAFF_ROLE_ID for role in interaction.user.roles)
        if not (is_staff or interaction.user.id == OWNER_ID):
            return await interaction.response.send_message("❌ Doar Staff/Owner!", ephemeral=True)

        free_slots = [i for i in range(1, 11) if bracket_slots[i] == "[LIBER]"]
        if not free_slots: return await interaction.response.send_message("❌ Plin!", ephemeral=True)

        slot = random.choice(free_slots)
        bracket_slots[slot] = f"{self.player_name}"
        tournament_players.append(self.player_id)
        
        await update_table(self.player_name, "ID")
        await interaction.response.send_message(f"✅ Adăugat pe locul {slot}!")
        self.stop()

    @discord.ui.button(label="REJECTĂ", style=discord.ButtonStyle.danger, custom_id="staff_reject", emoji="❌")
    async def reject(self, interaction: discord.Interaction, button: discord.ui.Button):
        is_staff = any(role.id == STAFF_ROLE_ID for role in interaction.user.roles)
        if not (is_staff or interaction.user.id == OWNER_ID):
            return await interaction.response.send_message("❌ Doar Staff/Owner!", ephemeral=True)

        member = interaction.guild.get_member(self.player_id)
        role = interaction.guild.get_role(REJECT_ROLE_ID)
        if member and role:
            await member.add_roles(role)
            await interaction.response.send_message(f"❌ Respins 12h.")
            async def remove_later():
                await asyncio.sleep(43200)
                try: await member.remove_roles(role)
                except: pass
            bot.loop.create_task(remove_later())
        self.stop()

# ================= TICKET & ADMIN (STRICT CUM AI ZIS) =================

class TicketControlView(discord.ui.View):
    def __init__(self, player_id, player_name):
        super().__init__(timeout=None)
        self.player_id = player_id
        self.player_name = player_name

    @discord.ui.button(label="ÎNCHIDE TICKET", style=discord.ButtonStyle.danger, custom_id="close_ticket_btn", emoji="🔒")
    async def close_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        is_staff = any(role.id == STAFF_ROLE_ID for role in interaction.user.roles)
        if is_staff or interaction.user.id == OWNER_ID:
            await interaction.response.send_message("🔒 Închidere...")
            await asyncio.sleep(2)
            await interaction.channel.delete()

class TournamentJoinView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="🏆 ÎNSCRIE-TE", style=discord.ButtonStyle.success, custom_id="tr_join_btn")
    async def create_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        if tournament_status != "înscrieri":
            return await interaction.response.send_message("❌ Închis!", ephemeral=True)
        
        category = interaction.guild.get_channel(TOURNAMENT_CATEGORY_ID)
        overwrites = {
            interaction.guild.default_role: discord.PermissionOverwrite(view_channel=False),
            interaction.user: discord.PermissionOverwrite(view_channel=True, send_messages=True),
            interaction.guild.me: discord.PermissionOverwrite(view_channel=True, manage_channels=True)
        }
        
        ticket_ch = await interaction.guild.create_text_channel(name=f"🎫-{interaction.user.name}", category=category, overwrites=overwrites)
        await interaction.response.send_message(f"✅ {ticket_ch.mention}", ephemeral=True)
        
        # Aici punem ambele seturi de butoane să fie vizibile din start
        view = TicketControlView(interaction.user.id, interaction.user.name)
        view.add_item(discord.ui.Button(label="Așteaptă Staff-ul", style=discord.ButtonStyle.secondary, disabled=True))
        
        embed = discord.Embed(title="📝 ÎNSCRIERE", description="Trimite screenshot-ul. Staff-ul va folosi butoanele de mai jos.", color=0x3498db)
        await ticket_ch.send(content=f"{interaction.user.mention}", embed=embed, view=StaffReviewView(interaction.user.id, interaction.user.name))
        await ticket_ch.send("Folosește acest buton pentru a închide ticketul la final:", view=TicketControlView(interaction.user.id, interaction.user.name))

@bot.command()
@commands.is_owner()
async def setup_tournament(ctx):
    await ctx.message.delete()
    embed = discord.Embed(title="🏆 STANDOFF 2 - TOURNAMENT 🏆", description="Apasă butonul de mai jos.", color=0xff0000)
    await ctx.send(embed=embed, view=TournamentJoinView())

@bot.command()
@commands.is_owner()
async def admin_tr(ctx):
    embed = discord.Embed(title="🛡️ PANOU CONTROL OWNER", color=discord.Color.dark_grey())
    view = discord.ui.View()
    btn_start = discord.ui.Button(label="START ÎNSCRIERI", style=discord.ButtonStyle.success)
    async def start_cb(i):
        global tournament_status
        tournament_status = "înscrieri"
        await i.response.send_message("✅ START", ephemeral=True)
    btn_start.callback = start_cb
    btn_stop = discord.ui.Button(label="STOP ÎNSCRIERI", style=discord.ButtonStyle.danger)
    async def stop_cb(i):
        global tournament_status
        tournament_status = "închis"
        await i.response.send_message("🛑 STOP", ephemeral=True)
    btn_stop.callback = stop_cb
    btn_reset = discord.ui.Button(label="RESET DATE", style=discord.ButtonStyle.secondary)
    async def reset_cb(i):
        global tournament_players, bracket_slots, last_table_msg_id
        tournament_players, last_table_msg_id = [], None
        for k in range(1, 18): bracket_slots[k] = "[LIBER]"
        await i.response.send_message("🧹 RESET", ephemeral=True)
    btn_reset.callback = reset_cb
    view.add_item(btn_start); view.add_item(btn_stop); view.add_item(btn_reset)
    await ctx.send(embed=embed, view=view, ephemeral=True)

@bot.event
async def on_ready():
    bot.add_view(TournamentJoinView())
    print(f"✅ {bot.user} este pornit!")

keep_alive()
bot.run(os.getenv("DISCORD_TOKEN"))
