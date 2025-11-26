import discord
from discord.ext import commands
import json
import os
from datetime import datetime

# Bot setup
intents = discord.Intents.default()
intents.message_content = True
intents.reactions = True
bot = commands.Bot(command_prefix='!', intents=intents)

# Data storage
DRAFT_DATA_FILE = 'draft_data.json'
ROSTER_FILE = 'thanksgiving_rosters.json'

# Draft defaults
DEFAULT_ROUNDS = 5

# Emoji numbers for selection
NUMBER_EMOJIS = ['1️⃣', '2️⃣', '3️⃣', '4️⃣', '5️⃣', '6️⃣', '7️⃣', '8️⃣', '9️⃣', '🔟']

# Position emojis for navigation
POSITION_EMOJIS = {
    '🏈': 'QB',
    '🏃': 'RB',
    '🙌': 'WR',
    '🤲': 'TE'
}

# Roster layout for positional displays
ROSTER_POSITIONS = ['QB', 'RB', 'WR', 'TE']

class RosterManager:
    def __init__(self):
        self.players = []
        self.players_by_position = {}
        self.load_rosters()
    
    def load_rosters(self):
        """Load roster data from JSON file"""
        if os.path.exists(ROSTER_FILE):
            try:
                with open(ROSTER_FILE, 'r') as f:
                    self.players = json.load(f)
                
                # Organize by position
                for player in self.players:
                    pos = player['position']
                    if pos not in self.players_by_position:
                        self.players_by_position[pos] = []
                    self.players_by_position[pos].append(player)
                
                print(f"✅ Loaded {len(self.players)} players from rosters")
            except Exception as e:
                print(f"⚠️ Could not load roster file: {e}")
        else:
            print(f"⚠️ Roster file not found: {ROSTER_FILE}")
    
    def get_top_available(self, position, drafted_players, limit=10):
        """Get top available players at a position"""
        available = []
        for player in self.players_by_position.get(position, []):
            player_key = f"{player['name'].lower()}|{player['team'].lower()}"
            if player_key not in drafted_players:
                available.append(player)
        
        return available[:limit]

roster_manager = RosterManager()

class DraftManager:
    def __init__(self):
        self.base_draft_order = []
        self.draft_order = []
        self.current_pick = 0
        self.num_rounds = 0
        self.teams = {}
        self.all_picks = []
        self.is_active = False
        self.channel_id = None
        self.drafted_players = set()
        self.current_draft_message = None
        self.current_position = 'QB'
        self.load_data()

    def end_draft(self):
        """End the current draft session while preserving picks"""
        self.is_active = False
        self.channel_id = None
        self.current_draft_message = None
        self.save_data()
    
    def start_draft(self, draft_order, num_rounds, channel_id):
        self.base_draft_order = draft_order
        self.num_rounds = num_rounds
        self.channel_id = channel_id
        self.is_active = True
        self.current_pick = 0
        self.all_picks = []
        self.drafted_players = set()
        self.current_position = 'QB'
        
        # Create snake draft order
        self.draft_order = self.create_snake_order()
        
        # Initialize teams
        self.teams = {user_id: {'players': [], 'team_name': f'Team {i+1}'} 
                     for i, user_id in enumerate(draft_order)}
        
        self.save_data()
    
    def create_snake_order(self):
        """Create snake draft order (1-2-3, 3-2-1, 1-2-3, etc.)"""
        order = []
        for round_num in range(self.num_rounds):
            if round_num % 2 == 0:
                order.extend(self.base_draft_order)
            else:
                order.extend(reversed(self.base_draft_order))
        return order
    
    def get_current_user(self):
        if self.current_pick < len(self.draft_order):
            return self.draft_order[self.current_pick]
        return None
    
    def get_next_user(self):
        if self.current_pick + 1 < len(self.draft_order):
            return self.draft_order[self.current_pick + 1]
        return None
    
    def get_current_round(self):
        return (self.current_pick // len(self.base_draft_order)) + 1
    
    def is_player_drafted(self, player_name, team_abbr):
        key = f"{player_name.lower()}|{team_abbr.lower()}"
        return key in self.drafted_players
    
    def add_pick(self, player_name, player_team, position):
        if self.current_pick >= len(self.draft_order):
            return None, "Draft is complete!"
        
        # Check if already drafted
        player_key = f"{player_name.lower()}|{player_team.lower()}"
        if player_key in self.drafted_players:
            return None, f"{player_name} ({player_team}) has already been drafted!"
        
        user_id = self.draft_order[self.current_pick]
        
        pick_data = {
            'player_name': player_name,
            'player_team': player_team,
            'position': position,
            'pick_number': len(self.all_picks) + 1,
            'round': self.get_current_round()
        }
        
        self.teams[user_id]['players'].append(pick_data)
        self.all_picks.append({
            'user_id': user_id,
            **pick_data
        })
        
        self.drafted_players.add(player_key)
        self.current_pick += 1
        self.save_data()
        
        return user_id, None
    
    def undo_last_pick(self):
        if not self.all_picks:
            return False
        
        last_pick = self.all_picks.pop()
        user_id = last_pick['user_id']
        
        # Remove from team
        self.teams[user_id]['players'] = [
            p for p in self.teams[user_id]['players'] 
            if p['pick_number'] != last_pick['pick_number']
        ]
        
        # Remove from drafted set
        player_key = f"{last_pick['player_name'].lower()}|{last_pick['player_team'].lower()}"
        self.drafted_players.discard(player_key)
        
        self.current_pick -= 1
        self.save_data()
        return True
    
    def save_data(self):
        data = {
            'base_draft_order': self.base_draft_order,
            'draft_order': self.draft_order,
            'current_pick': self.current_pick,
            'num_rounds': self.num_rounds,
            'teams': self.teams,
            'all_picks': self.all_picks,
            'is_active': self.is_active,
            'channel_id': self.channel_id,
            'drafted_players': list(self.drafted_players)
        }
        with open(DRAFT_DATA_FILE, 'w') as f:
            json.dump(data, f, indent=2)
    
    def load_data(self):
        if os.path.exists(DRAFT_DATA_FILE):
            try:
                with open(DRAFT_DATA_FILE, 'r') as f:
                    data = json.load(f)
                self.base_draft_order = data.get('base_draft_order', [])
                self.draft_order = data.get('draft_order', [])
                self.current_pick = data.get('current_pick', 0)
                self.num_rounds = data.get('num_rounds', 0)
                self.teams = data.get('teams', {})
                self.all_picks = data.get('all_picks', [])
                self.is_active = data.get('is_active', False)
                self.channel_id = data.get('channel_id')
                self.drafted_players = set(data.get('drafted_players', []))
            except Exception as e:
                print(f"Error loading draft data: {e}")

draft_manager = DraftManager()


def format_team_roster(players):
    """Format a team's picks into positional roster lines."""
    sorted_players = sorted(players, key=lambda p: p.get('pick_number', 0))

    slots = {pos: None for pos in ROSTER_POSITIONS}
    flex_candidates = []

    for pick in sorted_players:
        pos = pick.get('position')
        if pos in slots and slots[pos] is None:
            slots[pos] = pick
        else:
            flex_candidates.append(pick)

    lines = []
    for pos in ROSTER_POSITIONS:
        pick = slots[pos]
        if pick:
            lines.append(f"{pos}: {pick['player_name']} ({pick['position']} - {pick['player_team']})")
        else:
            lines.append(f"{pos}: —")

    if flex_candidates:
        flex_text = " / ".join(
            [f"{p['player_name']} ({p['position']} - {p['player_team']})" for p in flex_candidates]
        )
    else:
        flex_text = "—"

    lines.append(f"Flex: {flex_text}")

    return "\n".join(lines)

@bot.event
async def on_ready():
    print(f'Starting bot...')
    print(f'{bot.user} has connected to Discord!')
    print(f'Bot is ready in {len(bot.guilds)} guild(s)')

async def create_draft_board(ctx, position):
    """Create visual draft board with top 10 players"""
    current_user_id = draft_manager.get_current_user()
    current_round = draft_manager.get_current_round()
    pick_in_round = ((draft_manager.current_pick) % len(draft_manager.base_draft_order)) + 1
    
    # Get top available players
    available_players = roster_manager.get_top_available(
        position, 
        draft_manager.drafted_players,
        limit=10
    )
    
    if not available_players:
        embed = discord.Embed(
            title=f"❌ No {position} Available",
            description="All players at this position have been drafted. Try another position!",
            color=discord.Color.red()
        )
        return embed, []
    
    # Create embed
    embed = discord.Embed(
        title=f"🏈 DRAFT BOARD - {position}",
        description=f"**Round {current_round}, Pick {pick_in_round}**\n<@{current_user_id}> is on the clock!\n\n**React with a number to draft:**",
        color=discord.Color.blue()
    )
    
    # Add players
    for i, player in enumerate(available_players[:10]):
        emoji = NUMBER_EMOJIS[i]
        name = player['name']
        team = player['team']
        pos = player['position']
        
        embed.add_field(
            name=f"{emoji} {name}",
            value=f"{pos} - {team}",
            inline=True
        )
        
        # Add thumbnail for first player if available
        if i == 0 and player.get('headshot'):
            embed.set_thumbnail(url=player['headshot'])
    
    # Add position navigation
    embed.add_field(
        name="\n🔄 Switch Position",
        value="🏈 QB | 🏃 RB | 🙌 WR | 🤲 TE",
        inline=False
    )
    
    embed.set_footer(text=f"Pick #{draft_manager.current_pick + 1} of {len(draft_manager.draft_order)}")
    
    return embed, available_players

@bot.command(name='setdraftorder')
async def set_draft_order(ctx, *user_mentions):
    """Set and save a specific base draft order"""
    if not user_mentions:
        await ctx.send("❌ Please mention users in the desired order: `!setdraftorder @User1 @User2 @User3`")
        return

    draft_order = [str(user.id) for user in ctx.message.mentions]

    if len(draft_order) < 2:
        await ctx.send("❌ Need at least 2 users for a draft order!")
        return

    draft_manager.base_draft_order = draft_order
    draft_manager.save_data()

    order_text = "\n".join([f"{i+1}. <@{uid}>" for i, uid in enumerate(draft_order)])
    embed = discord.Embed(
        title="✅ Draft Order Saved",
        description=f"The base draft order has been set:\n{order_text}\n\nUse `!startdraft` to start using this order, or provide mentions to override it.",
        color=discord.Color.green()
    )

    await ctx.send(embed=embed)

@bot.command(name='startdraft')
async def start_draft(ctx, *args):
    """Start a new visual draft (defaults to 5 rounds)"""
    rounds = DEFAULT_ROUNDS

    # Support an optional explicit rounds argument; otherwise default to 5
    if args:
        try:
            possible_rounds = int(args[0])
            if possible_rounds != DEFAULT_ROUNDS:
                await ctx.send("❌ Drafts are limited to exactly 5 rounds. No other round counts are supported.")
                return
            rounds = possible_rounds
            args = args[1:]
        except ValueError:
            # First argument is a mention; keep default rounds
            pass

    # Draft order can be provided directly or pulled from a saved order
    if ctx.message.mentions:
        draft_order = [str(user.id) for user in ctx.message.mentions]
    else:
        draft_order = draft_manager.base_draft_order

    if len(draft_order) < 2:
        await ctx.send("❌ Need at least 2 users for a draft! Provide mentions or set a saved order with `!setdraftorder`.")
        return
    
    draft_manager.start_draft(draft_order, rounds, ctx.channel.id)
    
    # Create initial announcement
    order_text = "\n".join([f"{i+1}. <@{uid}>" for i, uid in enumerate(draft_order)])
    
    embed = discord.Embed(
        title="🏈 VISUAL DRAFT STARTED!",
        description=f"**Draft Order:**\n{order_text}\n\n**{rounds} rounds** • **Snake format**",
        color=discord.Color.green()
    )
    embed.set_footer(text="Starting draft board...")
    
    await ctx.send(embed=embed)
    
    # Show first draft board
    embed, players = await create_draft_board(ctx, 'QB')
    message = await ctx.send(embed=embed)
    
    # Add reaction options
    for i in range(min(len(players), 10)):
        await message.add_reaction(NUMBER_EMOJIS[i])
    
    # Add position navigation
    for emoji in POSITION_EMOJIS.keys():
        await message.add_reaction(emoji)

    draft_manager.current_draft_message = message.id

@bot.command(name='enddraft')
async def end_draft(ctx):
    """End the current draft early"""
    if not draft_manager.is_active:
        await ctx.send("❌ There is no active draft to end. Use `!startdraft` to begin a new one.")
        return

    total_picks = len(draft_manager.all_picks)
    draft_manager.end_draft()

    embed = discord.Embed(
        title="🛑 Draft Ended",
        description=(
            f"Ended by <@{ctx.author.id}>.\n\n"
            f"**Picks recorded:** {total_picks}\n"
            "Use `!export` to download results or `!startdraft` to begin a new draft."
        ),
        color=discord.Color.red()
    )

    await ctx.send(embed=embed)

@bot.event
async def on_reaction_add(reaction, user):
    """Handle draft selections via reactions"""
    # Ignore bot reactions
    if user.bot:
        return
    
    # Check if this is the active draft message
    if not draft_manager.is_active:
        return
    
    if draft_manager.current_draft_message != reaction.message.id:
        return
    
    # Check if it's the correct user's turn
    current_user_id = draft_manager.get_current_user()
    if str(user.id) != current_user_id:
        await reaction.message.channel.send(f"❌ <@{user.id}> - It's not your turn! <@{current_user_id}> is on the clock.")
        await reaction.remove(user)
        return
    
    emoji = str(reaction.emoji)
    
    # Handle position switching
    if emoji in POSITION_EMOJIS:
        draft_manager.current_position = POSITION_EMOJIS[emoji]
        
        # Update board
        embed, players = await create_draft_board(reaction.message.channel, draft_manager.current_position)
        await reaction.message.edit(embed=embed)
        
        # Clear and re-add reactions
        await reaction.message.clear_reactions()
        for i in range(min(len(players), 10)):
            await reaction.message.add_reaction(NUMBER_EMOJIS[i])
        for pos_emoji in POSITION_EMOJIS.keys():
            await reaction.message.add_reaction(pos_emoji)
        
        return
    
    # Handle player selection
    if emoji in NUMBER_EMOJIS:
        player_index = NUMBER_EMOJIS.index(emoji)
        
        # Get available players
        available_players = roster_manager.get_top_available(
            draft_manager.current_position,
            draft_manager.drafted_players,
            limit=10
        )
        
        if player_index >= len(available_players):
            await reaction.message.channel.send("❌ Invalid selection!")
            await reaction.remove(user)
            return
        
        selected_player = available_players[player_index]
        
        # Make the pick
        user_id, error = draft_manager.add_pick(
            selected_player['name'],
            selected_player['team'],
            selected_player['position']
        )
        
        if error:
            await reaction.message.channel.send(f"❌ {error}")
            await reaction.remove(user)
            return
        
        # Announce the pick
        pick_number = len(draft_manager.all_picks)
        current_round = draft_manager.get_current_round()
        pick_in_round = ((pick_number - 1) % len(draft_manager.base_draft_order)) + 1
        
        embed = discord.Embed(
            title=f"✅ Pick #{pick_number} (Round {current_round}, Pick {pick_in_round})",
            description=f"<@{user.id}> selects:",
            color=discord.Color.green()
        )
        embed.add_field(name="Player", value=selected_player['name'], inline=True)
        embed.add_field(name="Position", value=selected_player['position'], inline=True)
        embed.add_field(name="Team", value=selected_player['team'], inline=True)
        
        if selected_player.get('headshot'):
            embed.set_thumbnail(url=selected_player['headshot'])
        
        await reaction.message.channel.send(embed=embed)
        
        # Check if draft is complete
        if draft_manager.current_pick >= len(draft_manager.draft_order):
            await reaction.message.channel.send("🎉 **DRAFT COMPLETE!** Use `!teams` to see all rosters or `!export` to get data for scoring.")
            draft_manager.is_active = False
            draft_manager.save_data()
            return
        
        # Show next draft board
        draft_manager.current_position = 'QB'  # Reset to QB
        embed, players = await create_draft_board(reaction.message.channel, 'QB')
        new_message = await reaction.message.channel.send(embed=embed)
        
        # Add reactions
        for i in range(min(len(players), 10)):
            await new_message.add_reaction(NUMBER_EMOJIS[i])
        for pos_emoji in POSITION_EMOJIS.keys():
            await new_message.add_reaction(pos_emoji)
        
        draft_manager.current_draft_message = new_message.id
        
        # Ping next user
        next_user_id = draft_manager.get_current_user()
        next_round = draft_manager.get_current_round()
        next_pick_in_round = ((draft_manager.current_pick) % len(draft_manager.base_draft_order)) + 1
        
        await reaction.message.channel.send(f"🔔 <@{next_user_id}> - You're on the clock! (Round {next_round}, Pick {next_pick_in_round})")

@bot.command(name='teams')
async def show_teams(ctx):
    """Show all current team rosters"""
    if not draft_manager.teams:
        await ctx.send("❌ No draft data available!")
        return
    
    for user_id, team_data in draft_manager.teams.items():
        roster_text = format_team_roster(team_data['players']) if team_data['players'] else "No picks yet"

        embed = discord.Embed(
            title=f"🏈 {team_data['team_name']}",
            description=f"**Manager:** <@{user_id}>\n\n{roster_text}",
            color=discord.Color.blue()
        )
        embed.set_footer(text=f"{len(team_data['players'])} players")

        await ctx.send(embed=embed)

@bot.command(name='myteam')
async def show_my_team(ctx):
    """Show your current roster"""
    user_id = str(ctx.author.id)
    
    if user_id not in draft_manager.teams:
        await ctx.send("❌ You're not in the current draft!")
        return
    
    team_data = draft_manager.teams[user_id]
    roster_text = format_team_roster(team_data['players']) if team_data['players'] else "No picks yet"
    
    embed = discord.Embed(
        title=f"🏈 {team_data['team_name']}",
        description=roster_text,
        color=discord.Color.blue()
    )
    embed.set_footer(text=f"{len(team_data['players'])} players")
    
    await ctx.send(embed=embed)

@bot.command(name='export')
async def export_data(ctx):
    """Export draft data as JSON for scoring"""
    if not draft_manager.teams:
        await ctx.send("❌ No draft data available!")
        return
    
    export_data = {
        'draft_date': datetime.now().isoformat(),
        'teams': []
    }
    
    for user_id, team_data in draft_manager.teams.items():
        export_data['teams'].append({
            'team_name': team_data['team_name'],
            'user_id': user_id,
            'players': team_data['players']
        })
    
    json_str = json.dumps(export_data, indent=2)
    
    with open('draft_export.json', 'w') as f:
        f.write(json_str)
    
    await ctx.send("📤 Draft data exported!", file=discord.File('draft_export.json'))

# Run bot
token = os.getenv('DISCORD_BOT_TOKEN')
if not token:
    print("❌ Error: DISCORD_BOT_TOKEN not found in environment variables!")
else:
    bot.run(token)
