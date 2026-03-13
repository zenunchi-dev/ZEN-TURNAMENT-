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
STAFF_ROLE_ID = 1481794622752555072       
OWNER_ID = 1466541122636611759            
REJECT_ROLE_ID = 1481789988654940272      
TOURNAMENT_ROLE_ID = 1481418649196560414  
SPECIAL_USER_ID = 810609759324471306     

# State Turneu
tournament_players = []
banned_players = [] 
tournament_data = {} 
tournament_status = "închis"
last_table_msg_id = None 

# --- LOGICĂ TABEL TEXT ---
bracket_slots = {i: "[LIBER]" for i in range(1, 18)}

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
        f"Ultimul update: Jucătorul {last_user}\n"
        "```"
    )
    return text

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

# ================= SISTEM ACCEPT/REJECT =================

class StaffReviewView(discord.ui.View):
    def __init__(self, player=None, game_id=None):
        super().__init__(timeout=None)
        self.player = player
        self.game_id = game_id

    @discord.ui.button(label="ACCEPTĂ", style=discord.ButtonStyle.success, emoji="✅", custom_id="persistent_accept")
    async def accept(self, interaction: discord.Interaction, button: discord.ui.Button):
        is_staff = any(role.id == STAFF_ROLE_ID for role in interaction.user.roles)
        is_owner = interaction.user.id == OWNER_ID
        if not (is_staff or is_owner):
            return await interaction.response.send_message("❌ Doar Staff/Owner!", ephemeral=True)

        free_slots = [i for i in range(1, 11) if bracket_slots[i] == "[LIBER]"]
        if not free_slots: return await interaction.response.send_message("❌ Tabel plin!", ephemeral=True)

        slot = random.choice(free_slots)
        
        # Extragem membrul din context dacă self.player nu e setat (pentru butoane persistente)
        target = self.player if self.player else interaction.guild.get_member(int(interaction.message.content.split('<@')[1].split('>')[0]))
        
        bracket_slots[slot] = f"{target.name}"
        tournament_players.append(target.id)
        
        await update_table(target.name, "ID")
        await interaction.response.send_message(f"✅ Adăugat pe locul {slot}!")
        self.stop()

    @discord.ui.button(label="REJECTĂ", style=discord.ButtonStyle.danger, emoji="❌", custom_id="persistent_reject")
    async def reject(self, interaction: discord.Interaction, button: discord.ui.Button):
        is_staff = any(role.id == STAFF_ROLE_ID for role in interaction.user.roles)
        is_owner = interaction.user.id == OWNER_ID
        if not (is_staff or is_owner):
            return await interaction.response.send_message("❌ Doar Staff/Owner!", ephemeral=True)

        rej_role = interaction.guild.get_role(REJECT_ROLE_ID)
        target = self.player if self.player else interaction.guild.get_member(int(interaction.message.content.split('<@')[1].split('>')[0]))
        
        if rej_role:
            await target.add_roles(rej_role)
            await interaction.response.send_message(f"❌ Respins. Rolul va fi scos peste 12 ore.")
            async def remove_role_later(member, role_obj):
                await asyncio.sleep(43200) 
                try: await member.remove_roles(role_obj)
                except: pass
            bot.loop.create_task(remove_role_later(target, rej_role))
        self.stop()

# ================= BUTON CLOSE TICKET =================

class TicketControlView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="ÎNCHIDE TICKET", style=discord.ButtonStyle.danger, custom_id="close_ticket_btn", emoji="🔒")
    async def close_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        is_staff = any(role.id == STAFF_ROLE_ID for role in interaction.user.roles)
        is_owner = interaction.user.id == OWNER_ID
        if is_staff or is_owner or interaction.user.id == SPECIAL_USER_ID:
            await interaction.response.send_message("🔒 Se închide...")
            await asyncio.sleep(5)
            await interaction.channel.delete()

# ================= SISTEM ÎNSCRIERE =================

class TournamentJoinView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="🏆 ÎNSCRIE-TE", style=discord.ButtonStyle.success, custom_id="tr_join_btn")
    async def create_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        global tournament_status
        if tournament_status != "înscrieri":
            return await interaction.response.send_message("❌ Înscrierile sunt închise!", ephemeral=True)
        
        if any(role.id == TOURNAMENT_ROLE_ID for role in interaction.user.roles):
            return await interaction.response.send_message("❌ Ești deja înscris!", ephemeral=True)

        guild = interaction.guild
        category = guild.get_channel(TOURNAMENT_CATEGORY_ID)
        
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            interaction.user: discord.PermissionOverwrite(view_channel=True, send_messages=True, attach_files=True),
            guild.get_role(STAFF_ROLE_ID): discord.PermissionOverwrite(view_channel=True, send_messages=True),
            guild.get_member(OWNER_ID): discord.PermissionOverwrite(view_channel=True, send_messages=True),
            guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True, manage_channels=True)
        }

        ticket_channel = await guild.create_text_channel(name=f"🎫-{interaction.user.name}", category=category, overwrites=overwrites)
        await interaction.response.send_message(f"✅ Ticket creat: {ticket_channel.mention}", ephemeral=True)
        
        embed = discord.Embed(title="📝 ÎNSCRIERE", description="Trimite screenshot-ul. Staff-ul va verifica cererea folosind butoanele de mai jos.", color=0x3498db)
        await ticket_channel.send(content=f"{interaction.user.mention}", embed=embed, view=StaffReviewView(interaction.user, "N/A"))
        await ticket_channel.send("Control ticket:", view=TicketControlView())

# ================= COMENZI ADMIN =================

@bot.command()
@commands.is_owner()
async def setup_tournament(ctx):
    await ctx.message.delete()
    embed = discord.Embed(title="🏆 STANDOFF 2 - TOURNAMENT 🏆", description="Apasă butonul pentru înscriere.", color=0xff0000)
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
        global tournament_players, bracket_slots, last_table_msg_id
        tournament_players = []
        last_table_msg_id = None
        for i in range(1, 18): bracket_slots[i] = "[LIBER]"
        await inter.response.send_message("🧹 Resetat!", ephemeral=True)
    btn_reset.callback = reset_callback
    view.add_item(btn_start); view.add_item(btn_stop); view.add_item(btn_reset)
    await ctx.send(embed=embed, view=view, ephemeral=True)

@bot.event
async def on_ready():
    # ÎNREGISTRARE PERSISTENTĂ A TUTUROR VEDERILOR
    bot.add_view(TournamentJoinView())
    bot.add_view(TicketControlView())
    bot.add_view(StaffReviewView())
    print(f"✅ Bot Online!")

keep_alive()
bot.run(os.getenv("DISCORD_TOKEN"))
